# -*- coding: utf-8 -*-
from odoo import models, fields, _
import base64
from datetime import datetime
from odoo.exceptions import UserError


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
        values = {
            "wizard": self,
            "company": self.company_id,
            "purchases": data["purchases"],
            "sales": data["sales"],
            "cancelled": data["cancelled"],
            "total_sales": sum(
                s["baseImpGrav"] + s["baseNoGraIva"] for s in data["sales"]
            ),
            "format_float": lambda x, p: ("%." + str(p) + "f") % x,
        }
        xml_content = self.env["ir.qweb"]._render(
            "l10n_ec_reports.l10n_ec_ats_xml", values
        )
        return xml_content.encode("utf-8")

    def _get_ats_data(self):
        """
        Core logic to fetch and aggregate data for ATS, Form 103, and Form 104.
        """
        try:
            date_start = datetime.strptime(
                f"{self.date_year}-{self.date_month}-01", "%Y-%m-%d"
            ).date()
            if self.date_month == "12":
                date_end = datetime.strptime(
                    f"{int(self.date_year)+1}-01-01", "%Y-%m-%d"
                ).date()
            else:
                date_end = datetime.strptime(
                    f"{self.date_year}-{int(self.date_month)+1:02d}-01", "%Y-%m-%d"
                ).date()
        except ValueError:
            raise UserError(_("Invalid Date Configuration"))

        # 1. PURCHASES
        domain_in = [
            ("move_type", "=", "in_invoice"),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ]
        in_invoices = self.env["account.move"].search(domain_in)
        purchases_data = []

        for inv in in_invoices:
            # Map ID Type
            if inv.partner_id.l10n_ec_identifier_type == "ruc":
                tpId = "01"
            elif inv.partner_id.l10n_ec_identifier_type == "cedula":
                tpId = "02"
            else:
                tpId = "03"

            parts = (
                inv.l10n_latam_document_number.split("-")
                if inv.l10n_latam_document_number
                else []
            )
            estab, pto, sec = parts if len(parts) == 3 else ("001", "001", "999999999")

            # Bases
            base_0 = sum(
                l.price_subtotal for l in inv.invoice_line_ids if not l.tax_ids
            )
            base_15 = sum(l.price_subtotal for l in inv.invoice_line_ids if l.tax_ids)

            # Tax Split (ICE vs IVA)
            monto_iva = 0.0
            monto_ice = 0.0
            for line in inv.line_ids:
                if line.tax_line_id:
                    if (
                        hasattr(line.tax_line_id, "l10n_ec_ice_category_id")
                        and line.tax_line_id.l10n_ec_ice_category_id
                    ):
                        monto_ice += abs(line.balance)
                    elif line.tax_group_id.name == "ICE":
                        monto_ice += abs(line.balance)
                    elif (
                        "IVA" in line.tax_group_id.name
                        or "VAT" in line.tax_group_id.name
                    ):
                        monto_iva += abs(line.balance)

            # Retentions. El modelo `account.retention` se consolidó en
            # `l10n_ec.retention`, que no tiene campo `state`: su ciclo de vida es
            # `l10n_ec_sri_status`. Al ATS sólo deben llegar las ya emitidas.
            retentions_recs = self.env["l10n_ec.retention"].search(
                [
                    ("invoice_id", "=", inv.id),
                    ("l10n_ec_sri_status", "in", ("sent", "authorized")),
                ]
            )
            air_data = []
            ret_info = {
                "estabRet": "000",
                "ptoEmiRet": "000",
                "secRet": "0",
                "autRet": "0",
                "fechaEmiRet": "",
            }

            if retentions_recs:
                main_ret = retentions_recs[0]
                ret_parts = main_ret.name.split("-") if main_ret.name else []
                if len(ret_parts) == 3:
                    ret_info["estabRet"] = ret_parts[0]
                    ret_info["ptoEmiRet"] = ret_parts[1]
                    ret_info["secRet"] = ret_parts[2]
                ret_info["autRet"] = main_ret.l10n_ec_sri_access_key or "0000000000"
                ret_info["fechaEmiRet"] = main_ret.date_issue.strftime("%d/%m/%Y")

                for line in main_ret.tax_ids:
                    tax = line.tax_id
                    # El módulo AIR del ATS sólo reporta retenciones de renta
                    # (tabla 19, código 1). Se usa el resolutor que NO lanza para
                    # clasificar; el código sí debe estar configurado, y si falta es
                    # preferible que la declaración falle a presentarla mal.
                    if tax._l10n_ec_resolve_retention_tax() != "1":
                        continue
                    air_data.append(
                        {
                            "code": tax.l10n_ec_get_retention_code(),
                            "base": line.base_amount,
                            "percent": abs(tax.amount or 0.0),
                            "val": line.amount,
                        }
                    )

            purchases_data.append(
                {
                    "sustento": inv.l10n_ec_sustento_code or "01",
                    "tpIdProv": tpId,
                    "idProv": inv.partner_id.vat,
                    "tipoComprobante": inv.l10n_latam_document_type_id.code or "01",
                    "fechaRegistro": inv.date.strftime("%d/%m/%Y"),
                    "estab": estab,
                    "ptoEmi": pto,
                    "secuencial": sec,
                    "fechaEmision": inv.invoice_date.strftime("%d/%m/%Y"),
                    "autorizacion": inv.l10n_ec_authorization or "9999999999",
                    "baseNoGraIva": 0.0,
                    "baseImponible": base_0,
                    "baseImpGrav": base_15,
                    "montoIva": monto_iva,
                    "montoIce": monto_ice,
                    "retentions": air_data,
                    **ret_info,
                }
            )

        # 2. SALES
        domain_out = [
            ("move_type", "=", "out_invoice"),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "posted"),
            ("company_id", "=", self.company_id.id),
        ]
        # Use search instead of read_group to correctly calculate ICE
        out_invoices = self.env["account.move"].search(domain_out)

        # Aggregate in Python manually
        sales_agg = {}  # Key: (partner_id, doc_type_id)

        for inv in out_invoices:
            pid = inv.partner_id.id
            dtype = inv.l10n_latam_document_type_id.id
            key = (pid, dtype)

            if key not in sales_agg:
                sales_agg[key] = {
                    "partner": inv.partner_id,
                    "dtype": inv.l10n_latam_document_type_id,
                    "untaxed": 0.0,
                    "iva": 0.0,
                    "ice": 0.0,
                    "count": 0,
                }

            # Sum logic
            sales_agg[key]["untaxed"] += inv.amount_untaxed
            sales_agg[key]["count"] += 1

            # Split Tax
            for line in inv.line_ids:
                if line.tax_line_id:
                    if (
                        hasattr(line.tax_line_id, "l10n_ec_ice_category_id")
                        and line.tax_line_id.l10n_ec_ice_category_id
                    ):
                        sales_agg[key]["ice"] += abs(line.balance)
                    elif line.tax_group_id.name == "ICE":
                        sales_agg[key]["ice"] += abs(line.balance)
                    elif (
                        "IVA" in line.tax_group_id.name
                        or "VAT" in line.tax_group_id.name
                    ):
                        sales_agg[key]["iva"] += abs(line.balance)

        sales_data = []
        for key, val in sales_agg.items():
            partner = val["partner"]
            if partner.l10n_ec_identifier_type == "ruc":
                tpId = "04"
            elif partner.l10n_ec_identifier_type == "cedula":
                tpId = "05"
            else:
                tpId = "06"

            sales_data.append(
                {
                    "tpIdCliente": tpId,
                    "idCliente": partner.vat,
                    "tipoComprobante": val["dtype"].code or "18",
                    "count": val["count"],
                    "baseImpGrav": val["untaxed"],
                    "montoIva": val["iva"],
                    "montoIce": val["ice"],
                    "baseNoGraIva": 0.0,
                    "baseImponible": 0.0,
                }
            )

        return {
            "purchases": purchases_data,
            "sales": sales_data,
            "cancelled": self._get_cancelled_documents(date_start, date_end),
        }

    def _get_cancelled_documents(self, date_start, date_end):
        domain = [
            ("move_type", "in", ["out_invoice", "in_invoice"]),
            ("invoice_date", ">=", date_start),
            ("invoice_date", "<", date_end),
            ("state", "=", "cancel"),
            ("company_id", "=", self.company_id.id),
        ]
        cancelled_moves = self.env["account.move"].search(domain)
        data = []
        for inv in cancelled_moves:
            data.append(
                {
                    "tipo": inv.l10n_latam_document_type_id.code or "01",
                    "estab": "001",
                    "pto": "001",
                    "sec": "0",
                    "aut": "",
                }
            )
        return data
