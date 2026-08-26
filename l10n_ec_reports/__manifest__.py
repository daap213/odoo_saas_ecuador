# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Reports (ATS, Form 104)",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations/Reporting",
    "summary": "ATS (Anexo Transaccional Simplificado) XML Generation",
    "description": """
Ecuador Tax Reports Module
==========================

SRI Tax reporting for Ecuador:

* ATS (Anexo Transaccional Simplificado)
  - Sales summary
  - Purchases summary
  - Withholdings summary
  - Cancelled documents
  - XML generation for upload to SRI
* Form 104 support (IVA declaration)

**Filing Deadlines**: Monthly, by RUC 9th digit

**Regulatory Compliance**: SRI 2026
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "l10n_ec_base",
        "l10n_ec_edi",
        # El ATS lee l10n_ec.retention, definido en l10n_ec_sri.
        "l10n_ec_sri",
        "l10n_ec_withholding",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/ats_template.xml",
        "report/form_templates.xml",
        "report/reports.xml",
        "wizard/l10n_ec_ats_wizard_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
