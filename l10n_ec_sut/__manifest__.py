# -*- coding: utf-8 -*-
{
    "name": "Ecuador - SUT Reports (MDT)",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Legal",
    "summary": "Generate TXT/XML for Ministry of Labor (Salarios en Línea)",
    "description": """
Ecuador SUT Reports
===================

Generates compliance files for the **Sistema Único de Trabajo (SUT)**:

1. **13th Salary Report**: TXT for bulk upload.
2. **14th Salary Report**: TXT for bulk upload.
3. **Utilidades**: (Placement for future logic).

Ensures Art. 13 and Art. 14 compliance reporting.
    """,
    "author": "Somatech.dev",
    # account: sut_report_wizard.py consulta account_move_line / account_account /
    # account_move con SQL directo; sin este depends las tablas no existen.
    "depends": ["l10n_ec_hr_payroll", "account"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/sut_report_wizard_view.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
