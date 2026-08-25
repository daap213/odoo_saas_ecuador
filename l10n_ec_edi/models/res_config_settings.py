# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Ambiente SRI y certificado de firma en la página de ajustes de Ecuador.

Van aquí y no en `l10n_ec_base` porque los campos que reflejan viven en
`res.company` y los declara ESTE módulo. `l10n_ec_base` no depende de `l10n_ec_edi`
—la dependencia es al revés—, así que un `related` a estos campos desde allí revienta
al cargar el registro con "Field ... does not exist".
"""
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_ec_sri_environment = fields.Selection(
        related="company_id.l10n_ec_sri_environment",
        readonly=False,
        string="Ambiente SRI",
        help="Pruebas transmite a celcer.sri.gob.ec; Producción a cel.sri.gob.ec. "
             "El endpoint lo resuelve el ambiente salvo que se fuerce una URL "
             "concreta en la compañía.",
    )
    l10n_ec_certificate_id = fields.Many2one(
        related="company_id.l10n_ec_certificate_id",
        readonly=False,
        string="Certificado de firma",
        help="Certificado .p12 activo con el que se firman los comprobantes.",
    )
    l10n_ec_forced_accounting = fields.Boolean(
        related="company_id.l10n_ec_forced_accounting",
        readonly=False,
        string="Obligado a llevar contabilidad",
        help="Viaja como <obligadoContabilidad> en cada comprobante.",
    )
    l10n_ec_special_resolution = fields.Char(
        related="company_id.l10n_ec_special_resolution",
        readonly=False,
        string="Resolución de contribuyente especial",
        help="Viaja como <contribuyenteEspecial>. Vacío = no se emite la etiqueta.",
    )
    l10n_ec_withhold_agent = fields.Boolean(
        related="company_id.l10n_ec_withhold_agent",
        readonly=False,
        string="Agente de retención",
    )
    l10n_ec_withhold_resolution = fields.Char(
        related="company_id.l10n_ec_withhold_resolution",
        readonly=False,
        string="Resolución de agente de retención",
        help="Anexo 21: número de resolución sin ceros a la izquierda, máximo 8 "
             "dígitos. Viaja como <agenteRetencion>.",
    )
    l10n_ec_big_taxpayer_resolution = fields.Char(
        related="company_id.l10n_ec_big_taxpayer_resolution",
        readonly=False,
        string="Resolución de Gran Contribuyente",
        help="Anexo 24: se emite en la información adicional del comprobante.",
    )
