# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Electronic Invoicing (SRI 2026)",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Electronic Invoicing, XAdES-BES Signing, and SRI Transmission (Ficha 2.32)",
    "description": """
Ecuador Electronic Invoicing Module
===================================

This module provides full SRI electronic invoicing:

* XML Generation (Factura, Nota Crédito, Nota Débito, Guía Remisión)
* XAdES-BES Digital Signature (SHA-256)
* Access Key generation (49 digits, Mod 11)
* SRI SOAP transmission (Test/Production)
* RIDE PDF generation
* Consumidor Final validation ($50 limit, no annulment)
* 7-day annulment rule enforcement

**Ficha Técnica**: Version 2.32
**Regulatory Compliance**: SRI 2026, Resolution NAC-DGERCGC25-00000017
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "l10n_ec_base",
        "account_edi",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_ec_certificate_views.xml",
        "views/res_company_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "external_dependencies": {
        "python": ["zeep", "cryptography", "lxml", "requests"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
