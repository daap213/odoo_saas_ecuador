# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import float_compare, float_is_zero

# Tabla 24 de la Ficha: la unidad de tiempo del plazo es texto libre acotado. El SRI
# sólo acepta estos tres valores en <unidadTiempo>.
TIME_UNITS = [
    ("dias", "Días"),
    ("meses", "Meses"),
    ("anios", "Años"),
]


class L10nEcMovePayment(models.Model):
    """Una forma de pago de un comprobante.

    El bloque <pagos> de la Ficha es REPETIBLE: una factura pagada mitad en efectivo
    y mitad con tarjeta lleva dos <pago>. Hasta ahora se emitía siempre uno solo por
    el total, con la forma de pago de la cabecera, lo que describe mal cualquier venta
    mixta — y el SRI no lo rechaza, así que el error viajaba silencioso hasta el ATS.

    Cuando este one2many está vacío se sigue emitiendo el pago único derivado de la
    cabecera; el modelo es la vía para el caso que no cabía, no un requisito nuevo.
    """

    _name = "l10n_ec.move.payment"
    _description = "Forma de pago SRI del comprobante"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    move_id = fields.Many2one(
        "account.move",
        string="Comprobante",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(related="move_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="move_id.currency_id")
    payment_method_id = fields.Many2one(
        "l10n_ec.payment.method",
        string="Forma de pago",
        required=True,
        help="Tabla 24 de la Ficha Técnica.",
    )
    amount = fields.Monetary(string="Importe", required=True)
    term_days = fields.Integer(
        string="Plazo",
        help="Obligatorio en venta a crédito. Se emite como <plazo>; 0 lo omite.",
    )
    time_unit = fields.Selection(
        TIME_UNITS, string="Unidad de tiempo", default="dias", required=True
    )

    @api.constrains("amount")
    def _check_amount_positive(self):
        for payment in self:
            if float_compare(
                payment.amount, 0.0, precision_rounding=payment.currency_id.rounding or 0.01
            ) <= 0:
                raise ValidationError(
                    _("El importe de la forma de pago '%s' debe ser mayor que cero.",
                      payment.payment_method_id.display_name)
                )

    @api.constrains("term_days")
    def _check_term_days(self):
        for payment in self:
            if payment.term_days < 0:
                raise ValidationError(_("El plazo no puede ser negativo."))


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ec_payment_ids = fields.One2many(
        "l10n_ec.move.payment",
        "move_id",
        string="Formas de pago SRI",
        copy=False,
        help="Déjelo vacío para emitir un único <pago> por el total del comprobante.",
    )

    l10n_ec_tip = fields.Monetary(
        string="Propina",
        compute="_compute_l10n_ec_tip",
        store=True,
        readonly=False,
        copy=False,
        help="Recargo del 10 %% por servicio. Va en <propina>, FUERA de la base "
             "imponible: el SRI valida importeTotal = base + impuestos + propina.",
    )

    l10n_ec_waybill_number = fields.Char(
        string="Guía de remisión",
        size=17,
        copy=False,
        help="Número de la guía con la que viajó la mercadería, formato "
             "001-001-000000001. Se emite en <guiaRemision>.",
    )

    @api.depends("invoice_line_ids.price_subtotal",
                 "invoice_line_ids.product_id.l10n_ec_is_tip")
    def _compute_l10n_ec_tip(self):
        """Suma de las líneas cuyo producto está marcado como propina.

        `store=True, readonly=False` para que el cálculo automático sirva de punto de
        partida y siga siendo corregible a mano: en restauración la propina la teclea
        el cajero tan a menudo como la trae el producto.
        """
        for move in self:
            move.l10n_ec_tip = sum(
                line.price_subtotal
                for line in move.invoice_line_ids
                if line.display_type == "product" and line.product_id.l10n_ec_is_tip
            )

    @api.constrains("l10n_ec_waybill_number")
    def _check_waybill_number(self):
        """001-001-000000001: 17 caracteres con guiones (Anexo 3).

        Distinto de `numDocSustento` de la retención, que son 15 SIN guiones. Los dos
        formatos conviven en la Ficha y confundirlos es un error 39 garantizado, así
        que cada uno se valida donde se usa.
        """
        for move in self:
            number = (move.l10n_ec_waybill_number or "").strip()
            if not number:
                continue
            parts = number.split("-")
            valid = (
                len(parts) == 3
                and [len(p) for p in parts] == [3, 3, 9]
                and all(p.isdigit() for p in parts)
            )
            if not valid:
                raise ValidationError(_(
                    "La guía de remisión '%s' no tiene el formato 001-001-000000001 "
                    "que exige el Anexo 3.", number,
                ))

    @api.constrains("l10n_ec_payment_ids", "amount_total")
    def _check_payment_lines_total(self):
        """Las formas de pago deben sumar el total.

        Si no cuadran, el SRI devuelve el error 52 ("valor total no coincide"). Vale
        más detenerlo aquí, donde se puede señalar la diferencia exacta, que descifrar
        después un código de rechazo.
        """
        for move in self:
            if not move.l10n_ec_payment_ids:
                continue
            rounding = move.currency_id.rounding or 0.01
            declared = sum(move.l10n_ec_payment_ids.mapped("amount"))
            if float_compare(declared, move.amount_total, precision_rounding=rounding):
                raise ValidationError(_(
                    "Las formas de pago de %(doc)s suman %(declared).2f y el "
                    "comprobante totaliza %(total).2f. El SRI rechaza la diferencia "
                    "con el error 52.",
                    doc=move.display_name, declared=declared, total=move.amount_total,
                ))

    def _l10n_ec_find_waybill(self):
        """Guía de remisión ya emitida para la mercadería de esta factura.

        Recorre factura → línea → línea de pedido → albaranes. Todo el camino va con
        `getattr` porque depende de `sale_stock`, que no está en las dependencias de
        este módulo: si no está instalado, no hay relación que seguir y el campo se
        queda vacío en vez de reventar.
        """
        self.ensure_one()
        pickings = self.env["stock.picking"].browse()
        for line in self.invoice_line_ids:
            for sale_line in getattr(line, "sale_line_ids", ()):
                order = getattr(sale_line, "order_id", None)
                if order is not None:
                    pickings |= getattr(order, "picking_ids", pickings)
        emitted = pickings.filtered(
            lambda p: getattr(p, "l10n_ec_sri_status", False) == "authorized"
            and getattr(p, "l10n_ec_guia_number", False)
        )
        return emitted[:1].l10n_ec_guia_number if emitted else False
