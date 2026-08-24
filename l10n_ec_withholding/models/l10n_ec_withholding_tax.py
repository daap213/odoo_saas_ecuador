# -*- coding: utf-8 -*-
from odoo import models, fields


class L10nEcWithholdingTax(models.Model):
    _name = "l10n_ec.withholding.tax"
    _description = "Ecuador Withholding Tax Code (SRI Table 19/21)"
    _rec_name = "code"

    code = fields.Char(
        "Code", required=True, index=True, help="SRI Code (e.g., 303, 332B)"
    )
    name = fields.Char("Description", required=True)

    type = fields.Selection(
        [
            ("renta", "Impuesto a la Renta (Table 19)"),
            ("iva", "IVA (Table 21)"),
            ("isd", "ISD"),
        ],
        string="Tax Type",
        required=True,
    )

    percentage = fields.Float("Percentage %", digits=(12, 2), required=True)

    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code, type)",
        "Tax Code must be unique per type!",
    )
