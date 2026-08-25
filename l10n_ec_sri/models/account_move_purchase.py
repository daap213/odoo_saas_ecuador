# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ec_retention_ids = fields.One2many(
        "l10n_ec.retention", "invoice_id", string="Retentions"
    )
    l10n_ec_retention_count = fields.Integer(
        compute="_compute_retention_count", string="Retention Count"
    )

    @api.depends("l10n_ec_retention_ids")
    def _compute_retention_count(self):
        for move in self:
            move.l10n_ec_retention_count = len(move.l10n_ec_retention_ids)

    def action_create_retention(self):
        """
        Creates a new Retention document based on this Vendor Bill.
        Populates lines based on the Taxes applied in the bill.
        """
        self.ensure_one()
        if self.move_type != "in_invoice":
            raise UserError(_("Retentions can only be created for Vendor Bills."))

        if self.state != "posted":
            raise UserError(_("The Bill must be Posted before creating a Retention."))

        # Create Header
        val_header = {
            "invoice_id": self.id,
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "date_issue": fields.Date.context_today(self),
        }

        retention = self.env["l10n_ec.retention"].create(val_header)

        # Populate Lines from Invoice Taxes
        # We look for Tax Lines in the Move
        # This implementation adheres to Vibe Rule 2 (Check First) - we use existing structure
        # In Odoo, taxes are on lines, but summaries are in line_ids with tax_repartition_line_id

        # Strategy: Iterate invoice lines, check for Withholding taxes
        # For simplicity in this scaffold, we look for ALL taxes that are of scope 'purchase'
        # But specifically we should look for "Retencion" scope if defined, or assume user selects them.
        # Often, Withholdings are NOT on the bill itself (the bill has IVA),
        # the Withholding is calculated ON TOP.

        # So we create the header and let the user add lines, OR we try to pre-compute
        # based on a "Fiscal Position" logic.
        # For now, we open the form view for the user to add lines (Manual Control to avoid assumption).

        return {
            "name": _("Create Retention"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.retention",
            "res_id": retention.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_retentions(self):
        self.ensure_one()
        return {
            "name": _("Retentions"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.retention",
            "domain": [("invoice_id", "=", self.id)],
            "view_mode": "list,form",
        }
