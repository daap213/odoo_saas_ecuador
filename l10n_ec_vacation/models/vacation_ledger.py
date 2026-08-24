# -*- coding: utf-8 -*-
from odoo import models, fields, api
from dateutil.relativedelta import relativedelta


class L10nEcVacationLedger(models.Model):
    _name = "l10n_ec.vacation.ledger"
    _description = "Ecuadorian Vacation Ledger"
    _order = "date desc"

    employee_id = fields.Many2one("hr.employee", string="Employee", required=True)
    # Odoo 19: hr.contract desapareció; el equivalente es hr.version.
    contract_id = fields.Many2one("hr.version", string="Contract", required=True)

    date = fields.Date("Date", default=fields.Date.today, required=True)
    description = fields.Char("Description", required=True)

    # Ledger columns
    days_earned = fields.Float(
        "Days Earned (+)", default=0.0, help="Accrual (1.25/month + seniority)"
    )
    days_taken = fields.Float(
        "Days Taken (-)", default=0.0, help="Vacation days enjoyed"
    )
    days_paid = fields.Float(
        "Days Paid (-)", default=0.0, help="Liquidated days (cash)"
    )

    balance = fields.Float("Balance", compute="_compute_balance", store=True)

    @api.depends("employee_id")
    def _compute_balance(self):
        # Rolling balance calculation is tricky in stored compute without strict ordering.
        # For simplicity in V1, we verify balance per employee.
        # A better approach for Ledger is usually on-the-fly or sequential triggers.
        # Here we will just sum for the employee.
        for rec in self:
            domain = [("employee_id", "=", rec.employee_id.id)]
            ledgers = self.search(domain)
            earned = sum(l.days_earned for l in ledgers)
            taken = sum(l.days_taken for l in ledgers)
            paid = sum(l.days_paid for l in ledgers)
            rec.balance = earned - taken - paid

    @api.model
    def run_monthly_accrual(self, reference_date=None):
        """
        Scheduled Action to run accruals.
        Logic:
        1. Find active contracts.
        2. Calculate seniority (Years of service).
        3. Base = 1.25.
        4. If years > 5, add (years - 5) capped? No, logic is +1 day for every year after 5.
           Wait, Art 69 says "un día adicional por cada año excedente".
           It usually caps at 15 extra days (total 30), but law says "no excederá de 15".
           So Max Days = 15 (Base) + 15 (Seniority) = 30.
           Monthly portion of seniority = (Years - 5) / 12.
        """
        if not reference_date:
            reference_date = fields.Date.today()

        # Odoo 19: hr.version es un HISTÓRICO de versiones, no un registro por
        # empleado. Buscar directamente en hr.version por rango de fechas devuelve
        # todas las versiones vigentes del mismo empleado y generaría un devengo por
        # cada una. Hay que iterar empleados y quedarse con su versión vigente.
        #
        # `is_current` no sirve para filtrar: es computado, sin store y sin método
        # `search=`, así que no es usable en un dominio. Se filtra por fechas, que sí
        # están almacenadas. El sudo() es porque contract_date_* y version_id están
        # restringidos por grupo y esto corre desde un cron.
        employees = self.env["hr.employee"].sudo().search([])

        contracts = employees.mapped("version_id").filtered(
            lambda v: v.contract_date_start
            and v.contract_date_start <= reference_date
            and (not v.contract_date_end or v.contract_date_end >= reference_date)
        )

        for contract in contracts:
            # Check if accrual already ran for this month? (Omitted for MVP simplicity, would be a unique constraint)

            # 1. Base Accrual
            accrual = 1.25

            # 2. Seniority Bonus
            # Calculate seniority
            start_date = contract.contract_date_start
            # Service years
            delta = relativedelta(reference_date, start_date)
            years_service = delta.years

            seniority_days_yearly = 0.0
            if years_service > 5:
                extra_years = years_service - 5
                seniority_days_yearly = min(
                    extra_years, 15
                )  # Cap additional days at 15

            seniority_monthly = seniority_days_yearly / 12.0
            total_earned = accrual + seniority_monthly

            self.create(
                {
                    "employee_id": contract.employee_id.id,
                    "contract_id": contract.id,
                    "date": reference_date,
                    "description": f"Monthly Accrual ({reference_date.strftime('%B %Y')}) - Base: 1.25, Seniority: {seniority_monthly:.2f}",
                    "days_earned": total_earned,
                }
            )
