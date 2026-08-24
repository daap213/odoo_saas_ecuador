# -*- coding: utf-8 -*-
from odoo import models, fields, api


class L10nEcPayslip(models.Model):
    _inherit = "l10n_ec.payslip"

    # Add Loan Deduction Field
    loan_deduction = fields.Float(
        "IESS/Company Loans", compute="_compute_loans", store=True
    )

    @api.depends("employee_id", "date_start", "date_end")
    def _compute_loans(self):
        for rec in self:
            # Find unpaid loan installments due in this period
            installments = self.env["l10n_ec.loan.line"].search(
                [
                    ("loan_id.employee_id", "=", rec.employee_id.id),
                    ("loan_id.state", "=", "active"),
                    ("is_paid", "=", False),
                    ("date_due", ">=", rec.date_start),
                    ("date_due", "<=", rec.date_end),
                ]
            )
            total = sum(installments.mapped("amount"))
            rec.loan_deduction = total

    # Al sobrescribir un compute, el @api.depends nuevo REEMPLAZA al de la clase base:
    # hay que repetir las dependencias del padre y añadir la propia (loan_deduction).
    # Tampoco se listan total_income ni income_tax: los escribe este mismo método a
    # través de super(), así que dependerían de sí mismos.
    @api.depends(
        "wage",
        "commission",
        "bonus",
        "iess_personal",
        "total_benefits_cash",
        "advances",
        "loan_deduction",
    )
    def _compute_totals(self):
        # super() calcula total_income, income_tax y net_wage. Es obligatorio llamarlo:
        # total_income también declara compute="_compute_totals", y si este override no
        # lo asignara Odoo lanzaría "Compute method failed to assign total_income".
        super()._compute_totals()
        for rec in self:
            rec.net_wage -= rec.loan_deduction

    def action_confirm(self):
        # Mark installments as paid
        for rec in self:
            installments = self.env["l10n_ec.loan.line"].search(
                [
                    ("loan_id.employee_id", "=", rec.employee_id.id),
                    ("loan_id.state", "=", "active"),
                    ("is_paid", "=", False),
                    ("date_due", ">=", rec.date_start),
                    ("date_due", "<=", rec.date_end),
                ]
            )
            installments.write({"is_paid": True, "payslip_id": rec.id})

        return super(L10nEcPayslip, self).action_confirm()
