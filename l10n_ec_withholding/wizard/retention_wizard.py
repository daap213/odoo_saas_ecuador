# -*- coding: utf-8 -*-
"""Asistente para crear el comprobante de retención desde una factura de compra.

Antes construía un `account.retention` con el código de retención como texto libre
(`tax_code`), que no era lo que la emisión necesita: la plantilla XML lee
`account.tax` para sacar <codigo> y <codigoRetencion>. Ahora crea directamente el
modelo vivo `l10n_ec.retention` con impuestos reales, así que lo que se confirma en
el asistente es exactamente lo que se transmite.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RetentionWizard(models.TransientModel):
    _name = "l10n_ec.retention.wizard"
    _description = "Wizard to Create Withholding Document"

    invoice_id = fields.Many2one("account.move", string="Invoice", required=True)
    partner_id = fields.Many2one(related="invoice_id.partner_id", string="Vendor")
    company_id = fields.Many2one(related="invoice_id.company_id")
    currency_id = fields.Many2one(related="invoice_id.currency_id")
    date = fields.Date(string="Date", default=fields.Date.context_today, required=True)

    line_ids = fields.One2many(
        "l10n_ec.retention.wizard.line", "wizard_id", string="Withholding Lines"
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get("active_model") != "account.move":
            return res
        active_id = self.env.context.get("active_id")
        if not active_id:
            return res

        invoice = self.env["account.move"].browse(active_id)
        res["invoice_id"] = invoice.id

        # Se proponen las dos bases, no los porcentajes: qué impuesto aplica depende
        # del tipo de contribuyente y del bien o servicio, y elegirlo mal es lo que
        # el SRI rechaza. El usuario escoge el `account.tax`, que ya lleva el código.
        #
        # Base de renta  = subtotal sin impuestos.
        # Base de IVA    = el propio valor del IVA (Ficha, tabla 20: la retención de
        #                  IVA es un porcentaje del IVA facturado, no del subtotal).
        vat_amount = invoice.amount_total - invoice.amount_untaxed
        lines = [(0, 0, {"base_amount": invoice.amount_untaxed})]
        if vat_amount > 0:
            lines.append((0, 0, {"base_amount": vat_amount}))
        res["line_ids"] = lines
        return res

    def action_create_retention(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Añada al menos una línea de retención."))

        missing = self.line_ids.filtered(lambda line: not line.tax_id)
        if missing:
            raise UserError(_(
                "Cada línea necesita un impuesto de retención: es de donde salen el "
                "<codigo> y el <codigoRetencion> del comprobante."
            ))

        retention = self.env["l10n_ec.retention"].create({
            "invoice_id": self.invoice_id.id,
            "date_issue": self.date,
            "company_id": self.invoice_id.company_id.id,
            "l10n_ec_sri_status": "draft",
            "tax_ids": [
                (0, 0, {
                    "tax_id": line.tax_id.id,
                    "base_amount": line.base_amount,
                    "amount": line.amount,
                })
                for line in self.line_ids
            ],
        })

        return {
            "name": _("Withholding"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.retention",
            "res_id": retention.id,
            "view_mode": "form",
            "target": "current",
        }


class RetentionWizardLine(models.TransientModel):
    _name = "l10n_ec.retention.wizard.line"
    _description = "Retention Wizard Line"

    wizard_id = fields.Many2one("l10n_ec.retention.wizard", required=True, ondelete="cascade")
    tax_id = fields.Many2one(
        "account.tax",
        string="Retención",
        domain="[('type_tax_use', '=', 'purchase')]",
        help="Impuesto de retención. Su 'Código de Retención SRI' es el que se emite.",
    )
    base_amount = fields.Monetary(string="Base Imponible", required=True)
    amount = fields.Monetary(string="Valor Retenido", compute="_compute_amount", store=True)
    currency_id = fields.Many2one(related="wizard_id.currency_id")

    @api.depends("base_amount", "tax_id")
    def _compute_amount(self):
        """Porcentaje plano sobre la base.

        Una retención ecuatoriana no encadena impuestos ni lleva precio incluido, así
        que la aritmética directa es exacta; `compute_all()` además desapareció en
        Odoo 19.
        """
        for line in self:
            tax = line.tax_id
            if not tax or not line.base_amount:
                line.amount = 0.0
            elif tax.amount_type == "percent":
                line.amount = abs(line.base_amount * tax.amount / 100.0)
            elif tax.amount_type == "fixed":
                line.amount = abs(tax.amount)
            else:
                line.amount = 0.0
