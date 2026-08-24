# -*- coding: utf-8 -*-
from odoo import models, fields


class L10nEcIceCategory(models.Model):
    _name = "l10n_ec.ice.category"
    _description = "ICE Tax Category (SRI)"
    _rec_name = "name"

    code = fields.Char("SRI Code", size=4, required=True, help="Codigo SRI (Tabla 6)")
    name = fields.Char("Description", required=True)

    type = fields.Selection(
        [
            ("specific", "Specific Rate (Amount per Unit)"),
            ("specific_content", "Specific Rate with Content (Alcohol, Sugar)"),
            ("ad_valorem", "Ad Valorem (Percentage of Price)"),
        ],
        string="ICE Type",
        required=True,
        default="ad_valorem",
    )

    # For Specific Rates
    specific_rate = fields.Float(
        "Specific Rate ($)", digits=(12, 4), help="Dollar amount per unit/liter/gram"
    )

    # For Ad Valorem Rates
    ad_valorem_rate = fields.Float("Ad Valorem Rate (%)", digits=(12, 2))

    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint(
        "UNIQUE(code)",
        "The SRI Code must be unique!",
    )
