# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Anexo Transaccional Simplificado.

Todo lo que se declara aqui sale de los MISMOS resolutores que construyen el XML de
los comprobantes. Es deliberado: un comprobante mal formado lo rechaza el SRI y el
error se ve en el acto; un ATS con los codigos o las bases cambiadas **el SRI lo
acepta**, y la diferencia no aparece hasta el cruce de informacion.
"""
import base64
import re
from datetime import date, datetime

from odoo import models, fields, _
from odoo.exceptions import UserError

from odoo.addons.l10n_ec_sri.models.l10n_ec_sri_xml import (
    L10N_EC_TAX_CODE_ICE,
    L10N_EC_TAX_CODE_VAT,
)

_ATS_NUMBER_RE = re.compile(r"^(\d{3})-(\d{3})-(\d{9})$")


class L10nEcAtsWizard(models.TransientModel):
    _name = "l10n_ec.ats.wizard"
    _description = "Anexo Transaccional Simplificado (ATS) Wizard"

    date_month = fields.Selection(
        [
            ("01", "January"),
            ("02", "February"),
            ("03", "March"),
            ("04", "April"),
            ("05", "May"),
            ("06", "June"),
            ("07", "July"),
            ("08", "August"),
            ("09", "September"),
            ("10", "October"),
            ("11", "November"),
            ("12", "December"),
        ],
        string="Month",
        required=True,
        default=lambda self: datetime.now().strftime("%m"),
    )

    date_year = fields.Char(
        string="Year", required=True, default=lambda self: datetime.now().strftime("%Y")
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # Result
    xml_data = fields.Binary("ATS XML", readonly=True)
    xml_filename = fields.Char(string="Filename", readonly=True)

    def action_generate_ats(self):
        self.ensure_one()
        xml_content = self.generate_xml()
        self.xml_data = base64.b64encode(xml_content)
        self.xml_filename = (
            f"ATS_{self.date_month}_{self.date_year}_{self.company_id.vat}.xml"
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.ats.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def action_print_form103(self):
        self.ensure_one()
        data = self._get_ats_data()

        # Prepare data for Form 103 (Retentions)
        # Group by Tax Code
        retention_summary = {}
        for p in data["purchases"]:
            for r in p.get("retentions", []):
                code = r["code"]
                if code not in retention_summary:
                    retention_summary[code] = {
                        "code": code,
                        "name": "Retention " + code,
                        "base": 0.0,
                        "percent": r["percent"],
                        "amount": 0.0,
                    }
                retention_summary[code]["base"] += r["base"]
                retention_summary[code]["amount"] += r["val"]

        report_data = {
            "period": f"{self.date_month}/{self.date_year}",
            "retentions": sorted(retention_summary.values(), key=lambda x: x["code"]),
        }
        return self.env.ref("l10n_ec_reports.action_report_form_103").report_action(
            self, data={"data": report_data}
        )

    def action_print_form104(self):
        self.ensure_one()
        data = self._get_ats_data()

        # Aggregate logic
        sales_base = sum(s["baseImpGrav"] + s["baseNoGraIva"] for s in data["sales"])
        sales_iva = sum(s["montoIva"] for s in data["sales"])
        sales_ice = sum(s.get("montoIce", 0.0) for s in data["sales"])

        purchases_base = sum(
            p["baseImponible"] + p["baseImpGrav"] + p["baseNoGraIva"]
            for p in data["purchases"]
        )
        purchases_iva = sum(p["montoIva"] for p in data["purchases"])
        purchases_ice = sum(p.get("montoIce", 0.0) for p in data["purchases"])

        report_data = {
            "period": f"{self.date_month}/{self.date_year}",
            "sales_base": sales_base,
            "sales_iva": sales_iva,
            "purchases_base": purchases_base,
            "purchases_iva": purchases_iva,
            "ice_payable": sales_ice,
            "ice_credit": purchases_ice,
        }
        return self.env.ref("l10n_ec_reports.action_report_form_104").report_action(
            self, data={"data": report_data}
        )

    def generate_xml(self):
        data = self._get_ats_data()
        establishments = self._l10n_ec_sales_by_establishment(*self._l10n_ec_period_bounds())
        values = {
            "wizard": self,
            "company": self.company_id,
            "purchases": data["purchases"],
            "sales": data["sales"],
            "cancelled": data["cancelled"],
            "establishments": establishments,
            "establishment_count": len(establishments),
            "total_sales": sum(
                s["baseImpGrav"] + s["baseNoGraIva"] + s["baseImponible"]
                + s["baseImpExe"]
                for s in data["sales"]
            ),
            "format_float": lambda x, p: ("%." + str(p) + "f") % x,
        }
        xml_content = self.env["ir.qweb"]._render(
            "l10n_ec_reports.l10n_ec_ats_xml", values
        )
        return xml_content.encode("utf-8")

    # ------------------------------------------------------------------
    # Resolución de datos, compartida con el generador de comprobantes
    # ------------------------------------------------------------------

    def _l10n_ec_split_bases(self, invoice):
        """Bases y montos del ATS, resueltos con el MISMO resolutor que el XML.

        Antes se clasificaba por el NOMBRE del grupo de impuestos
        (`line.tax_group_id.name == "ICE"`, `"IVA" in ...name`) y se partía la base en
        dos por la mera presencia de impuestos en la línea. Dos consecuencias:

        * renombrar un grupo rompía el ATS en silencio — la misma heurística por
          subcadena que `_get_tax_sri_codes` se quitó a propósito del generador;
        * `baseNoGraIva` y `baseImpExe` iban fijos a 0,00, así que lo no objeto de
          IVA y lo exento se declaraban como si fueran base tarifa 0 %.

        `_compute_sri_taxes` ya devuelve, por cada código de la tabla 17, la base y el
        valor. Aquí sólo hay que repartirlos en las casillas del ATS. Un comprobante
        mal formado lo rechaza el SRI; un ATS con las bases cambiadas lo acepta.
        """
        sri = self.env["l10n_ec.sri.xml"]
        totals, _lines = sri._compute_sri_taxes(invoice)

        bases = {
            "baseNoGraIva": 0.0,   # código 6: no objeto de impuesto
            "baseImponible": 0.0,  # código 0: tarifa 0 %
            "baseImpGrav": 0.0,    # el resto de tarifas de IVA
            "baseImpExe": 0.0,     # código 7: exento de IVA
            "montoIva": 0.0,
            "montoIce": 0.0,
        }
        for total in totals:
            base = float(total["baseImponible"])
            value = float(total["valor"])
            if total["codigo"] == L10N_EC_TAX_CODE_ICE:
                bases["montoIce"] += value
                continue
            if total["codigo"] != L10N_EC_TAX_CODE_VAT:
                continue
            bases["montoIva"] += value
            code = total["codigoPorcentaje"]
            if code == "6":
                bases["baseNoGraIva"] += base
            elif code == "7":
                bases["baseImpExe"] += base
            elif code == "0":
                bases["baseImponible"] += base
            else:
                bases["baseImpGrav"] += base

        # Líneas sin ningún impuesto: no aparecen en `_compute_sri_taxes` porque no
        # generan ninguna entrada, y el SRI las quiere declaradas como no objeto.
        untaxed = sum(
            line.price_subtotal
            for line in sri._get_product_lines(invoice)
            if not line.tax_ids
        )
        bases["baseNoGraIva"] += untaxed
        return bases

    def _l10n_ec_document_parts(self, move):
        """(establecimiento, punto de emisión, secuencial) de un comprobante.

        Sin respaldo inventado. La versión anterior caía a
        `("001", "001", "999999999")` cuando el número no venía con el formato
        esperado: eso declara al SRI un comprobante que no existe, con un
        establecimiento que puede no estar registrado en el RUC del emisor. Y a
        diferencia de un comprobante mal formado, **el ATS con datos inventados el
        SRI lo acepta**, así que el error no se descubre hasta una diferencia en el
        cruce.
        """
        number = (move.l10n_latam_document_number or "").strip()
        match = _ATS_NUMBER_RE.match(number)
        if not match:
            return None
        return match.groups()

    def _l10n_ec_check_numbers(self, moves):
        """Detiene la generación listando TODOS los comprobantes sin número válido.

        De uno en uno obligaría a regenerar el anexo tantas veces como facturas
        defectuosas haya.
        """
        offenders = [
            move for move in moves if not self._l10n_ec_document_parts(move)
        ]
        if not offenders:
            return
        raise UserError(_(
            "Estos comprobantes no tienen un número con el formato "
            "001-001-000000001 que el ATS exige, y no se puede declarar uno "
            "inventado en su lugar:\n\n- %(list)s\n\nCorrija el campo 'Número de "
            "documento' en cada uno y vuelva a generar el anexo.",
            list="\n- ".join(
                "%s (%s)" % (move.display_name, move.l10n_latam_document_number or _("vacío"))
                for move in offenders[:40]
            ),
        ))

    def _l10n_ec_retentions_by_invoice(self, invoices):
        """{id de factura: retenciones emitidas}, en UNA sola consulta.

        Estaba dentro del bucle de facturas: un `search` por cada una. En un mes de
        varios miles de compras eso son varios miles de consultas para construir un
        anexo.
        """
        retentions = self.env["l10n_ec.retention"].search([
            ("invoice_id", "in", invoices.ids),
            ("l10n_ec_sri_status", "in", ("sent", "authorized")),
        ], order="date_issue, id")
        grouped = {}
        for retention in retentions:
            grouped.setdefault(retention.invoice_id.id, []).append(retention)
        return grouped

    def _l10n_ec_sales_by_establishment(self, date_start, date_end):
        """Ventas de cada establecimiento, del DIARIO de cada comprobante.

        El bloque <ventasEstablecimiento> declaraba un unico establecimiento con el
        codigo `company.l10n_ec_entity or '001'`. Ese campo no existe en
        `res.company`, asi que el `or` se cumplia siempre y toda empresa —tuviera los
        establecimientos que tuviera— declaraba el total de sus ventas al 001.

        El establecimiento sale del diario, que es de donde sale tambien en la clave
        de acceso de cada comprobante: asi el anexo y los comprobantes declaran lo
        mismo.
        """
        invoices = self.env["account.move"].search([
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ])

        by_establishment = {}
        for invoice in invoices:
            code = (invoice.journal_id.l10n_ec_entity or "").strip().zfill(3)
            if not code.strip("0"):
                continue
            entry = by_establishment.setdefault(code, {
                "code": code, "amount": 0.0, "iva": 0.0,
            })
            bases = self._l10n_ec_split_bases(invoice)
            entry["amount"] += (
                bases["baseImpGrav"] + bases["baseImponible"]
                + bases["baseNoGraIva"] + bases["baseImpExe"]
            )
            entry["iva"] += bases["montoIva"]

        # Un periodo sin ventas es legitimo —un mes de solo compras se declara
        # igual—, asi que la ausencia de establecimientos solo es un error cuando SI
        # hubo ventas y ninguna salio de un diario configurado.
        if invoices and not by_establishment:
            raise UserError(_(
                "Ninguna venta del periodo sale de un diario con establecimiento SRI "
                "configurado, y el ATS declara las ventas por establecimiento.\n\n"
                "Rellene 'Establecimiento SRI' en los diarios de venta "
                "(Contabilidad > Configuracion > Diarios)."
            ))
        return sorted(by_establishment.values(), key=lambda e: e["code"])

    def _get_ats_data(self):
        """Datos del ATS, del Formulario 103 y del 104 para el período."""
        date_start, date_end = self._l10n_ec_period_bounds()

        return {
            "purchases": self._l10n_ec_purchase_lines(date_start, date_end),
            "sales": self._l10n_ec_sale_lines(date_start, date_end),
            "cancelled": self._get_cancelled_documents(date_start, date_end),
        }

    def _l10n_ec_period_bounds(self):
        """Primer día del mes declarado y primer día del siguiente."""
        try:
            year = int(self.date_year)
            month = int(self.date_month)
            date_start = date(year, month, 1)
            date_end = (date(year + 1, 1, 1) if month == 12
                        else date(year, month + 1, 1))
        except (TypeError, ValueError):
            raise UserError(_(
                "El período '%(month)s/%(year)s' no es una fecha válida.",
                month=self.date_month, year=self.date_year,
            ))
        return date_start, date_end

    def _l10n_ec_purchase_lines(self, date_start, date_end):
        """Bloque <compras>: una entrada por comprobante de compra."""
        invoices = self.env["account.move"].search([
            ("move_type", "in", ("in_invoice", "in_refund")),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ], order="invoice_date, id")
        self._l10n_ec_check_numbers(invoices)
        retentions_by_invoice = self._l10n_ec_retentions_by_invoice(invoices)

        purchases = []
        for invoice in invoices:
            establishment, emission_point, sequential = self._l10n_ec_document_parts(
                invoice
            )
            bases = self._l10n_ec_split_bases(invoice)
            retention_info, air = self._l10n_ec_retention_block(
                retentions_by_invoice.get(invoice.id, [])
            )

            purchases.append(dict(bases, **{
                "sustento": invoice.l10n_ec_sustento_code or "",
                "tpIdProv": self._l10n_ec_ats_identification_type(
                    invoice.partner_id, "purchase"),
                "idProv": (invoice.partner_id.vat or "").strip(),
                "tipoComprobante": self._l10n_ec_document_code(invoice),
                "fechaRegistro": invoice.date.strftime("%d/%m/%Y"),
                "estab": establishment,
                "ptoEmi": emission_point,
                "secuencial": sequential,
                "fechaEmision": invoice.invoice_date.strftime("%d/%m/%Y"),
                # En el esquema offline el número de autorización ES la clave de
                # acceso (Anexo 2 de la Ficha).
                "autorizacion": invoice.l10n_ec_sri_access_key or "",
                "retentions": air,
                **retention_info
            }))
        return purchases

    def _l10n_ec_retention_block(self, retentions):
        """(datos de la retención que respalda la compra, detalle AIR).

        Sólo el módulo AIR reporta retenciones de renta (tabla 19, código 1); las de
        IVA van en sus propias casillas del formulario.
        """
        empty = {
            "estabRet": "",
            "ptoEmiRet": "",
            "secRet": "",
            "autRet": "",
            "fechaEmiRet": "",
        }
        if not retentions:
            return empty, []

        main = retentions[0]
        parts = (main.name or "").split("-")
        info = dict(empty)
        if len(parts) == 3:
            info.update({
                "estabRet": parts[0],
                "ptoEmiRet": parts[1],
                "secRet": parts[2],
            })
        # Sin respaldo a "0000000000": una autorización inventada la acepta el SRI y
        # después no cuadra contra el comprobante real. Y si falta, se detiene: el
        # bloque AIR se declararía sin la cabecera que dice de qué retención sale.
        if not main.l10n_ec_sri_access_key:
            raise UserError(_(
                "La retención %s consta como transmitida al SRI pero no tiene "
                "clave de acceso, y el ATS declara la autorización de la "
                "retención que respalda cada compra. Revise su estado antes de "
                "generar el anexo.",
                main.display_name,
            ))
        info["autRet"] = main.l10n_ec_sri_access_key
        info["fechaEmiRet"] = (
            main.date_issue.strftime("%d/%m/%Y") if main.date_issue else ""
        )

        air = []
        for retention in retentions:
            for line in retention.tax_ids:
                tax = line.tax_id
                if tax._l10n_ec_resolve_retention_tax() != "1":
                    continue
                air.append({
                    "code": tax.l10n_ec_get_retention_code(retention.date_issue),
                    "base": line.base_amount,
                    "percent": abs(tax.amount or 0.0),
                    "val": abs(line.amount),
                })
        return info, air

    def _l10n_ec_sale_lines(self, date_start, date_end):
        """Bloque <ventas>: agregado por cliente y tipo de comprobante.

        Incluye las notas de crédito, que antes quedaban fuera del anexo: el filtro
        era `move_type = out_invoice` a secas, así que una devolución se declaraba
        como si no hubiera existido y las ventas salían infladas.
        """
        invoices = self.env["account.move"].search([
            ("move_type", "in", ("out_invoice", "out_refund")),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ], order="invoice_date, id")

        aggregates = {}
        for invoice in invoices:
            key = (invoice.partner_id.id, invoice.l10n_latam_document_type_id.id)
            entry = aggregates.setdefault(key, {
                "partner": invoice.partner_id,
                "document_type": invoice.l10n_latam_document_type_id,
                "count": 0,
                "baseNoGraIva": 0.0,
                "baseImponible": 0.0,
                "baseImpGrav": 0.0,
                "baseImpExe": 0.0,
                "montoIva": 0.0,
                "montoIce": 0.0,
            })
            entry["count"] += 1
            for field_name, amount in self._l10n_ec_split_bases(invoice).items():
                entry[field_name] += amount

        sales = []
        for entry in aggregates.values():
            partner = entry["partner"]
            sales.append({
                "tpIdCliente": self._l10n_ec_ats_identification_type(partner, "sale"),
                "idCliente": (partner.vat or "").strip(),
                # Del campo del contacto, no el literal "NO" que la plantilla
                # escribía para todos: `l10n_ec_related_party` ya existe y se
                # ignoraba.
                "parteRelVentas": (
                    "SI" if getattr(partner, "l10n_ec_related_party", False) else "NO"
                ),
                "tipoComprobante": (entry["document_type"].code or "").zfill(2),
                "tipoEmision": "F",
                "count": entry["count"],
                "baseNoGraIva": entry["baseNoGraIva"],
                "baseImponible": entry["baseImponible"],
                "baseImpGrav": entry["baseImpGrav"],
                "baseImpExe": entry["baseImpExe"],
                "montoIva": entry["montoIva"],
                "montoIce": entry["montoIce"],
                # Retenciones que el CLIENTE nos practicó. Este repositorio no modela
                # la retención recibida —`l10n_ec.retention` sólo cubre las emitidas,
                # su dominio es `in_invoice`—, así que no hay de dónde sacarlas y se
                # declara cero. Queda documentado aquí y no como un `0.00` escrito en
                # la plantilla, que es donde nadie lo iba a encontrar.
                "valorRetIva": 0.0,
                "valorRetRenta": 0.0,
            })
        return sales

    def _l10n_ec_ats_identification_type(self, partner, side):
        """Código de identificación del ATS.

        El catálogo del ATS no coincide con la tabla 6 de los comprobantes, y encima
        difiere entre compras y ventas: en compras 01/02/03 (RUC/cédula/pasaporte) y
        en ventas 04/05/06/07. Estaba escrito con dos cadenas de `if` casi idénticas.
        """
        purchase_codes = {"ruc": "01", "cedula": "02", "pasaporte": "03"}
        sale_codes = {"ruc": "04", "cedula": "05", "pasaporte": "06"}
        codes = purchase_codes if side == "purchase" else sale_codes
        identifier = partner.l10n_ec_identifier_type
        if identifier in codes:
            return codes[identifier]
        vat = (partner.vat or "").strip()
        if len(vat) == 13 and vat.isdigit():
            return codes["ruc"]
        if len(vat) == 10 and vat.isdigit():
            return codes["cedula"]
        return codes["pasaporte"]

    def _l10n_ec_document_code(self, move):
        """codDoc de la tabla 3, sin respaldo silencioso a '01'."""
        code = (move.l10n_latam_document_type_id.code or "").strip()
        if not code:
            raise UserError(_(
                "El comprobante %s no tiene tipo de documento, y el ATS declara el "
                "código de cada uno. Asígnelo antes de generar el anexo.",
                move.display_name,
            ))
        return code.zfill(2)

    def _get_cancelled_documents(self, date_start, date_end):
        """Bloque <anulados>, con los números REALES.

        Escribía `("001", "001", "0")` para todos: el SRI recibía una declaración de
        que se anuló el comprobante 001-001-0, que no existe, en lugar del que de
        verdad se anuló. Los que no tengan número válido se omiten y se avisa, en vez
        de inventarles uno.
        """
        cancelled = self.env["account.move"].search([
            ("move_type", "in", ("out_invoice", "out_refund",
                                 "in_invoice", "in_refund")),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "cancel"),
            ("company_id", "=", self.company_id.id),
        ], order="invoice_date, id")

        data, skipped = [], []
        for move in cancelled:
            parts = self._l10n_ec_document_parts(move)
            if not parts:
                skipped.append(move)
                continue
            establishment, emission_point, sequential = parts
            data.append({
                "tipo": self._l10n_ec_document_code(move),
                "estab": establishment,
                "pto": emission_point,
                "sec": sequential,
                "aut": move.l10n_ec_sri_access_key or "",
            })

        if skipped:
            raise UserError(_(
                "Estos comprobantes anulados no tienen número con formato "
                "001-001-000000001, y el bloque <anulados> del ATS declara el número "
                "exacto de cada uno:\n\n- %(list)s",
                list="\n- ".join(move.display_name for move in skipped[:40]),
            ))
        return data
