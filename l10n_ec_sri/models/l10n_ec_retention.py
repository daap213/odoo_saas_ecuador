# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class L10nEcRetention(models.Model):
    _name = "l10n_ec.retention"
    _description = "Ecuadorian Withholding (Retención)"
    _inherit = ["portal.mixin", "mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain="[('move_type', '=', 'in_invoice')]",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner", related="invoice_id.partner_id", string="Supplier", store=True
    )
    date_issue = fields.Date(
        string="Date Issue", default=fields.Date.context_today, required=True
    )

    # Tax Lines
    tax_ids = fields.One2many(
        "l10n_ec.retention.line", "retention_id", string="Withholding Lines"
    )

    # SRI Fields
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent to SRI"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
    )
    l10n_ec_sri_access_key = fields.Char(string="Access Key", size=49, copy=False)
    l10n_ec_authorization_date = fields.Datetime(
        string="Authorization Date", copy=False
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.model
    def create(self, vals):
        if vals.get("name", _("New")) == _("New"):
            # Use Native Odoo Sequence Engine
            vals["name"] = self.env["ir.sequence"].next_by_code(
                "l10n_ec.retention"
            ) or _("New")
        return super(L10nEcRetention, self).create(vals)

    def action_post(self):
        self.l10n_ec_sri_status = "draft"  # Ready to send

    def action_send_sri(self):
        """
        Orchestrator for Retention: XML Gen -> Sign -> Send
        """
        for ret in self:
            if ret.l10n_ec_sri_status in ["authorized", "sent"]:
                continue

            # 1. Generate Access Key & XML
            # render_xml returns bytes
            xml_content = self.env["l10n_ec.sri.retention.xml"].render_xml(ret)
            if not isinstance(xml_content, bytes):
                xml_content = xml_content.encode("utf-8")

            # 2. Sign XML (Reuse Signer)
            certificate = ret.company_id.l10n_ec_certificate_id
            if not certificate:
                raise UserError(_("No active Electronic Signature found."))

            signed_xml = self.env["l10n_ec.sri.signer"].sign_xml(
                xml_content, certificate.content, certificate.password
            )

            # 3. Send to SRI
            response = self.env["l10n_ec.sri.service"].send_document(
                signed_xml, environment=ret.company_id.l10n_ec_sri_environment
            )

            if response.get("status") == "RECIBIDA":
                ret.l10n_ec_sri_status = "sent"
                # Optional: Schedule check
            else:
                ret.l10n_ec_sri_status = "rejected"
                # ret.l10n_ec_sri_error = ... (Add field if needed)

    def action_check_sri(self):
        """
        Check Status for Retention
        """
        for ret in self:
            if not ret.l10n_ec_sri_access_key:
                raise UserError(_("No Access Key."))

            response = self.env["l10n_ec.sri.service"].check_authorization(
                ret.l10n_ec_sri_access_key
            )

            if response.get("status") == "AUTORIZADO":
                ret.l10n_ec_sri_status = "authorized"
                if response.get("date"):
                    from datetime import timezone as _tz
                    d = response["date"]
                    if hasattr(d, 'tzinfo') and d.tzinfo is not None:
                        d = d.astimezone(_tz.utc).replace(tzinfo=None)
                    ret.l10n_ec_authorization_date = d
            elif response.get("status") == "NO AUTORIZADO":
                ret.l10n_ec_sri_status = "rejected"


class L10nEcRetentionLine(models.Model):
    _name = "l10n_ec.retention.line"
    _description = "Withholding Tax Line"

    retention_id = fields.Many2one(
        "l10n_ec.retention", string="Retention", ondelete="cascade"
    )
    tax_id = fields.Many2one("account.tax", string="Tax", required=True)
    base_amount = fields.Monetary(string="Base Amount", required=True)
    amount = fields.Monetary(string="Withheld Amount", required=True)
    currency_id = fields.Many2one(
        "res.currency", related="retention_id.company_id.currency_id"
    )

    @api.onchange("tax_id", "base_amount")
    def _compute_amount(self):
        for line in self:
            if line.tax_id and line.base_amount:
                # Use Native Odoo Tax Engine (compute_all)
                # This respects python formulas, rounding, and currency settings configured in Odoo
                taxes = line.tax_id.compute_all(
                    line.base_amount,
                    line.currency_id,
                    1.0,  # Quantity
                    False,  # Product
                )
                # compute_all returns {'total_included': x, 'total_excluded': y, 'taxes': [...]}
                # The 'amount' of the tax is total_included - total_excluded (since it's a withholding, it behaves like a tax)
                # But for withholding, usually we look at the specific tax amount calculated.
                if taxes["taxes"]:
                    line.amount = abs(taxes["taxes"][0]["amount"])
                else:
                    line.amount = 0.0
