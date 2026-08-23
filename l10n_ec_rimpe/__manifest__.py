# -*- coding: utf-8 -*-
{
    "name": "Ecuador - RIMPE Regime",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Manage RIMPE (Emprendedores & Negocios Populares)",
    "description": """
        Implements LORTI Art. 97 (RIMPE).
        Supports:
        - Partner Classification (Popular vs Entrepreneur)
        - Document Type 02 (Notas de Venta) logic
        - Special Retention Codes (332B, 343A)
        - Retention Restrictions (0% for Popular)
    """,
    "author": "Somatech Ecuador",
    "depends": ["account", "l10n_ec_base", "l10n_ec_withholding"],
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
