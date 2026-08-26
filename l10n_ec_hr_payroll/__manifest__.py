# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

{
    "name": "Ecuador - Payroll (IESS, Décimos, Utilidades)",
    "version": "19.0.1.0.0",
    "category": "Human Resources/Payroll",
    "summary": "Complete Ecuadorian payroll with IESS, Décimos, and Utilidades",
    "description": """
Ecuadorian Payroll Localization
===============================

Complete payroll management for Ecuador (SBU 2026: $482):

* IESS Contributions
  - Personal: 9.45%
  - Patronal: 11.15% (base IESS) + SECAP 0.5% + IECE 0.5% = 12.15% total
* Décimo Tercero (13th Salary) - Due December 24
* Décimo Cuarto (14th Salary)
  - Costa/Galápagos: March 15
  - Sierra/Amazonía: August 15
* Fondos de Reserva (8.33% after 13 months)
* Utilidades (15% profit sharing - April 15)
* Overtime calculations (50%, 100%, 25%)
* Income Tax (Impuesto a la Renta)

**Regulatory Compliance**: Ministerio del Trabajo 2026, IESS 2026
    """,
    "author": "Somatech.dev, Odoo Community Association (OCA)",
    "website": "https://github.com/somatechlat/odoo_saas_ecuador",
    "license": "LGPL-3",
    # Odoo 19 eliminó hr_contract: hr.contract pasó a ser hr.version dentro de hr.
    # hr_attendance: _compute_overtime_from_attendance lee hr.attendance en cada
    #   cálculo de rol de pago.
    # l10n_ec_income_tax: _compute_income_tax_2026 usa l10n_ec.tax.table y
    #   l10n_ec.family.basket. La dependencia va en este sentido y no al revés; por
    #   eso el asistente de gastos personales vive ahora aquí y no allí (antes había
    #   un ciclo: income_tax escribía l10n_ec_projected_expenses, definido aquí).
    "depends": ["hr", "hr_attendance", "l10n_ec_income_tax"],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_ec_salary_rule_data.xml",
        "data/l10n_ec_payroll_data.xml",
        "report/form_107_template.xml",
        "views/hr_version_views.xml",
        # define menu_l10n_ec_payroll_root -> debe cargarse antes del wizard
        "views/l10n_ec_payslip_views.xml",
        "wizard/gastos_personales_wizard_view.xml",
    ],
    "installable": True,
    "application": False,
}
