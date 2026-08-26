# -*- coding: utf-8 -*-
"""
SUT Report Generator - MDT Integration

Legal basis:
- Código Trabajo Art. 97-104: 15% Utilidades
  - 10% repartición directa (igual para todos)
  - 5% por cargas familiares
- Filing: April 15 each year
"""
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from collections import defaultdict


class L10nEcSutReportWizard(models.TransientModel):
    _name = "l10n_ec.sut.report.wizard"
    _description = "MDT SUT Report Generator"

    report_type = fields.Selection(
        [
            ("13th", "Décimo Tercero"),
            ("14th", "Décimo Cuarto"),
            ("utilidades", "Utilidades"),
        ],
        string="Report Type",
        required=True,
    )

    date_start = fields.Date("Start Date", required=True)
    date_end = fields.Date("End Date", required=True)

    # For utilidades - AUTO-CALCULATED from accounting P&L
    fiscal_year_profit = fields.Float(
        "Utilidad Neta del Ejercicio",
        compute="_compute_fiscal_profit",
        help="Auto-calculado desde cuentas de Ingresos - Gastos del período",
    )
    company_profit = fields.Float(
        "Utilidad a Repartir (15%)",
        compute="_compute_fiscal_profit",
        help="Código Trabajo Art. 97: 15% de utilidad neta, auto-calculado",
    )

    # Generated File
    filename = fields.Char("Filename")
    file_data = fields.Binary("Report File")

    @api.depends("date_start", "date_end")
    def _compute_fiscal_profit(self):
        """
        Auto-calculate company profit from accounting:
        - Income accounts (type: income, income_other)
        - Expense accounts (type: expense, expense_depreciation, expense_direct_cost)
        """
        for rec in self:
            if not rec.date_start or not rec.date_end:
                rec.fiscal_year_profit = 0.0
                rec.company_profit = 0.0
                continue

            # Get income and expense totals from account.move.line
            self.env.cr.execute(
                """
                SELECT
                    COALESCE(SUM(CASE WHEN aa.account_type IN ('income', 'income_other')
                             THEN -aml.balance ELSE 0 END), 0) as total_income,
                    COALESCE(SUM(CASE WHEN aa.account_type IN ('expense', 'expense_depreciation', 'expense_direct_cost')
                             THEN aml.balance ELSE 0 END), 0) as total_expense
                FROM account_move_line aml
                JOIN account_account aa ON aml.account_id = aa.id
                JOIN account_move am ON aml.move_id = am.id
                WHERE am.state = 'posted'
                  AND am.date >= %s AND am.date <= %s
                  AND am.company_id = %s
            """,
                (rec.date_start, rec.date_end, self.env.company.id),
            )

            result = self.env.cr.fetchone()
            total_income = result[0] if result else 0
            total_expense = result[1] if result else 0

            # Net profit = Income - Expenses
            net_profit = total_income - total_expense
            rec.fiscal_year_profit = max(net_profit, 0)  # Only distribute if profit
            rec.company_profit = (
                rec.fiscal_year_profit * 0.15
            )  # 15% per Código Trabajo Art. 97

    def action_generate(self):
        self.ensure_one()

        # 1. Fetch relevant Payslips
        domain = [
            ("state", "=", "done"),
            ("date_end", ">=", self.date_start),
            ("date_start", "<=", self.date_end),
        ]
        payslips = self.env["l10n_ec.payslip"].search(domain)

        if not payslips:
            raise UserError(_("No payslips found for the selected period."))

        content = ""

        if self.report_type == "13th":
            content = self._generate_13th_report(payslips)

        elif self.report_type == "14th":
            content = self._generate_14th_report(payslips)

        elif self.report_type == "utilidades":
            content = self._generate_utilidades_report(payslips)

        self.filename = f"SUT_{self.report_type}_{self.date_end}.txt"
        self.file_data = base64.b64encode(content.encode("utf-8"))

        return {
            "type": "ir.actions.act_window",
            "res_model": "l10n_ec.sut.report.wizard",
            "view_mode": "form",
            "res_id": self.id,
            "target": "new",
        }

    def _generate_13th_report(self, payslips):
        """Décimo Tercero report for SUT."""
        content = "Cedula,Nombres,Dias_Trabajados,Total_Ganado,Valor_Decimo\n"
        for p in payslips:
            content += f"{p.employee_id.identification_id},{p.employee_id.name},{p.days_worked},{p.total_income},{p.thirteenth}\n"
        return content

    def _generate_14th_report(self, payslips):
        """Décimo Cuarto report for SUT."""
        content = "Cedula,Nombres,Region,Dias_Trabajados,Valor_Decimo\n"
        for p in payslips:
            # `private_state_id`, no `address_home_id`: ese campo lo eliminó Odoo 17 y
            # la dirección particular del empleado pasó a campos `private_*` en el
            # propio `hr.employee`. Con el nombre viejo, este informe lanzaba
            # AttributeError en el primer empleado: nunca ha llegado a generarse.
            region = p.employee_id.private_state_id.name or "Sierra"
            # Sierra/Oriente: Sept 15, Costa/Galapagos: March 15
            content += f"{p.employee_id.identification_id},{p.employee_id.name},{region},{p.days_worked},{p.fourteenth}\n"
        return content

    def _generate_utilidades_report(self, payslips):
        """
        Utilidades report per Código Trabajo Art. 97-104.

        Distribution:
        - 10% equal distribution (Art. 100)
        - 5% by cargas familiares (Art. 101)

        Profit is AUTO-CALCULATED from accounting.
        """
        if self.company_profit <= 0:
            raise UserError(
                _(
                    "No hay utilidad a repartir. La utilidad neta del ejercicio es: $%.2f"
                )
                % self.fiscal_year_profit
            )

        # Calculate 10% (equal) and 5% (by cargas)
        total_profit = self.company_profit
        equal_portion = total_profit * (10 / 15)  # 10% of 15% = 2/3
        cargas_portion = total_profit * (5 / 15)  # 5% of 15% = 1/3

        # Aggregate by employee
        employee_data = defaultdict(
            lambda: {"name": "", "cedula": "", "days": 0, "cargas": 0}
        )

        for p in payslips:
            emp_id = p.employee_id.id
            employee_data[emp_id]["name"] = p.employee_id.name
            employee_data[emp_id]["cedula"] = p.employee_id.identification_id or ""
            employee_data[emp_id]["days"] += p.days_worked or 0
            # Get cargas familiares from employee or contract
            employee_data[emp_id]["cargas"] = (
                getattr(p.employee_id, "l10n_ec_family_loads", 0) or 0
            )

        total_days = sum(emp["days"] for emp in employee_data.values())
        total_cargas = sum(emp["cargas"] for emp in employee_data.values())

        # Calculate per employee
        content = "Cedula,Nombres,Dias_Trabajados,Cargas_Familiares,Utilidad_10pct,Utilidad_5pct,Total_Utilidad\n"

        for emp_id, emp in employee_data.items():
            # 10% portion: proportional to days worked
            if total_days > 0:
                utilidad_10 = (emp["days"] / total_days) * equal_portion
            else:
                utilidad_10 = 0

            # 5% portion: proportional to cargas
            if total_cargas > 0 and emp["cargas"] > 0:
                utilidad_5 = (emp["cargas"] / total_cargas) * cargas_portion
            else:
                utilidad_5 = 0

            total_util = utilidad_10 + utilidad_5

            content += (
                f"{emp['cedula']},"
                f"{emp['name']},"
                f"{emp['days']},"
                f"{emp['cargas']},"
                f"{utilidad_10:.2f},"
                f"{utilidad_5:.2f},"
                f"{total_util:.2f}\n"
            )

        return content
