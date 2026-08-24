# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager


class L10nEcPortal(CustomerPortal):

    # Los roles de pago y los préstamos son datos de RR.HH.: ni el usuario portal ni
    # un empleado corriente tienen ACL sobre l10n_ec.payslip / l10n_ec.loan. Se leen
    # en sudo() y la propiedad se garantiza SIEMPRE con ('employee_id', '=', employee.id)
    # en el dominio, nunca filtrando después.
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        employee = request.env.user.employee_id
        if "payslip_count" in counters:
            values["payslip_count"] = (
                request.env["l10n_ec.payslip"].sudo().search_count(
                    [("employee_id", "=", employee.id), ("state", "=", "done")]
                )
                if employee
                else 0
            )
        if "loan_count" in counters:
            values["loan_count"] = (
                request.env["l10n_ec.loan"].sudo().search_count(
                    [("employee_id", "=", employee.id)]
                )
                if employee
                else 0
            )
        return values

    # ------------------------------------------------------------
    # My Payslips
    # ------------------------------------------------------------
    @http.route(
        ["/my/payslips", "/my/payslips/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_payslips(
        self, page=1, date_begin=None, date_end=None, sortby=None, **kw
    ):
        values = self._prepare_portal_layout_values()
        employee = request.env.user.employee_id
        if not employee:
            return request.redirect("/my")

        Payslip = request.env["l10n_ec.payslip"].sudo()
        domain = [("employee_id", "=", employee.id), ("state", "=", "done")]

        payslip_count = Payslip.search_count(domain)
        pager = portal_pager(
            url="/my/payslips",
            url_args={"date_begin": date_begin, "date_end": date_end},
            total=payslip_count,
            page=page,
            step=10,
        )

        payslips = Payslip.search(
            domain, order="date_end desc", limit=10, offset=pager["offset"]
        )
        request.session["my_payslips_history"] = payslips.ids[:100]

        values.update(
            {
                "payslips": payslips,
                "page_name": "payslip",
                "pager": pager,
                "default_url": "/my/payslips",
            }
        )
        return request.render("l10n_ec_portal.portal_my_payslips", values)

    @http.route(
        ["/my/payslips/<int:payslip_id>"], type="http", auth="user", website=True
    )
    def portal_my_payslip_detail(self, payslip_id, **kw):
        employee = request.env.user.employee_id
        if not employee:
            return request.redirect("/my")

        # sudo() para poder leerlo, .exists() por si el id no existe, y comprobación
        # de propiedad ANTES de renderizar nada.
        payslip = request.env["l10n_ec.payslip"].sudo().browse(payslip_id).exists()
        if not payslip or payslip.employee_id != employee:
            return request.redirect("/my")

        values = {
            "payslip": payslip,
            "page_name": "payslip",
        }
        return request.render("l10n_ec_portal.portal_my_payslip_detail", values)

    # ------------------------------------------------------------
    # My Loans
    # ------------------------------------------------------------
    @http.route(
        ["/my/loans", "/my/loans/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_loans(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        employee = request.env.user.employee_id
        if not employee:
            return request.redirect("/my")

        Loan = request.env["l10n_ec.loan"].sudo()
        domain = [("employee_id", "=", employee.id)]

        loan_count = Loan.search_count(domain)
        pager = portal_pager(url="/my/loans", total=loan_count, page=page, step=10)

        loans = Loan.search(
            domain, order="date_start desc", limit=10, offset=pager["offset"]
        )
        values.update(
            {
                "loans": loans,
                "page_name": "loan",
                "pager": pager,
                "default_url": "/my/loans",
            }
        )
        return request.render("l10n_ec_portal.portal_my_loans", values)
