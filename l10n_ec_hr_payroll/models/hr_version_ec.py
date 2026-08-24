from odoo import models, fields


class HrVersion(models.Model):
    # Odoo 19 eliminó el módulo hr_contract: los datos contractuales viven ahora en
    # hr.version, dentro de hr, y hr.employee los expone por delegación
    # (_inherits = {'hr.version': 'version_id'}).
    _inherit = "hr.version"

    l10n_ec_regime = fields.Selection(
        [
            ("general", "General"),
            ("construction", "Construction"),
            ("agriculture", "Agriculture"),
            ("part_time", "Part Time"),
        ],
        string="IESS Regime",
        default="general",
        required=True,
    )

    l10n_ec_accumulate_13 = fields.Boolean("Accumulate 13th Salary", default=False)
    l10n_ec_accumulate_14 = fields.Boolean("Accumulate 14th Salary", default=False)
    l10n_ec_accumulate_reserve = fields.Boolean(
        "Accumulate Reserve Funds", default=True
    )

    # SRI Projections
    l10n_ec_projected_expenses = fields.Float(
        "Projected Personal Expenses (SRI Encuesta)"
    )

    # Jubilación Patronal (Employer Retirement)
    l10n_ec_jubilacion_patronal = fields.Boolean(
        "Apply Jubilación Patronal",
        default=False,
        help="Check if this employee is eligible for Employer Retirement provision (usually >10 years).",
    )
    l10n_ec_jubilacion_accumulated = fields.Float(
        "Accumulated Jubilación Liability",
        help="Total actuarial calculation of liability to date.",
    )
