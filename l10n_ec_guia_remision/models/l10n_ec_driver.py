# -*- coding: utf-8 -*-
from odoo import models, fields


class L10nEcDriver(models.Model):
    _name = "l10n_ec.driver"
    _description = "Transport Driver (Ecuador)"

    name = fields.Char(string="Driver Name", required=True)
    identification_type = fields.Selection(
        [("cedula", "Cédula"), ("ruc", "RUC"), ("pasaporte", "Pasaporte")],
        string="Identification Type",
        default="cedula",
        required=True,
    )

    identification_number = fields.Char(string="Identification Number", required=True)
    country_id = fields.Many2one(
        "res.country",
        string="País",
        default=lambda self: self.env.ref("base.ec", raise_if_not_found=False),
        help="Determina el código de la tabla 6: un transportista no residente "
             "sin cédula ni pasaporte se identifica con 08 (exterior).",
    )
    country_code = fields.Char(related="country_id.code", string="Código de país")
    license_number = fields.Char(
        string="License Number", help="Driver's License ID (Licencia de Conducir)"
    )
    active = fields.Boolean(default=True)
