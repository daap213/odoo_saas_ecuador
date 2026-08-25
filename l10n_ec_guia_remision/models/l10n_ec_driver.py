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
    license_number = fields.Char(
        string="License Number", help="Driver's License ID (Licencia de Conducir)"
    )
    active = fields.Boolean(default=True)
