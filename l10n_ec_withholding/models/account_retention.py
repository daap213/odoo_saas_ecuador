# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import base64


class AccountRetention(models.Model):
    _name = "account.retention"
    _description = "Comprobante de Retención (Ecuador)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, name desc"

    name = fields.Char(
        string="Document Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default="Draft",
    )
    company_id = fields.Many2one(
        "res.company", index=True, required=True, default=lambda self: self.env.company
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    partner_id = fields.Many2one(
        "res.partner", string="Vendor", required=True, index=True
    )
    date = fields.Date(string="Date", required=True, default=fields.Date.context_today)

    # SRI Integration Fields (Direct Link to Shared Logic)
    l10n_ec_sri_access_key = fields.Char(string="SRI Access Key", copy=False)
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("sent", "Sent"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    l10n_ec_sri_response = fields.Text("SRI Response")
    l10n_ec_xml_data = fields.Binary("XML File", attachment=True)

    # Lines
    retention_line_ids = fields.One2many(
        "account.retention.line", "retention_id", string="Withholding Lines"
    )

    invoice_id = fields.Many2one(
        "account.move", string="Related Bill", domain=[("move_type", "=", "in_invoice")]
    )

    state = fields.Selection(
        [("draft", "Draft"), ("posted", "Posted"), ("cancel", "Cancelled")],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    # =========================================================================
    # REGULACIONES SRI 2026 (Res. NAC-DGERCGC25-00000017)
    # =========================================================================
    # - Transmisión INMEDIATA de comprobantes electrónicos
    # - Anulación permitida hasta día 7 del mes siguiente
    # - Anulación requiere aceptación del receptor en 5 días hábiles
    # - La regla de 5 días para retención YA NO APLICA desde 2026
    # =========================================================================

    def _check_cancellation_allowed(self):
        """
        Valida si el documento puede ser anulado según regulaciones SRI 2026.

        Regla: Anulación solo hasta el día 7 del mes siguiente a la emisión.
        Resolución NAC-DGERCGC25-00000017
        """
        from datetime import date

        self.ensure_one()

        if not self.date:
            return True

        today = date.today()
        emission_date = self.date

        # Calcular fecha límite: día 7 del mes siguiente
        if emission_date.month == 12:
            limit_date = date(emission_date.year + 1, 1, 7)
        else:
            limit_date = date(emission_date.year, emission_date.month + 1, 7)

        if today > limit_date:
            raise ValidationError(
                _(
                    "No se puede anular este documento.\n\n"
                    "Según Resolución NAC-DGERCGC25-00000017, la anulación solo es "
                    "permitida hasta el día 7 del mes siguiente a la emisión.\n\n"
                    "Fecha de emisión: %s\n"
                    "Fecha límite de anulación: %s\n"
                    "Fecha actual: %s"
                )
                % (emission_date, limit_date, today)
            )

        return True

    @api.constrains("date", "invoice_id")
    def _check_retention_date(self):
        """
        Valida que la fecha de retención sea coherente con la factura.

        NOTA: La regla de 5 días fue ELIMINADA en 2026.
        Solo validamos que la fecha no sea anterior a la factura.
        """
        for record in self:
            if record.invoice_id and record.date:
                inv_date = record.invoice_id.invoice_date
                if not inv_date:
                    continue
                if record.date < inv_date:
                    raise ValidationError(
                        _(
                            "La fecha de retención (%s) no puede ser anterior "
                            "a la fecha de la factura (%s)."
                        )
                        % (record.date, inv_date)
                    )

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo 19: create() siempre recibe una lista de diccionarios.
        for vals in vals_list:
            if vals.get("name", "Draft") == "Draft":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("account.retention") or "Draft"
                )
        return super().create(vals_list)

    def action_post(self):
        self.write({"state": "posted"})
        # Trigger SRI flow here in future

    def _generate_access_key(self):
        """
        Uses l10n_ec_edi.models.access_key
        """
        for record in self:
            if not record.l10n_ec_sri_access_key:
                from ..models.access_key import AccessKey  # Import from EDI module?

                # Better: Use the shared helper if possible or re-implement simple call
                # Since l10n_ec_edi is a dependency, we can import from it.
                # However, Odoo imports are tricky.
                # Let's rely on the method being available or duplicate the helper call for safety in this scope?
                # No, duplicating code is bad.
                # We can call the helper class from l10n_ec_edi.models.access_key
                # But it's not an Odoo model.

                # Option B: Add a transient model or utility in EDI to generate keys.
                # Or just import it:
                from odoo.addons.l10n_ec_edi.models.access_key import AccessKey

                # Check environment
                env = (
                    "2"
                    if record.company_id.l10n_ec_sri_environment == "production"
                    else "1"
                )

                # Parse sequence "001-001-000000001"
                parts = record.name.split("-")
                if len(parts) == 3:
                    estab, pto, seq = parts
                else:
                    # Fallback for draft/bad format
                    estab, pto = "001", "001"
                    seq = record.id

                key = AccessKey.generate(
                    invoice_date=record.date,
                    doc_type="07",  # Retention
                    ruc=record.company_id.vat,
                    environment=env,
                    establishment=estab,
                    emission_point=pto,
                    sequential=seq,
                )
                record.l10n_ec_sri_access_key = key

    def action_send_sri(self):
        """
        Generates XML, Signs it, and Sends to SRI.
        """
        for record in self:
            if not record.l10n_ec_sri_access_key:
                record._generate_access_key()

            # 1. Render XML
            values = {
                "retention": record,
                "company": record.company_id,
                "partner": record.partner_id,
                "environment": (
                    "1" if record.company_id.l10n_ec_sri_environment == "test" else "2"
                ),
                "access_key": record.l10n_ec_sri_access_key,
                "format_monetary": lambda x: "%.2f" % x,
                "format_float": lambda x, p: ("%." + str(p) + "f") % x,
                "identifier_code": (
                    "05"
                    if record.partner_id.l10n_ec_identifier_type == "cedula"
                    else "04"
                ),  # Simplified
            }
            xml_content = self.env["ir.qweb"]._render(
                "l10n_ec_withholding.l10n_ec_retention_xml", values
            )

            # 2. Sign
            certificate = record.company_id.l10n_ec_certificate_id
            if not certificate or certificate.state != "active":
                raise UserError(
                    _("SRI Error: No active Signing Certificate configured.")
                )

            try:
                # Use AbstractModels from l10n_ec_edi
                service = self.env["l10n_ec.sri.service"]

                signed_xml_bytes = certificate.sign_xml(xml_content.encode("utf-8"))

                # 3. Transmit
                env_code = (
                    "1" if record.company_id.l10n_ec_sri_environment == "test" else "2"
                )
                response_data = service.send_document(record.company_id, signed_xml_bytes)

                # 4. Process
                if response_data.get("status") == "RECIBIDA":
                    record.l10n_ec_sri_status = "sent"
                    record.l10n_ec_sri_response = (
                        "RECIBIDA. Waiting for Authorization..."
                    )
                else:
                    record.l10n_ec_sri_status = "rejected"
                    msgs = "\n".join(response_data.get("messages", []))
                    record.l10n_ec_sri_response = (
                        f"{response_data.get('status')}: {msgs}"
                    )

                record.l10n_ec_xml_data = base64.b64encode(signed_xml_bytes)

            except Exception as e:
                record.l10n_ec_sri_response = f"System Error: {str(e)}"
                # Don't rollback, save the error
