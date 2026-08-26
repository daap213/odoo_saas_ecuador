# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    l10n_ec_is_tip = fields.Boolean(
        string="Es propina",
        help="El importe de las líneas con este producto se emite en <propina>, no "
             "en <detalles> ni en la base imponible. Marcarlo en el producto de "
             "servicio del 10 %% que usa el restaurante.",
    )
