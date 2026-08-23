# -*- coding: utf-8 -*-
{
    "name": "Ecuador - Bank Cash Management (Pichincha/Guayaquil)",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Generate TXT files for Bulk Payroll Payments",
    "description": """
Ecuador Bank Transfer - Cash Management
=======================================

**The Fragata ERP Killer Feature.**
Generates the specific `.txt` files required by Ecuadorian banks for bulk payroll transfers.

Supported Banks:
1.  **Banco Pichincha** (Cash Management Carga de Pagos)
2.  **Banco Guayaquil** (Multicash)

Usage:
1.  Select Payslips in List View.
2.  Action > Generate Cash Management File.
3.  Upload to Bank Portal.
    """,
    "author": "Somatech.dev",
    "depends": ["l10n_ec_hr_payroll"],
    "data": [
        "security/ir.model.access.csv",
        "views/bank_transfer_view.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
