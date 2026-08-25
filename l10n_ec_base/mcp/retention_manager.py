# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

"""
Retention Manager - Gestión de Retenciones vía MCP

Este módulo proporciona operaciones para retenciones IR/IVA
cumpliendo la regla de 5 días y códigos SRI.
"""

import logging
from datetime import date, timedelta
from typing import Optional

_logger = logging.getLogger(__name__)

# Códigos de Retención IR
RETENTION_CODES_IR = {
    '303': {'rate': 10.0, 'name': 'Honorarios Profesionales'},
    '304': {'rate': 8.0, 'name': 'Servicios Predomina Intelecto'},
    '307': {'rate': 2.0, 'name': 'Servicios Mano de Obra'},
    '308': {'rate': 2.0, 'name': 'Servicios Entre Sociedades'},
    '309': {'rate': 1.0, 'name': 'Publicidad y Comunicación'},
    '310': {'rate': 1.0, 'name': 'Transporte'},
    '312': {'rate': 1.0, 'name': 'Bienes Muebles'},
    '319': {'rate': 1.0, 'name': 'Arrendamiento Mercantil'},
    '320': {'rate': 1.75, 'name': 'Arrendamiento Inmuebles'},
    '322': {'rate': 1.0, 'name': 'Seguros y Reaseguros'},
    '323': {'rate': 2.0, 'name': 'Rendimientos Financieros'},
    '340': {'rate': 1.0, 'name': 'Artes Gráficas'},
    '344': {'rate': 25.0, 'name': 'Dividendos Residentes'},
    '500': {'rate': 25.0, 'name': 'Pagos Paraísos Fiscales'},
}

# Códigos de Retención IVA
RETENTION_CODES_IVA = {
    '721': {'rate': 10.0, 'name': 'Bienes'},
    '723': {'rate': 20.0, 'name': 'Servicios'},
    '725': {'rate': 30.0, 'name': 'Bienes (Contribuyente Especial)'},
    '727': {'rate': 70.0, 'name': 'Servicios (Contribuyente Especial)'},
    '729': {'rate': 100.0, 'name': 'Liquidación de Compra'},
    '731': {'rate': 100.0, 'name': 'Profesionales'},
}


