# -*- coding: utf-8 -*-
from odoo import models, api
from odoo.exceptions import ValidationError
import random
import logging

_logger = logging.getLogger(__name__)


class L10nEcSriXml(models.AbstractModel):
    _name = "l10n_ec.sri.xml"
    _description = "SRI XML Generator"

    @api.model
    def generate_access_key(self, record):
        """
        Generate 49-digit Access Key.
        Format:
        [0:8]   Date (DDMMYYYY)
        [8:10]  Doc Type (01)
        [10:23] RUC (1234567890001)
        [23:24] Environment (1 or 2)
        [24:30] Establisment/Series (001-001) -> 001001
        [30:39] Sequential (000000001)
        [39:47] Random Number (8 digits)
        [47:48] Emission Type (1)
        [48:49] Verifier Digit (Mod 11)
        """
        # 1. Extraction
        date_inv = record.invoice_date.strftime("%d%m%Y")
        doc_type = record.l10n_latam_document_type_id.code  # e.g., '01'
        ruc = record.company_id.vat
        # SRI: 1=pruebas, 2=produccion.
        env_raw = record.company_id.l10n_ec_sri_environment
        env = "2" if env_raw == "production" else "1"

        # Split Journal: 001-001
        try:
            entity, emission = record.journal_id.code.split(
                "-"
            )  # Simplified extraction hook
            serie = f"{entity}{emission}"
        except:
            # Fallback for now or use fields from journal extension
            # In real implementation, use l10n_ec_entity from `account.journal`
            serie = f"{record.journal_id.l10n_ec_entity}{record.journal_id.l10n_ec_emission}"

        sequential = f"{record.name.split('-')[-1]:0>9}"  # Extract sequence number

        # Random 8 digits
        code_numeric = f"{random.randint(1, 99999999):08d}"
        emission_type = "1"  # Normal

        # 2. Construction (Pre-Verifier)
        base_key = f"{date_inv}{doc_type}{ruc}{env}{serie}{sequential}{code_numeric}{emission_type}"

        # 3. Check Digit (Modulo 11)
        verifier = self._get_modulo_11(base_key)

        access_key = f"{base_key}{verifier}"

        if len(access_key) != 49:
            raise ValidationError(
                f"Generated Access Key length is {len(access_key)}, expected 49."
            )

        return access_key

    def _get_modulo_11(self, key):
        """
        Standard SRI Modulo 11 Algorithm
        """
        key = key[::-1]
        total = 0
        factor = 2

        for char in key:
            total += int(char) * factor
            factor += 1
            if factor > 7:
                factor = 2

        remainder = total % 11
        check_digit = 11 - remainder

        if check_digit == 11:
            check_digit = 0
        elif check_digit == 10:
            check_digit = 1

        return str(check_digit)

    @api.model
    def _compute_sri_taxes(self, record):
        """
        Returns (sri_totals, sri_line_taxes) for XML generation.
        sri_totals: list of dicts for <totalConImpuestos>
        sri_line_taxes: {invoice_line_id -> list of dicts} for <impuestos> in each <detalle>
        """
        TYPE_CODIGO = {'iva': '2', 'ice': '3', 'isd': '5'}

        def get_porcentaje_code(tax):
            amount = round(tax.amount, 2)
            if amount == 15.0: return '4'
            if amount == 5.0:  return '5'
            if amount == 14.0: return '3'
            if amount == 12.0: return '2'
            name = (tax.name or '').lower()
            if 'no objeto' in name: return '6'
            if 'exento' in name:    return '7'
            return '0'

        def get_tipo(tax):
            group = (tax.tax_group_id.name or '').lower()
            if 'ice' in group: return 'ice'
            if 'isd' in group: return 'isd'
            return 'iva'

        # Aggregate totals from invoice lines (avoids journal entry structure dependency)
        totals = {}
        sri_line_taxes = {}
        for line in record.invoice_line_ids:
            base = abs(line.price_subtotal)
            line_taxes = []
            for tax in line.tax_ids:
                codigo = TYPE_CODIGO.get(get_tipo(tax), '2')
                cod_pct = get_porcentaje_code(tax)
                valor = base * (tax.amount / 100.0)
                # accumulate for totalConImpuestos
                key = (codigo, cod_pct)
                if key not in totals:
                    totals[key] = {'codigo': codigo, 'codigoPorcentaje': cod_pct,
                                   'baseImponible': 0.0, 'valor': 0.0}
                totals[key]['baseImponible'] += base
                totals[key]['valor'] += valor
                # per-line entry
                line_taxes.append({
                    'codigo': codigo,
                    'codigoPorcentaje': cod_pct,
                    'tarifa': '%.2f' % tax.amount,
                    'baseImponible': '%.2f' % base,
                    'valor': '%.2f' % valor,
                })
            sri_line_taxes[line.id] = line_taxes

        sri_totals = [
            {'codigo': v['codigo'], 'codigoPorcentaje': v['codigoPorcentaje'],
             'baseImponible': '%.2f' % v['baseImponible'],
             'valor': '%.2f' % v['valor']}
            for v in totals.values()
        ]

        return sri_totals, sri_line_taxes

    @api.model
    def render_xml(self, record):
        sri_totals, sri_line_taxes = self._compute_sri_taxes(record)
        values = {
            "record": record,
            "access_key": record.l10n_ec_sri_access_key,
            "sri_totals": sri_totals,
            "sri_line_taxes": sri_line_taxes,
        }
        return self.env["ir.qweb"]._render("l10n_ec_sri.xml_invoice", values)
