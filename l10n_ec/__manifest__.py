# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "🇪🇨 Ecuador - Localización Completa",
    "version": "19.0.1.0.0",
    "category": "Accounting/Localizations",
    "summary": "Instala TODA la localización Ecuador con un solo clic - SRI 2026, IESS, Aduanas",
    "description": """
🇪🇨 Localización Ecuador Completa para Odoo 18
==============================================

Este módulo instala **TODA** la localización ecuatoriana con **UN SOLO CLIC**:

✅ **Contabilidad** - Plan de Cuentas NEC/NIIF, IVA 15%/5%/0%
✅ **Facturación Electrónica** - XML, XAdES-BES, SRI, RIDE
✅ **Retenciones** - IR, IVA, Regla 5 días
✅ **Punto de Venta** - Facturación POS
✅ **Inventario** - Guía de Remisión
✅ **Reportes** - ATS, Formulario 104
✅ **Nómina** - IESS, Décimos, Utilidades
✅ **Aduanas** - DAU, FODINFA

🔧 **CONFIGURACIÓN AUTOMÁTICA**:
   - Asistente de configuración de empresa
   - Idioma: Español Ecuador
   - País: Ecuador
   - Moneda: USD
   - Zona horaria: America/Guayaquil
   - SBU 2026: $482
   - IVA: 15%

Desarrollado por Somatech.dev
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    "depends": [
        # ================================================================
        # CORE BUSINESS MODULES
        # ================================================================
        "sale_management",  # LORTI Art. 64 - Facturación ventas
        "purchase",  # COPCI Art. 108 - Importaciones
        "stock",  # COPCI Art. 142 - Guía remisión
        "point_of_sale",  # NAC-DGERCGC25-17 - POS electrónico
        "pos_restaurant",  # NAC-DGERCGC25-17 - POS restaurantes
        "account",  # LORTI Art. 19-20 - Contabilidad obligatoria
        "crm",  # Gestión clientes
        "project",  # Gestión proyectos
        "contacts",  # Gestión contactos
        # ================================================================
        # HR COMPLETE - Código Trabajo + IESS + DE 255
        # ================================================================
        "hr",  # Código Trabajo Art. 42 - Registro empleados
        # Odoo 19: hr_contract fue eliminado; hr.contract → hr.version dentro de 'hr'.
        # Código Trabajo Art. 12-17 (contratos escritos) se cubre con hr.version.
        "hr_attendance",  # Código Trabajo Art. 47-55, DE 255 - Control jornada
        "hr_holidays",  # Código Trabajo Art. 69-78 - Vacaciones 15 días
        "hr_timesheet",  # Código Trabajo Art. 55 - Registro horas
        "hr_expense",  # LORTI Art. 10 num. 9 - Gastos deducibles
        # ================================================================
        # MANUFACTURING - INEN + ARCSA
        # ================================================================
        "mrp",  # RTE INEN 142 - Manufactura regulada
        "maintenance",  # DE 255 + MDT-2024-196 - Mantenimiento equipos
        # NOTE: 'quality' is Enterprise-only, will create l10n_ec_quality
        # ================================================================
        # LOGISTICS - LOTTTSV + COPCI
        # ================================================================
        "fleet",  # LOTTTSV Art. 45-52 - Vehículos transporte
        # ================================================================
        # ASSETS - LORTI (Community alternative)
        # ================================================================
        "l10n_ec_asset",  # LORTI Art. 28 num. 6 - Depreciación
        # ================================================================
        # ECUADOR LOCALIZATION MODULES
        # ================================================================
        "l10n_ec_base",  # Plan cuentas NEC, RUC validation
        "l10n_ec_edi",  # NAC-DGERCGC25-17 - Factura electrónica
        "l10n_ec_sri",  # SRI XML, Access Key
        "l10n_ec_withholding",  # LORTI Art. 43-50 - Retenciones
        "l10n_ec_stock",  # COPCI Art. 142 - Guía remisión
        "l10n_ec_pos",  # POS Ecuador
        "l10n_ec_reports",  # LORTI Art. 107 - ATS
        "l10n_ec_hr_payroll",  # Código Trabajo + IESS - Nómina
        "l10n_ec_customs",  # COPCI Art. 108-216 - Aduanas
        "l10n_ec_quality",  # Ley Calidad Art. 31-40, ARCSA Res. 067
    ],
    "data": [
        "security/l10n_ec_security.xml",
        "security/ir.model.access.csv",
        "wizard/l10n_ec_company_setup_wizard_views.xml",
        # Catálogo de plantillas de negocio: dato maestro del módulo, no demo.
        "data/templates/tienda_barrio.xml",
    ],
    # Partners y productos de ejemplo. Sólo se cargan con --without-demo=False;
    # NUNCA en una base de cliente. Antes estaban en "data", lo que los instalaba
    # (y reescribía la compañía) en cada despliegue.
    "demo": [
        "demo/l10n_ec_demo_data.xml",
    ],
    "images": ["static/description/banner.png"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "sequence": 1,
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
}
