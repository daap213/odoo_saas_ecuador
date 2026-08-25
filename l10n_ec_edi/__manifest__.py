# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Electronic Invoicing (SRI 2026)",
    "version": "19.0.1.1.0",
    "category": "Accounting/Localizations",
    "summary": "Electronic Invoicing, XAdES-BES Signing, and SRI Transmission (Ficha 2.34)",
    "description": """
Ecuador Electronic Invoicing Module
===================================

This module provides full SRI electronic invoicing:

* XML Generation (Factura 1.1.0, Anexo 3 de la Ficha Técnica)
* XAdES-BES Digital Signature (RSA-SHA1 + SHA-1, §6.8 de la Ficha)
* Access Key generation (49 digits, Mod 11)
* SRI SOAP transmission (Test/Production)
* RIDE PDF generation
* Consumidor Final validation ($50 limit, no annulment)
* Configurable annulment deadline (l10n_ec.annulment_day_limit)

**Ficha Técnica**: Version 2.34 (julio 2026)
**Regulatory Compliance**: SRI 2026, Resolution NAC-DGERCGC25-00000017
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "l10n_ec_base",
        "account_edi",
        # Chatter y actividades: el aviso de caducidad del certificado y la entrega
        # del comprobante al receptor (Ficha §4.7) los necesitan.
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_ec_certificate_views.xml",
        "views/res_company_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "images": ["static/description/banner.png"],
    "external_dependencies": {
        "python": ["zeep", "cryptography", "lxml", "requests"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
