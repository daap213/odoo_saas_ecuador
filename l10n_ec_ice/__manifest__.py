# -*- coding: utf-8 -*-
{
    "name": "Ecuador - ICE (Impuesto Consumos Especiales)",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Manage specific and ad valorem ICE taxes",
    "description": """
        Implements LORTI Title III (Art. 75-89) for ICE.
        Supports:
        - Specific Rates (e.g. Cigarettes, Bags)
        - Specific Rates with Content (Alcohol, Sugar)
        - Ad Valorem Rates (Perfumes, Vehicles)
    """,
    "author": "Somatech Ecuador",
    "depends": ["account", "l10n_ec_base", "product"],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_ec.ice.category.csv",
        "views/l10n_ec_ice_category_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
