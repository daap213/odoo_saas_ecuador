# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    # El directorio se llama `l10n_ec_guia_remision` y NO `l10n_ec_stock`: ese nombre
    # técnico lo ocupa un módulo del núcleo de Odoo 19 (Odoo S.A.) que sólo añade
    # configuración del plan de cuentas y NO emite guías de remisión. El núcleo gana
    # en `odoo.addons.__path__`, así que mientras este módulo se llamó `l10n_ec_stock`
    # era INALCANZABLE y la guía de remisión no existía. Verificado en Odoo 19.
    "name": "Ecuador - Guía de Remisión electrónica",
    "version": "19.0.1.0.0",
    "category": "Inventory/Localizations",
    "summary": "Guía de Remisión, Transportistas, Motivos de Traslado",
    "description": """
Ecuador Stock & Logistics Module
=================================

Electronic Guía de Remisión (Waybill) for Ecuador:

* Guía de Remisión document (Document Type 06)
* Carrier/Transporter data management
* Transfer reason codes (Venta, Traslado, Exportación, etc.)
* Route information
* XML generation and SRI transmission
* Integration with stock.picking

**Regulatory Compliance**: SRI 2026
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        "l10n_ec_base",
        "l10n_ec_edi",
        "stock",
        # La orquestación (clave de acceso, firma, envío, dispatcher del XML) vive
        # en l10n_ec_sri. La dirección es guía -> sri y NUNCA al revés: l10n_ec_sri
        # no debe arrastrar Inventario a una instalación puramente contable.
        "l10n_ec_sri",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/l10n_ec_transport_views.xml",
        "data/l10n_ec_stock_data.xml",
        "data/ir_cron_data.xml",
        "views/stock_picking_xml_template.xml",
        "report/l10n_ec_guia_ride.xml",
        "views/stock_picking_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
