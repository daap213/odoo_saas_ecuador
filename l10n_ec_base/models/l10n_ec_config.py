# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Configuración Dinámica Ecuador - Modelo Odoo

IMPORTANTE: Todas las variables son dinámicas desde Odoo.
NADA está hardcodeado. Los valores se cargan desde:
- ir.config_parameter para configuraciones globales
- Modelos específicos para tasas/códigos

Este modelo centraliza:
- Parámetros SRI (IVA, retenciones)
- Parámetros IESS (aportes, topes)
- Parámetros MDT (SBU, beneficios)
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nEcConfig(models.Model):
    """
    Configuración centralizada de parámetros Ecuador.

    Todos los valores fiscales y laborales son dinámicos
    y se pueden modificar por año fiscal.
    """

    _name = 'l10n_ec.config'
    _description = 'Configuración Parámetros Ecuador'
    _rec_name = 'year'
    _order = 'year desc'

    # Identificación
    year = fields.Integer(
        string='Año Fiscal',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        default=lambda self: self.env.company,
    )

    # =========================================================================
    # PARÁMETROS LABORALES (MDT)
    # =========================================================================
    sbu = fields.Float(
        string='Salario Básico Unificado',
        required=True,
        help='Salario básico del año. Fuente: Ministerio del Trabajo',
    )

    hora_trabajo = fields.Float(
        string='Valor Hora Trabajo',
        compute='_compute_hora_trabajo',
        store=True,
    )

    # Horas extras
    recargo_suplementaria = fields.Float(
        string='Recargo Hora Suplementaria (%)',
        default=50.0,
        help='Recargo por hora extra después de jornada normal',
    )
    recargo_extraordinaria = fields.Float(
        string='Recargo Hora Extraordinaria (%)',
        default=100.0,
        help='Recargo feriados y fines de semana',
    )
    recargo_nocturna = fields.Float(
        string='Recargo Hora Nocturna (%)',
        default=25.0,
        help='Recargo jornada nocturna 19:00-06:00',
    )

    # Vacaciones
    dias_vacaciones = fields.Integer(
        string='Días Vacaciones Anuales',
        default=15,
    )
    dias_adicionales_5_anos = fields.Integer(
        string='Días Adicionales por 5+ Años',
        default=1,
        help='Días adicionales de vacaciones por cada año después de 5',
    )

    # =========================================================================
    # PARÁMETROS IESS
    # =========================================================================
    iess_personal = fields.Float(
        string='Aporte Personal IESS (%)',
        required=True,
        help='Porcentaje que aporta el empleado',
    )
    iess_patronal = fields.Float(
        string='Aporte Patronal IESS (%)',
        required=True,
        help='Porcentaje base que aporta el empleador',
    )
    iess_secap = fields.Float(
        string='SECAP (%)',
        default=0.5,
        help='Servicio Ecuatoriano de Capacitación',
    )
    iess_iece = fields.Float(
        string='IECE (%)',
        default=0.5,
        help='Instituto Ecuatoriano de Crédito Educativo',
    )

    iess_total_empleador = fields.Float(
        string='Total Aporte Empleador (%)',
        compute='_compute_iess_total',
        store=True,
    )

    iess_techo_sbu_multiplicador = fields.Integer(
        string='Multiplicador Techo IESS (en SBU)',
        default=25,
        help='Máximo de SBUs para cálculo IESS',
    )
    iess_techo = fields.Float(
        string='Techo Aportación IESS',
        compute='_compute_iess_techo',
        store=True,
    )

    fondos_reserva = fields.Float(
        string='Fondos de Reserva (%)',
        default=8.33,
    )

    # =========================================================================
    # PARÁMETROS TRIBUTARIOS (SRI)
    # =========================================================================
    iva_general = fields.Float(
        string='IVA General (%)',
        required=True,
        help='Tarifa general IVA',
    )
    iva_construccion = fields.Float(
        string='IVA Construcción (%)',
        default=5.0,
        help='Tarifa reducida para construcción (Ley 2024)',
    )
    isd = fields.Float(
        string='ISD (%)',
        default=5.0,
        help='Impuesto Salida de Divisas',
    )
    isd_exencion = fields.Float(
        string='Exención ISD ($)',
        default=5000.0,
    )

    # Límites
    limite_consumidor_final = fields.Float(
        string='Límite Consumidor Final ($)',
        default=50.0,
        help='Monto máximo factura sin datos cliente',
    )

    # =========================================================================
    # ESTADÍSTICAS INEC
    # =========================================================================
    canasta_basica = fields.Float(
        string='Canasta Básica Familiar ($)',
        help='Costo canasta básica según INEC',
    )
    canasta_vital = fields.Float(
        string='Canasta Vital ($)',
    )

    # =========================================================================
    # CÁLCULOS
    # =========================================================================
    @api.depends('sbu')
    def _compute_hora_trabajo(self):
        for rec in self:
            rec.hora_trabajo = rec.sbu / 240 if rec.sbu else 0

    @api.depends('iess_patronal', 'iess_secap', 'iess_iece')
    def _compute_iess_total(self):
        for rec in self:
            rec.iess_total_empleador = (
                rec.iess_patronal + rec.iess_secap + rec.iess_iece
            )

    @api.depends('sbu', 'iess_techo_sbu_multiplicador')
    def _compute_iess_techo(self):
        for rec in self:
            rec.iess_techo = rec.sbu * rec.iess_techo_sbu_multiplicador

    # =========================================================================
    # MÉTODOS DE CONSULTA
    # =========================================================================
    @api.model
    def get_current_config(self, year=None):
        """
        Obtiene la configuración del año actual o especificado.

        Args:
            year: Año fiscal (default: año actual)

        Returns:
            Recordset de l10n_ec.config
        """
        if not year:
            year = fields.Date.today().year

        config = self.search([
            ('year', '=', year),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

        if not config:
            raise ValidationError(
                _(f'No existe configuración para el año {year}. '
                  'Configure los parámetros en Configuración > Ecuador.')
            )

        return config

    @api.model
    def get_sbu(self, year=None):
        """Obtiene el SBU del año."""
        return self.get_current_config(year).sbu

    @api.model
    def get_iess_rates(self, year=None):
        """Obtiene tasas IESS del año."""
        config = self.get_current_config(year)
        return {
            'personal': config.iess_personal,
            'patronal': config.iess_patronal,
            'secap': config.iess_secap,
            'iece': config.iess_iece,
            'total_empleador': config.iess_total_empleador,
            'techo': config.iess_techo,
        }

    @api.model
    def get_iva_rate(self, year=None):
        """Obtiene tasa IVA general del año."""
        return self.get_current_config(year).iva_general

    _year_company_unique = models.Constraint(
        "UNIQUE(year, company_id)",
        "Solo puede existir una configuración por año y empresa.",
    )


class L10nEcRetentionCode(models.Model):
    """
    Códigos de Retención IR/IVA.

    Dinámico: Los códigos y tasas se cargan desde este modelo,
    no están hardcodeados.
    """

    _name = 'l10n_ec.retention.code'
    _description = 'Código de Retención Ecuador'
    _order = 'type, code'

    code = fields.Char(
        string='Código SRI',
        required=True,
    )
    name = fields.Char(
        string='Concepto',
        required=True,
    )
    type = fields.Selection(
        [('ir', 'Retención IR'), ('iva', 'Retención IVA')],
        string='Tipo',
        required=True,
    )
    rate = fields.Float(
        string='Tasa (%)',
        required=True,
    )
    active = fields.Boolean(default=True)

    # Aplicabilidad
    applies_to = fields.Selection(
        [
            ('goods', 'Bienes'),
            ('services', 'Servicios'),
            ('both', 'Ambos'),
        ],
        string='Aplica a',
        default='both',
    )

    notes = fields.Text(string='Notas')

    _code_type_unique = models.Constraint(
        "UNIQUE(code, type)",
        "El código de retención debe ser único por tipo.",
    )

    @api.model
    def get_rate_by_code(self, code, retention_type='ir'):
        """
        Obtiene la tasa de retención por código.

        Args:
            code: Código SRI (ej: '303')
            retention_type: 'ir' o 'iva'

        Returns:
            float: Tasa de retención o 0
        """
        record = self.search([
            ('code', '=', code),
            ('type', '=', retention_type),
        ], limit=1)
        return record.rate if record else 0.0


class L10nEcTaxCode(models.Model):
    """
    Códigos de Impuestos SRI.

    Dinámico: Mapeo código SRI → impuesto Odoo.
    """

    _name = 'l10n_ec.tax.code'
    _description = 'Código Impuesto Ecuador'

    code = fields.Char(
        string='Código SRI',
        required=True,
        help='Código según ficha técnica SRI',
    )
    name = fields.Char(
        string='Nombre',
        required=True,
    )
    rate = fields.Float(
        string='Tasa (%)',
    )
    tax_type = fields.Selection(
        [
            ('iva', 'IVA'),
            ('ice', 'ICE'),
            ('isd', 'ISD'),
        ],
        string='Tipo Impuesto',
        required=True,
    )
    tax_id = fields.Many2one(
        'account.tax',
        string='Impuesto Odoo',
        help='Impuesto de Odoo asociado',
    )
    active = fields.Boolean(default=True)

    _code_unique = models.Constraint(
        "UNIQUE(code)",
        "El código de impuesto debe ser único.",
    )
