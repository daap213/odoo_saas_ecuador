# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Catálogos SRI Ecuador - Modelos Dinámicos

Catálogos oficiales del SRI requeridos para facturación electrónica
y anexos transaccionales. TODOS los datos son dinámicos desde Odoo.

Fuente: Ficha Técnica Comprobantes Electrónicos SRI
        Catálogo ATS (Anexo Transaccional Simplificado)
"""

from odoo import api, fields, models, _


class L10nEcPaymentMethod(models.Model):
    """
    Formas de Pago SRI.

    Catálogo oficial para facturación electrónica.
    """

    _name = 'l10n_ec.payment.method'
    _description = 'Forma de Pago SRI'
    _order = 'code'

    code = fields.Char(
        string='Código SRI',
        required=True,
        help='Código según Ficha Técnica SRI',
    )
    name = fields.Char(
        string='Descripción',
        required=True,
        translate=True,
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de forma de pago debe ser único.",
    )


class L10nEcIdentificationType(models.Model):
    """
    Tipos de Identificación SRI.

    Catálogo para identificar compradores en comprobantes electrónicos.
    """

    _name = 'l10n_ec.identification.type'
    _description = 'Tipo de Identificación SRI'
    _order = 'code'

    code = fields.Char(
        string='Código SRI',
        required=True,
    )
    name = fields.Char(
        string='Descripción',
        required=True,
        translate=True,
    )
    length = fields.Integer(
        string='Longitud',
        help='Longitud del número de identificación',
    )
    validation_type = fields.Selection(
        [
            ('ruc', 'Validación RUC'),
            ('cedula', 'Validación Cédula'),
            ('none', 'Sin validación'),
        ],
        string='Tipo Validación',
        default='none',
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de identificación debe ser único.",
    )


class L10nEcTaxSupport(models.Model):
    """
    Sustentos Tributarios SRI.

    Catálogo para clasificación de gastos en ATS.
    """

    _name = 'l10n_ec.tax.support'
    _description = 'Sustento Tributario SRI'
    _order = 'code'

    code = fields.Char(
        string='Código SRI',
        required=True,
    )
    name = fields.Char(
        string='Descripción',
        required=True,
        translate=True,
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de sustento debe ser único.",
    )


class L10nEcProvince(models.Model):
    """
    Provincias de Ecuador.

    División político-administrativa para direcciones y regímenes.
    """

    _name = 'l10n_ec.province'
    _description = 'Provincia Ecuador'
    _order = 'code'

    code = fields.Char(
        string='Código',
        required=True,
        size=2,
    )
    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True,
    )
    capital = fields.Char(string='Capital')
    region = fields.Selection(
        [
            ('costa', 'Costa'),
            ('sierra', 'Sierra'),
            ('oriente', 'Oriente'),
            ('insular', 'Insular'),
        ],
        string='Región',
        required=True,
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='Estado Odoo',
        help='Mapeo a res.country.state',
    )
    active = fields.Boolean(default=True)

    # Parámetros por región
    decimo_cuarto_month = fields.Selection(
        [
            ('3', 'Marzo'),
            ('8', 'Agosto'),
        ],
        string='Mes Décimo Cuarto',
        compute='_compute_decimo_cuarto',
        store=True,
    )

    @api.depends('region')
    def _compute_decimo_cuarto(self):
        for rec in self:
            if rec.region in ('costa', 'insular'):
                rec.decimo_cuarto_month = '3'  # Marzo
            else:
                rec.decimo_cuarto_month = '8'  # Agosto

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de provincia debe ser único.",
    )


class L10nEcCanton(models.Model):
    """
    Cantones de Ecuador.
    """

    _name = 'l10n_ec.canton'
    _description = 'Cantón Ecuador'
    _order = 'province_id, name'

    code = fields.Char(
        string='Código',
        required=True,
        size=4,
    )
    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True,
    )
    province_id = fields.Many2one(
        'l10n_ec.province',
        string='Provincia',
        required=True,
        ondelete='cascade',
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de cantón debe ser único.",
    )


class L10nEcCIIU(models.Model):
    """
    Códigos CIIU (Clasificación Industrial Internacional Uniforme).

    Actividades económicas para clasificación de empresas.
    """

    _name = 'l10n_ec.ciiu'
    _description = 'Código CIIU Ecuador'
    _order = 'code'

    code = fields.Char(
        string='Código CIIU',
        required=True,
        help='Código de actividad económica CIIU Rev. 4',
    )
    name = fields.Char(
        string='Descripción',
        required=True,
        translate=True,
    )
    section = fields.Char(
        string='Sección',
        help='Letra de sección CIIU',
    )
    parent_id = fields.Many2one(
        'l10n_ec.ciiu',
        string='Código Padre',
    )
    level = fields.Integer(
        string='Nivel',
        compute='_compute_level',
        store=True,
    )
    active = fields.Boolean(default=True)

    @api.depends('code')
    def _compute_level(self):
        for rec in self:
            rec.level = len(rec.code) if rec.code else 0

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código CIIU debe ser único.",
    )


class L10nEcContributorType(models.Model):
    """
    Tipos de Contribuyente SRI.

    Clasificación según obligaciones tributarias.
    """

    _name = 'l10n_ec.contributor.type'
    _description = 'Tipo de Contribuyente SRI'

    code = fields.Char(
        string='Código',
        required=True,
    )
    name = fields.Char(
        string='Nombre',
        required=True,
        translate=True,
    )
    obligado_contabilidad = fields.Boolean(
        string='Obligado Contabilidad',
    )
    retention_agent = fields.Boolean(
        string='Agente de Retención',
    )
    special_contributor = fields.Boolean(
        string='Contribuyente Especial',
    )
    rimpe = fields.Boolean(
        string='Régimen RIMPE',
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de tipo contribuyente debe ser único.",
    )
