# -*- coding: utf-8 -*-
from odoo import models, fields


class L10nEcVehicle(models.Model):
    _name = "l10n_ec.vehicle"
    _description = "Transport Vehicle (Ecuador)"

    name = fields.Char(string="Vehicle Name", required=True, help="e.g., Truck 01")
    license_plate = fields.Char(
        string="License Plate", required=True, help="e.g., ABC-1234"
    )
    model_year = fields.Char(
        string="Model Year"
    )  # Renamed from model to avoid confusion with Odoo model
    brand = fields.Char(string="Brand")
    active = fields.Boolean(default=True)
