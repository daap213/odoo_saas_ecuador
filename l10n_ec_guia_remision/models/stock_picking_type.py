# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Diario del que la guía de remisión toma establecimiento y punto de emisión.

Un `stock.picking` no tiene diario ni tipo de documento LATAM, así que no hay de
dónde sacar el `001-001` que el SRI valida contra los establecimientos registrados en
el RUC. Antes se resolvía con un `getattr(..., "001") or "001"`: un punto de emisión
inventado, en silencio, en la clave de acceso y en el cuerpo del comprobante.

Se configura por tipo de operación (cada almacén suele ser un establecimiento
distinto) y, si ahí no hay nada, se cae al de la compañía.
"""
from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    l10n_ec_guia_journal_id = fields.Many2one(
        "account.journal",
        string="Diario para guías de remisión",
        check_company=True,
        domain="[('l10n_ec_entity', '!=', False), ('l10n_ec_emission', '!=', False)]",
        help="Diario del que se toman el establecimiento y el punto de emisión de las "
             "guías de remisión de este tipo de operación. Si se deja vacío se usa el "
             "de la compañía.",
    )


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ec_guia_journal_id = fields.Many2one(
        "account.journal",
        string="Diario para guías de remisión",
        check_company=True,
        domain="[('l10n_ec_entity', '!=', False), ('l10n_ec_emission', '!=', False)]",
        help="Diario por defecto para las guías de remisión, cuando el tipo de "
             "operación no indica uno.",
    )
