# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Point of Sale (Electronic Invoicing)",
    "version": "19.0.1.0.0",
    "category": "Sales/Point of Sale",
    "summary": "SRI Electronic Invoicing for POS",
    "description": """
Ecuador POS Electronic Invoicing
================================

SRI electronic invoicing integration for Point of Sale:

* Real-time invoice generation at POS
* RUC/Cédula customer identification
* Consumidor Final support ($50 limit)
* Receipt with SRI authorization number
* RIDE printing
* Offline mode support

**Regulatory Compliance**: SRI 2026
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "point_of_sale",
        "l10n_ec_edi",
    ],
    "data": [
        "views/pos_config_views.xml",
    ],
    "assets": {
        "point_of_sale._assets_pos": [
            "l10n_ec_pos/static/src/js/**/*",
            "l10n_ec_pos/static/src/xml/**/*",
        ],
    },
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": False,
    "auto_install": False,
}
