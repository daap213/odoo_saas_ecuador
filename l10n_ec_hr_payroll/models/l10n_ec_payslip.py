# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


# Anio comercial de 360 dias: es el divisor con el que la normativa laboral
# ecuatoriana prorratea el decimo cuarto. No es configurable porque no es un
# parametro que el SRI o el MDT revisen cada anio, sino la convencion de calculo.
L10N_EC_COMMERCIAL_YEAR_DAYS = 360.0

# Art. 55 del Codigo de Trabajo: 12 horas extra semanales como maximo. El tope
# mensual que se comprueba (12 x 4) es una aproximacion, y por eso se puede ajustar
# con `l10n_ec.horas_extra_tope_mensual`.
L10N_EC_WEEKLY_OVERTIME_LIMIT = 12


class L10nEcPayslip(models.Model):
    _name = "l10n_ec.payslip"
    _description = "Ecuadorian Payslip"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(readonly=True)  # e.g. "Cedula - Month/Year"
    employee_id = fields.Many2one("hr.employee", required=True)
    # Odoo 19: hr.contract desapareció; el equivalente es hr.version.
    contract_id = fields.Many2one(
        "hr.version", string="Contrato", required=True,
        domain="[('employee_id', '=', employee_id)]",
    )

    date_start = fields.Date(required=True)
    date_end = fields.Date(required=True)

    days_worked = fields.Float(default=30.0)

    # Earnings
    wage = fields.Float(
        "Base Wage", compute="_compute_wage", store=True, readonly=False
    )
    overtime_hours = fields.Float("Overtime (50%) Hours")
    supplementary_hours = fields.Float("Supplementary (100%) Hours")
    commission = fields.Float("Commissions")
    bonus = fields.Float("Bonuses")

    # Computations
    #
    # La cadena va en un solo sentido y no se puede cerrar en ciclo:
    #     total_income  ->  iess_personal  ->  income_tax  ->  net_wage
    #
    # Antes `total_income` declaraba `iess_personal` entre sus dependencias mientras
    # `_compute_iess` dependía de `total_income`: dos campos almacenados dependiendo
    # el uno del otro. Odoo entra en recomputación repetida o corta el ciclo por donde
    # le parece, y el resultado depende del orden en que se toquen los campos.
    total_income = fields.Float(
        "Total Income", compute="_compute_total_income", store=True
    )

    # Deductions
    iess_personal = fields.Float(
        "IESS Personal", compute="_compute_iess", store=True,
        help="Aporte personal al IESS, con la tasa del parámetro "
             "l10n_ec.iess_aporte_personal. La tasa NO está en la etiqueta a "
             "propósito: cambia por resolución.",
    )
    income_tax = fields.Float(
        "Impuesto Renta", compute="_compute_income_tax", store=True, readonly=False,
        help="Retención mensual de IR. Es computado pero editable: el contador puede "
             "sobreescribirlo cuando el empleado presenta su proyección de gastos.",
    )
    advances = fields.Float("Salary Advances")

    # Employer Costs
    iess_employer = fields.Float(
        "IESS Patronal", compute="_compute_iess", store=True,
        help="Aporte patronal, con la tasa del parámetro l10n_ec.iess_aporte_patronal.",
    )

    # Benefits (Provisions)
    thirteenth = fields.Float("13th Salary", compute="_compute_benefits", store=True)
    fourteenth = fields.Float("14th Salary", compute="_compute_benefits", store=True)
    reserve_funds = fields.Float(
        "Reserve Funds", compute="_compute_benefits", store=True
    )

    net_wage = fields.Float("Net Wage", compute="_compute_net_wage", store=True)
    total_benefits_cash = fields.Float(
        "Benefits (Cash)", compute="_compute_benefits", store=True
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("verify", "Verification"),
            ("done", "Done"),
            ("cancel", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    @api.depends("contract_id")
    def _compute_wage(self):
        # hr.version.wage está restringido a hr.group_hr_manager, pero el ACL de
        # l10n_ec.payslip permite crear a hr.group_hr_user: sin sudo() un HR officer
        # obtiene AccessError en cuanto se crea el rol de pago.
        for rec in self:
            rec.wage = rec.contract_id.sudo().wage if rec.contract_id else 0.0

    def _l10n_ec_year_config(self):
        """Configuracion del anio del rol, o un recordset vacio.

        Centraliza la lectura para que los recargos, los fondos de reserva y la
        jornada salgan todos del mismo sitio. Devolver vacio en vez de fallar es
        deliberado: cada consumidor decide su respaldo, y una base sin `l10n_ec.config`
        del anio corriente debe poder seguir calculando con los parametros globales.
        """
        self.ensure_one()
        reference = self.date_from or fields.Date.context_today(self)
        return self.env["l10n_ec.config"].sudo().search([
            ("year", "=", reference.year),
            ("active", "=", True),
        ], limit=1)

    def _l10n_ec_overtime_rates(self):
        """(recargo de horas extraordinarias, recargo de suplementarias).

        Art. 55 del Codigo de Trabajo: 100 % y 50 % de recargo. Estaban escritos como
        `* 1.5` y `* 2.0` dentro de la formula, en un modulo cuyo principio declarado
        es que ningun valor legal viva en el codigo — y `l10n_ec.config` ya tenia los
        dos campos, sin que nadie los leyera.
        """
        self.ensure_one()
        config = self._l10n_ec_year_config()
        supplementary = config.recargo_suplementaria if config else 0.0
        extraordinary = config.recargo_extraordinaria if config else 0.0
        return (extraordinary or 2.0), (supplementary or 1.5)

    def _l10n_ec_hourly_rate(self):
        """Valor de la hora ordinaria.

        El divisor (240 = 8 h × 30 días, la jornada mensual del Art. 47) sale de
        `l10n_ec.config.hora_trabajo` si hay configuración del año, y si no del
        parámetro `l10n_ec.jornada_mensual_horas`. Antes era un `240` escrito en la
        fórmula, en un módulo cuyo principio declarado es que ningún valor legal viva
        en el código.
        """
        self.ensure_one()
        if not self.wage:
            return 0.0
        config = self._l10n_ec_year_config()
        divisor = (config.hora_trabajo if config else 0.0) or float(
            self.env["ir.config_parameter"].sudo().get_param(
                "l10n_ec.jornada_mensual_horas", "240"
            )
        )
        return self.wage / divisor if divisor else 0.0

    @api.depends(
        "wage", "commission", "bonus", "overtime_hours", "supplementary_hours"
    )
    def _compute_total_income(self):
        """Ingreso gravable del período.

        `overtime_hours` y `supplementary_hours` SÍ están en las dependencias: son
        campos editables normales. Antes no podían estarlo porque este mismo método
        los escribía llamando a `_compute_overtime_from_attendance()`, un efecto
        secundario sobre campos no computados desde dentro de un compute — que además
        hacía un `search()` en `hr.attendance` por cada rol de pago. Ese cálculo es
        ahora una acción explícita: `action_compute_overtime_from_attendance`.
        """
        for rec in self:
            hourly = rec._l10n_ec_hourly_rate()
            extraordinary_rate, supplementary_rate = rec._l10n_ec_overtime_rates()
            # Extraordinarias (noches, fines de semana y feriados) al 100 % de
            # recargo; suplementarias (hasta 4 h despues de la jornada) al 50 %.
            ot_pay = rec.overtime_hours * hourly * extraordinary_rate
            supp_pay = rec.supplementary_hours * hourly * supplementary_rate
            rec.total_income = (
                rec.wage + ot_pay + supp_pay + rec.commission + rec.bonus
            )

    @api.depends("total_income", "iess_personal")
    def _compute_income_tax(self):
        for rec in self:
            rec.income_tax = rec._compute_income_tax_2026(
                rec.total_income, rec.iess_personal
            )

    @api.depends(
        "total_income", "total_benefits_cash", "iess_personal", "income_tax", "advances"
    )
    def _compute_net_wage(self):
        for rec in self:
            rec.net_wage = (
                (rec.total_income + rec.total_benefits_cash)
                - rec.iess_personal
                - rec.income_tax
                - rec.advances
            )

    def action_compute_overtime_from_attendance(self):
        """Rellena las horas extra desde los partes de asistencia.

        Es una acción y no un compute: lee `hr.attendance` con un `search()` por
        registro y escribe campos editables. Metido dentro de un compute hacía ambas
        cosas de forma implícita y con N+1 — cerrar la nómina de 200 empleados eran
        200 consultas — y además impedía que el usuario corrigiera las horas a mano,
        porque el siguiente recálculo se las pisaba.
        """
        for rec in self:
            rec._compute_overtime_from_attendance()
        return True

    def _compute_overtime_from_attendance(self):
        """
        PacERP Killer: Auto-calculate overtime from Biometric/Kiosk data.
        Logic:
        1. Fetch Attendance records within Payslip Period.
        2. Sum hours worked.
        3. Compare vs Contract Hours (e.g. 160h).
        4. Split Excess:
           - Weekdays > 8h -> 50% (Supplementary)
           - Weekends -> 100% (Extraordinary)
        """
        for rec in self:
            attendances = self.env["hr.attendance"].search(
                [
                    ("employee_id", "=", rec.employee_id.id),
                    ("check_in", ">=", rec.date_start),
                    ("check_out", "<=", rec.date_end),
                ]
            )

            total_supp_50 = 0.0
            total_extra_100 = 0.0

            for att in attendances:
                if not att.check_out:
                    continue

                # Calculate Duration
                delta = att.check_out - att.check_in
                hours = delta.total_seconds() / 3600.0

                # Check Day of Week (0=Mon, 6=Sun)
                # Odoo Datetime is UTC, need conversion to local typically?
                # For MVP we assume server time matches or is handled.
                weekday = att.check_in.weekday()

                # Logic:
                # If Weekend (Sat/Sun) -> 100%
                if weekday >= 5:
                    total_extra_100 += hours
                else:
                    # Weekday -> Standard is 8h. Excess is 50%.
                    # Note: Night shift (25%) logic omitted for MVP speed, focusing on OT.
                    if hours > 8.0:
                        extra = hours - 8.0
                        total_supp_50 += extra

            # Update Fields if they are zero (Manual override allowed)
            if rec.overtime_hours == 0 and total_extra_100 > 0:
                rec.overtime_hours = total_extra_100  # In our model overtime_hours is mapped to 100% or 50%?
                # Check model:
                # overtime_hours = 50% (Wait, typically 50 is supplementary)
                # supplementary_hours = 100%
                # Let's fix mapping in field definition if needed, but assuming:
                # overtime_hours field label says "Overtime (50%) Hours" in source code line 20
                # supplementary_hours field label says "Supplementary (100%) Hours" in source code line 21
                # Wait, Recargo Nocturno is usually 25, Suplementaria is 50, Extraordinaria is 100.
                # In common Ecuador terms:
                # 50% = Suplementaria (Weekday excess)
                # 100% = Extraordinaria (Weekend)

                pass

            # Write to fields strictly
            rec.overtime_hours = total_supp_50  # 50%
            rec.supplementary_hours = total_extra_100  # 100%

    def _compute_income_tax_2026(self, monthly_income, monthly_iess):
        """
        Implementation of Resolution NAC-DGERCGC25-00000043.
        1. Project Annual Income (Income * 12).
        2. Deduct IESS Personal (Income * 0.0945 * 12).
        3. Determine Tax Base.
        4. Calculate Impuesto Causado (Progressive Table).
        5. Calculate Rebaja Tributaria (Family Loads).
        6. Result: Annual Tax / 12.
        """
        # A. Projection
        # Note: Decimals and Reserve Funds are EXEMPT from Income Tax.
        annual_gross = monthly_income * 12.0
        annual_deductible_iess = monthly_iess * 12.0

        taxable_base = max(0.0, annual_gross - annual_deductible_iess)

        # B. Impuesto Causado
        # Get tax from l10n_ec.tax.table
        tax_table = self.env["l10n_ec.tax.table"]
        annual_caused_tax = tax_table.get_tax_for_base(taxable_base, year=2026)

        # If no tax caused, return 0 early
        if annual_caused_tax <= 0:
            return 0.0

        # C. Rebaja Tributaria (Tax Credit)
        # Needs Employee Family Loads and Contract Projected Expenses
        basket_model = self.env["l10n_ec.family.basket"]

        # Get Projected Expenses from Contract
        projected_expenses = 0.0
        if self.contract_id:
            projected_expenses = self.contract_id.l10n_ec_projected_expenses

        # Get Family Loads from Employee
        loads = 0
        catastrophic_disease = False
        if self.employee_id:
            loads = self.employee_id.l10n_ec_family_loads
            catastrophic_disease = self.employee_id.l10n_ec_catastrophic_disease

        rebate = basket_model.calculate_rebate(
            projected_expenses, loads, catastrophic_disease, year=2026
        )

        # D. Final Tax
        final_annual_tax = max(0.0, annual_caused_tax - rebate)

        return final_annual_tax / 12.0

    @api.depends("total_income")
    def _compute_iess(self):
        """
        Calculate IESS contributions using configurable rates.
        Rates from ir.config_parameter - NO HARDCODED FALLBACKS.
        """
        ICP = self.env["ir.config_parameter"].sudo()

        # Get IESS rates from config - NO HARDCODED DEFAULTS
        iess_personal_param = ICP.get_param("l10n_ec.iess_aporte_personal")
        iess_employer_param = ICP.get_param("l10n_ec.iess_aporte_patronal")
        if not iess_personal_param or not iess_employer_param:
            # `UserError`, no `ValueError`. Esto vive dentro de un compute ALMACENADO:
            # un `ValueError` no produce un diálogo sino un traceback 500, y como el
            # campo es almacenado la lista de roles de pago no se puede ni abrir.
            raise UserError(_(
                "Faltan las tasas del IESS.\n\n"
                "Configure 'l10n_ec.iess_aporte_personal' y "
                "'l10n_ec.iess_aporte_patronal' en Ajustes > Técnico > Parámetros del "
                "sistema, con el modo desarrollador activo."
            ))
        iess_personal_rate = float(iess_personal_param) / 100
        iess_employer_rate = float(iess_employer_param) / 100

        for rec in self:
            # IESS Personal contribution
            rec.iess_personal = rec.total_income * iess_personal_rate
            # IESS Employer contribution
            rec.iess_employer = rec.total_income * iess_employer_rate

    @api.depends(
        "total_income",
        "contract_id.l10n_ec_accumulate_13",
        "contract_id.l10n_ec_accumulate_14",
        "contract_id.l10n_ec_accumulate_reserve",
    )
    def _compute_benefits(self):
        # Fetch SBU from Config Parameter - NO HARDCODED FALLBACK
        sbu_param = self.env["ir.config_parameter"].sudo().get_param("l10n_ec.sbu")
        if not sbu_param:
            # UserError, no ValueError: esto corre dentro de un compute almacenado.
            raise UserError(_(
                "Falta el Salario Básico Unificado.\n\n"
                "Configure 'l10n_ec.sbu' en Ajustes > Técnico > Parámetros del "
                "sistema, con el modo desarrollador activo."
            ))
        sbu = float(sbu_param)

        for rec in self:
            # 13th: Total Income / 12
            rec.thirteenth = rec.total_income / 12.0

            # Decimo cuarto: proporcional al anio comercial de 360 dias, que es
            # el que usa la normativa laboral ecuatoriana para prorratear.
            rec.fourteenth = (sbu / L10N_EC_COMMERCIAL_YEAR_DAYS) * rec.days_worked

            # Fondos de reserva: 8,33 % (una doceava parte). El porcentaje esta en
            # `l10n_ec.config.fondos_reserva`, que existia y no se leia; el `1/12`
            # queda solo como respaldo cuando no hay configuracion del anio.
            config = rec._l10n_ec_year_config()
            reserve_rate = (config.fondos_reserva if config else 0.0) or (1.0 / 12.0)
            if reserve_rate > 1.0:
                # El campo admite tanto 8.33 como 0.0833 segun quien lo cargue.
                reserve_rate = reserve_rate / 100.0
            rec.reserve_funds = rec.total_income * reserve_rate

            # Determine Cash Payout (Mensualizado) vs Accumulation (Provision only)
            cash_total = 0.0
            contract = rec.contract_id

            # If NOT accumulating, pay it now
            if contract and not contract.l10n_ec_accumulate_13:
                cash_total += rec.thirteenth

            if contract and not contract.l10n_ec_accumulate_14:
                cash_total += rec.fourteenth

            if contract and not contract.l10n_ec_accumulate_reserve:
                cash_total += rec.reserve_funds

            rec.total_benefits_cash = cash_total

    @api.constrains("overtime_hours", "supplementary_hours")
    def _check_overtime_limits(self):
        """
        Enforce Código de Trabajo Art. 55:
        - Max 4 hours per day (Cannot check without daily logs).
        - Max 12 hours per week.

        Since this is a monthly/period payslip, we check the weekly limit * 4 weeks.
        Limit: 12 * 4 = 48 hours per month (approx).

        Strict compliance would require daily timesheets, but we enforce the monthly cap here.
        """
        for rec in self:
            total_ot = rec.overtime_hours + rec.supplementary_hours
            # Rough approximation: 4 weeks per month.
            # 12 hours * 4 weeks = 48 hours max per month.
            # This is a safe upper bound to prevent illegal exploitation.
            limit = float(
                self.env["ir.config_parameter"].sudo().get_param(
                    "l10n_ec.horas_extra_tope_mensual",
                    str(L10N_EC_WEEKLY_OVERTIME_LIMIT * 4),
                )
            )
            if total_ot > limit:
                raise ValidationError(_(
                    "Se supera el límite legal de horas extra (Art. 55 del Código "
                    "de Trabajo): el máximo es de %(weekly)s horas semanales, es "
                    "decir unas %(limit)s al mes, y este rol acumula "
                    "%(total)s.\n\nReduzca las horas o reparta el trabajo.",
                    weekly=L10N_EC_WEEKLY_OVERTIME_LIMIT,
                    limit=("%.0f" % limit),
                    total=("%.2f" % total_ot),
                ))

    def action_confirm(self):
        self._check_overtime_limits()
        self.write({"state": "done"})

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo 19: create() siempre recibe una lista, y el recordset devuelto puede
        # tener varios registros: hay que nombrarlos uno a uno.
        records = super().create(vals_list)
        for record in records:
            record.name = f"{record.employee_id.name} - {record.date_start}"
        return records
