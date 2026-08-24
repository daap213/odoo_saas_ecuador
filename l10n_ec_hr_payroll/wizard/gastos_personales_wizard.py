# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime


class L10nEcGastosPersonalesWizard(models.TransientModel):
    _name = "l10n_ec.gastos.personales.wizard"
    _description = "Formulario GP: Proyección Gastos Personales"

    def _default_employee(self):
        return self.env.user.employee_id

    employee_id = fields.Many2one(
        "hr.employee", string="Employee", required=True, default=_default_employee
    )
    year = fields.Integer(
        "Fiscal Year", required=True, default=lambda self: datetime.now().year
    )

    # Expense Categories (LORTI Art. 10)
    housing = fields.Float(
        "Vivienda", help="Rental checks, mortgage interest, property tax, utilities"
    )
    health = fields.Float(
        "Salud", help="Medical fees, medication, insurance, deductibles"
    )
    education = fields.Float(
        "Educación / Arte / Cultura", help="Tuition, supplies, art/culture classes"
    )
    food = fields.Float("Alimentación", help="Groceries, restaurants")
    clothing = fields.Float("Vestimenta", help="Clothing and footwear")
    tourism = fields.Float("Turismo Nacional", help="Registered local tourism expenses")

    total_projected = fields.Float(
        "Total Expenses", compute="_compute_total", store=True
    )

    @api.depends("housing", "health", "education", "food", "clothing", "tourism")
    def _compute_total(self):
        for rec in self:
            rec.total_projected = (
                rec.housing
                + rec.health
                + rec.education
                + rec.food
                + rec.clothing
                + rec.tourism
            )

    def action_apply_to_contract(self):
        self.ensure_one()
        # Odoo 19: hr.contract ya no existe y hr.version no tiene estado 'open'.
        # hr.employee._inherits = {'hr.version': 'version_id'}, así que escribir el
        # campo sobre el empleado lo delega a su versión de contrato vigente.
        employee = self.employee_id
        # OJO: no vale comprobar `employee.version_id` — es required=True, así que
        # siempre existe y la guarda nunca saltaría. Lo que hay que verificar es que
        # el empleado tenga de verdad un contrato vigente, y en Odoo 19 eso se mira
        # por fechas: hr.version no tiene campo `state`, e `is_current` es computado
        # sin `search=`, así que tampoco sirve en un dominio.
        today = fields.Date.context_today(self)
        version = employee.version_id
        started = version.contract_date_start and version.contract_date_start <= today
        not_ended = not version.contract_date_end or version.contract_date_end >= today
        if not (started and not_ended):
            raise UserError(
                _("El empleado %s no tiene un contrato vigente a fecha de hoy. "
                  "No se pueden actualizar los gastos proyectados.")
                % employee.name
            )

        employee.write({"l10n_ec_projected_expenses": self.total_projected})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Success"),
                "message": _("Projected expenses updated on contract ($%s)")
                % self.total_projected,
                "type": "success",
                "sticky": False,
            },
        }
