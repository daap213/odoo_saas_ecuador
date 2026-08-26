# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Customs (Imports/Exports)",
    "version": "19.0.1.0.0",
    "category": "Operations/Customs",
    "summary": "DAU, Tariff Codes, FODINFA, Import IVA",
    "description": """
Ecuadorian Customs Localization
===============================

Complete customs management for Ecuador (SENAE):

* Declaración Aduanera Única (DAU)
* Tariff Headings (Partidas Arancelarias / HS Codes)
* Import Tax Calculations:
  - Ad Valorem (0-40% based on tariff)
  - FODINFA (0.5% on CIF)
  - IVA Import (15% on CIF + duties)
  - ISD (5% on payments abroad)
* ECUAPASS integration support
* Customs regime tracking

**Regulatory Compliance**: SENAE 2026
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    # l10n_ec_base define los parámetros l10n_ec.fodinfa y l10n_ec.customs_iva en
    # data/l10n_ec_sri_config.xml. Este módulo los declaraba otra vez con IDs
    # externos distintos pero la MISMA clave, lo que rompía la instalación con
    # "duplicate key value violates unique constraint ir_config_parameter_key_uniq".
    # Se depende de la base y se usan sus parámetros en lugar de duplicarlos.
    "depends": ["stock", "account", "purchase", "l10n_ec_base"],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_ec_customs_views.xml",
    ],
    "installable": True,
    "application": False,
}