class RetentionManager:
    """
    Gestor de retenciones IR/IVA vía MCP.

    Proporciona operaciones para crear y validar retenciones
    cumpliendo la regla de 5 días hábiles.
    """

    def __init__(self, env):
        """
        Inicializa el gestor con el environment de Odoo.

        Args:
            env: Odoo environment
        """
        self.env = env
        # `account.retention` se consolidó en `l10n_ec.retention` (módulo
        # l10n_ec_sri). Se usa env.get() porque este wrapper MCP puede correr contra
        # una base donde l10n_ec_sri no esté instalado.
        self.Retention = env.get('l10n_ec.retention')
        self.Move = env['account.move']

    def calculate_retention(
        self,
        base_amount: float,
        code: str,
        retention_type: str = 'ir'
    ) -> dict:
        """
        Calcula el monto de retención según código SRI.

        Args:
            base_amount: Monto base imponible
            code: Código de retención SRI
            retention_type: 'ir' o 'iva'

        Returns:
            dict: {code, name, rate, base, amount}
        """
        codes = RETENTION_CODES_IR if retention_type == 'ir' else RETENTION_CODES_IVA

        if code not in codes:
            return {
                'success': False,
                'error': f'Código {code} no válido para retención {retention_type.upper()}'
            }

        info = codes[code]
        amount = base_amount * (info['rate'] / 100)

        return {
            'success': True,
            'code': code,
            'name': info['name'],
            'rate': info['rate'],
            'base': base_amount,
            'amount': round(amount, 2)
        }

    def validate_5_day_rule(self, invoice_date: date, retention_date: date = None) -> dict:
        """
        Valida la regla de 5 días hábiles para retenciones.

        Args:
            invoice_date: Fecha de la factura
            retention_date: Fecha de la retención (default: hoy)

        Returns:
            dict: {valid, days_elapsed, message}
        """
        if not retention_date:
            retention_date = date.today()

        # Calcular días hábiles (excluyendo fines de semana)
        business_days = 0
        current = invoice_date

        while current < retention_date:
            current += timedelta(days=1)
            if current.weekday() < 5:  # Lunes a Viernes
                business_days += 1

        is_valid = business_days <= 5

        return {
            'valid': is_valid,
            'days_elapsed': business_days,
            'message': 'Dentro del plazo' if is_valid else f'Excede el plazo: {business_days} días hábiles (máximo 5)'
        }

    def create_retention(
        self,
        invoice_id: int,
        lines: list,
        retention_date: date = None
    ) -> dict:
        """
        Crea una retención para una factura.

        Args:
            invoice_id: ID de la factura de compra
            lines: Lista de líneas [{code, base, type}]
            retention_date: Fecha de la retención

        Returns:
            dict: {success, retention_id, number, message}
        """
        try:
            invoice = self.Move.browse(invoice_id)
            if not invoice.exists():
                return {'success': False, 'message': 'Factura no encontrada'}

            if invoice.move_type != 'in_invoice':
                return {'success': False, 'message': 'Solo se aplica a facturas de compra'}

            # Validar regla de 5 días
            validation = self.validate_5_day_rule(
                invoice.invoice_date,
                retention_date or date.today()
            )

            if not validation['valid']:
                return {
                    'success': False,
                    'message': f"Regla 5 días: {validation['message']}"
                }

            # Calcular retenciones
            retention_lines = []
            total_ir = 0
            total_iva = 0

            for line in lines:
                calc = self.calculate_retention(
                    base_amount=line.get('base', 0),
                    code=line.get('code', ''),
                    retention_type=line.get('type', 'ir')
                )

                if calc.get('success'):
                    retention_lines.append(calc)
                    if line.get('type') == 'ir':
                        total_ir += calc['amount']
                    else:
                        total_iva += calc['amount']

            # Si existe modelo de retención, crear registro
            if self.Retention:
                # Implementar creación real aquí
                pass

            return {
                'success': True,
                'lines': retention_lines,
                'total_ir': round(total_ir, 2),
                'total_iva': round(total_iva, 2),
                'total': round(total_ir + total_iva, 2),
                'message': 'Retención calculada exitosamente'
            }

        except Exception as e:
            return {'success': False, 'message': f'Error: {str(e)}'}

    def get_retention_codes(self, retention_type: str = 'all') -> dict:
        """
        Obtiene lista de códigos de retención disponibles.

        Args:
            retention_type: 'ir', 'iva', o 'all'

        Returns:
            dict: Lista de códigos con sus tasas
        """
        result = {'success': True, 'codes': {}}

        if retention_type in ['ir', 'all']:
            result['codes']['ir'] = [
                {'code': k, **v} for k, v in RETENTION_CODES_IR.items()
            ]

        if retention_type in ['iva', 'all']:
            result['codes']['iva'] = [
                {'code': k, **v} for k, v in RETENTION_CODES_IVA.items()
            ]

        return result

    def bulk_create_retentions(self, retentions: list) -> dict:
        """
        Crea múltiples retenciones en lote.

        Args:
            retentions: Lista de retenciones a crear

        Returns:
            dict: Resumen de creación
        """
        result = {
            'created': 0,
            'errors': 0,
            'details': []
        }

        for ret in retentions:
            create_result = self.create_retention(
                invoice_id=ret.get('invoice_id'),
                lines=ret.get('lines', []),
                retention_date=ret.get('date')
            )

            if create_result.get('success'):
                result['created'] += 1
            else:
                result['errors'] += 1

            result['details'].append(create_result)

        return result


def get_retention_manager(env) -> RetentionManager:
    """Factory function para obtener instancia de RetentionManager."""
    return RetentionManager(env)
