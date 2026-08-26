# -*- coding: utf-8 -*-
"""Comprobante de retención (codDoc 07) — Ficha Técnica SRI 2.34."""
import logging
import re

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_RETENTION_NUMBER_RE = re.compile(r"^(\d{3})-(\d{3})-(\d{9})$")


class L10nEcSriRetentionXml(models.AbstractModel):
    _name = "l10n_ec.sri.retention.xml"
    _description = "SRI Retention XML Generator"

    def render_xml(self, retention):
        """XML del comprobante de retención, con prólogo UTF-8.

        La clave de acceso se genera UNA vez y se conserva. Antes se regeneraba en
        cada llamada a render_xml —y encima con un código numérico aleatorio—, así
        que dos renders del mismo comprobante producían dos claves distintas.
        """
        if not retention.l10n_ec_sri_access_key:
            retention.l10n_ec_sri_access_key = self._generate_retention_access_key(
                retention
            )

        establishment, emission_point, sequential = self._split_number(retention)
        # Tabla 6 en Python, no en la plantilla. El ternario que había en el QWeb
        # no contemplaba el 08 (exterior) y declaraba como RUC ecuatoriano a un
        # sujeto no residente. El 07 se prohíbe: no se retiene a consumidor final.
        subject_id_type, subject_id = self.env[
            "l10n_ec.sri.xml"
        ]._get_partner_identification(
            retention.partner_id, allow_final_consumer=False)

        # Código del documento que sustenta la retención (tabla 4). Antes caía a
        # '01' dentro de la plantilla, con lo que una retención sobre una
        # liquidación de compra se declaraba sobre una factura.
        sustento_cod_doc = (
            retention.invoice_id.l10n_latam_document_type_id.code or ""
        ).zfill(2) if retention.invoice_id.l10n_latam_document_type_id else ""
        if not sustento_cod_doc:
            raise UserError(_(
                "La factura %(doc)s no tiene tipo de documento, y la retención "
                "debe declarar el código del comprobante que la sustenta "
                "(<codDocSustento>, tabla 4). Asignelo en la factura antes de "
                "emitir.", doc=retention.invoice_id.display_name,
            ))
        values = {
            "record": retention,
            "access_key": retention.l10n_ec_sri_access_key,
            "company": retention.company_id,
            "partner": retention.partner_id,
            "establishment": establishment,
            "emission_point": emission_point,
            "sequential": sequential,
            "environment": self._get_environment(retention.company_id),
            "formatted_date": retention.date_issue.strftime("%d/%m/%Y"),
            "periodo_fiscal": retention.date_issue.strftime("%m/%Y"),
            "subject_id_type": subject_id_type,
            "subject_id": subject_id,
            "sustento_cod_doc": sustento_cod_doc,
            # Anexo 26 (RUC del proveedor) y Anexo 24 (Gran Contribuyente): son
            # obligatorios en TODO comprobante, no sólo en la factura.
            "additional_info": self.env["l10n_ec.sri.xml"]._get_additional_info(
                retention
            ),
        }
        body = self.env["ir.qweb"]._render("l10n_ec_sri.xml_retention", values)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + str(body)

    def get_ride_values(self, retention):
        """Valores del RIDE del comprobante de retención (07).

        Reutiliza el marco común de `l10n_ec_sri.report_ride_document`, que ya no lee
        campos de `account.move`: recibe las fechas y los totales resueltos. Así el
        papel de la retención sale con la misma cabecera de emisor y el mismo bloque
        de autorización que el resto, sin duplicar la maqueta del Anexo 2.

        No tenía RIDE ninguno. El Anexo 2 lo exige para todo comprobante electrónico:
        es lo que se entrega al sujeto retenido y lo que éste archiva como respaldo
        del crédito tributario.
        """
        establishment, emission_point, sequential = self._split_number(retention)
        company = retention.company_id
        sri = self.env["l10n_ec.sri.xml"]
        subject_id_type, subject_id = sri._get_partner_identification(
            retention.partner_id, allow_final_consumer=False
        )

        lines = []
        for line in retention.tax_ids:
            lines.append({
                "base": "%.2f" % line.base_amount,
                "rate": "%.2f" % abs(line.tax_id.amount or 0.0),
                "amount": "%.2f" % abs(line.amount),
                "code": line.tax_id.l10n_ec_get_retention_code(retention.date_issue),
                "tax": line.tax_id.display_name,
            })

        return {
            "record": retention,
            "company": company,
            "partner": retention.partner_id,
            "document_title": "COMPROBANTE DE RETENCIÓN",
            "document_code": "07",
            "body_template": "l10n_ec_sri.report_ride_body_retention",
            "counterparty_label": "Sujeto Retenido",
            "counterparty_id_label": "Identificación",
            "buyer_id_type": subject_id_type,
            "buyer_identification": subject_id,
            "document_number": "%s-%s-%s" % (
                establishment, emission_point, sequential),
            "access_key": retention.l10n_ec_sri_access_key or "",
            "environment_label": (
                "PRODUCCIÓN"
                if self._get_environment(company) == "2" else "PRUEBAS"
            ),
            "emission_date": retention.date_issue or "",
            "authorization_date": getattr(
                retention, "l10n_ec_authorization_date", False) or "",
            "fiscal_period": retention.date_issue.strftime("%m/%Y"),
            "lines": lines,
            "sustento": {
                "number": retention.invoice_id.l10n_latam_document_number or "",
                "date": (retention.invoice_id.invoice_date.strftime("%d/%m/%Y")
                         if retention.invoice_id.invoice_date else ""),
            },
            "total_retained": "%.2f" % sum(
                abs(line.amount) for line in retention.tax_ids),
            # La retención no lleva formas de pago ni el bloque de subtotales de IVA
            # de la factura: su único total es lo retenido, que va en su propia tabla.
            "show_payments": False,
            "show_totals": False,
            "total_amount": "0.00",
            "modified": False,
            "motivos": [],
            "subtotals": [],
            "additional_info": sri._get_additional_info(retention),
            "rimpe_legend": company.l10n_ec_rimpe_legend(),
            "barcode": sri._get_access_key_barcode(
                retention.l10n_ec_sri_access_key),
            "money": lambda value: "%.2f" % (value or 0.0),
            "quantity": lambda value: "%.6f" % (value or 0.0),
        }

    def _get_environment(self, company):
        """Tabla 4: 1 = Pruebas, 2 = Producción.

        Aquí estaba uno de los fallos más graves del módulo: se metía en la clave de
        acceso el valor CRUDO del campo de selección, es decir la cadena literal
        'test' o 'production'. La clave dejaba de ser numérica y el módulo 11
        reventaba: la retención electrónica no podía emitirse nunca.
        """
        return "2" if company.l10n_ec_sri_environment == "production" else "1"

    def _split_number(self, record):
        """(estab, ptoEmi, secuencial) del comprobante.

        El establecimiento y el punto de emisión salen SIEMPRE del diario, que es la
        única fuente que el SRI valida contra los establecimientos registrados en el
        RUC. El `name` sólo aporta el secuencial.

        Antes esto intentaba parsear `name` con el patrón `001-001-000000001` y, como
        la secuencia no lleva prefijo y produce `000000001`, el patrón NUNCA casaba:
        todas las retenciones se emitían con un `001-001` fijo. Un emisor con otro
        punto de emisión recibía rechazo del SRI sin explicación aparente.
        """
        journal = record.journal_id
        if not journal:
            raise UserError(_(
                "La retención '%s' no tiene diario de emisión, así que no hay de "
                "dónde tomar el establecimiento y el punto de emisión.",
                record.display_name,
            ))

        establishment = (journal.l10n_ec_entity or "").strip()
        emission_point = (journal.l10n_ec_emission or "").strip()
        if not establishment or not emission_point:
            raise UserError(_(
                "El diario '%s' no tiene establecimiento y punto de emisión SRI.\n\n"
                "Configúrelos en Contabilidad > Configuración > Diarios.",
                journal.display_name,
            ))

        number = (record.name or "").strip()
        match = _RETENTION_NUMBER_RE.match(number)
        if match:
            sequential = match.group(3)
        else:
            digits = re.sub(r"\D", "", number)
            if not digits:
                raise UserError(_(
                    "No se puede derivar el secuencial de la retención '%s'.", number
                ))
            sequential = digits[-9:].zfill(9)

        return establishment.zfill(3), emission_point.zfill(3), sequential

    def _generate_retention_access_key(self, record):
        """Clave de acceso de 49 dígitos para el comprobante de retención."""
        company = record.company_id
        ruc = (company.vat or "").strip()
        if not ruc.isdigit() or len(ruc) != 13:
            raise UserError(_(
                "El RUC de la compañía debe tener 13 dígitos numéricos (actual: '%s').",
                ruc or "",
            ))

        establishment, emission_point, sequential = self._split_number(record)

        base_key = "{date}{doc}{ruc}{env}{estab}{pto}{seq}{numeric}{emission}".format(
            date=record.date_issue.strftime("%d%m%Y"),
            doc="07",
            ruc=ruc,
            env=self._get_environment(company),
            estab=establishment,
            pto=emission_point,
            seq=sequential,
            # Determinista, igual que en la factura: un reenvío debe reutilizar la
            # misma clave (Ficha §5.10), no generar una nueva.
            numeric=sequential[-8:].zfill(8),
            emission="1",
        )
        return base_key + self.env["l10n_ec.sri.xml"]._get_modulo_11(base_key)
