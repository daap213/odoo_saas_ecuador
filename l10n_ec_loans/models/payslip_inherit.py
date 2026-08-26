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

    # El padre partió `_compute_totals` en tres computes encadenados
    # (total_income -> income_tax -> net_wage) para romper un ciclo de dependencias.
    # Aquí sólo interesa el último: el préstamo es un descuento sobre el neto, no
    # afecta ni al ingreso gravable ni al IR.
    #
    # Al sobrescribir un compute, el @api.depends nuevo REEMPLAZA al del padre: hay
    # que repetir sus dependencias y añadir la propia.
    @api.depends(
        "total_income",
        "total_benefits_cash",
        "iess_personal",
        "income_tax",
        "advances",
        "loan_deduction",
    )
    def _compute_net_wage(self):
        super()._compute_net_wage()
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
