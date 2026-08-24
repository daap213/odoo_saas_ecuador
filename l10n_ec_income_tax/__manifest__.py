# -*- coding: utf-8 -*-
{
    "name": "Ecuador - Income Tax Engine 2026 (Impuesto Renta)",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Progressive Tax Table & Family Loads Rebate (Resolution 00000043)",
    "description": """
Ecuador Income Tax Engine 2026
==============================

Implements the official 2026 logic for **Impuesto a la Renta Personas Naturales**:

1. **Progressive Table (0-37%)**:
   - Resolution NAC-DGERCGC25-00000043.
   - Calculates "Impuesto Causado" on net taxable income.

2. **Rebaja Tributaria (Tax Credit)**:
   - Replaces former "Deductible Expenses".
   - Based on **Family Loads** (Cargas Familiares).
   - Logic: `Min(Expenses, N * Canasta) * 18%`.
   - Handles Catastrophic Diseases (Max Rebate).

This module provides the calculation engine used by `l10n_ec_hr_payroll`.
    """,
    "author": "Somatech.dev",
    "depends": ["base", "l10n_ec_base"],
    "data": [
        "security/ir.model.access.csv",
        "data/tax_table_2026_data.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
