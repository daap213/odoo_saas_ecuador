# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Página "Ecuador — SRI" en los ajustes de Contabilidad.

Todos los valores regulatorios del proyecto viven en `ir.config_parameter` (principio
"todo configurable, nada hardcodeado"), pero hasta ahora sólo se podían tocar en
Ajustes > Técnico > Parámetros del sistema, que exige modo desarrollador. En la
práctica eso significaba que nadie los configuraba: el RUC del proveedor de software
que exige el Anexo 26, por ejemplo, se quedaba vacío y la etiqueta no se emitía.

Aquí se exponen con nombres y ayudas en español, en el sitio donde un contador los
busca. Los campos con `config_parameter=` los lee y escribe Odoo solo; los `related`
apuntan a la compañía activa.
"""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # El ambiente y el certificado son campos de `res.company` que declara
    # `l10n_ec_edi`, no este módulo: se añaden en
    # `l10n_ec_edi/models/res_config_settings.py`. Aquí sólo van los parámetros del
    # sistema, que `l10n_ec_base` sí siembra.

    # ── Emisión electrónica ───────────────────────────────────────────────────
    l10n_ec_auto_send_sri = fields.Boolean(
        string="Enviar al SRI al validar",
        config_parameter="l10n_ec.auto_send_sri",
        help="Transmite el comprobante en cuanto se publica el asiento. Un fallo de "
             "envío se registra pero NO bloquea la contabilización.",
    )

    # Anexo 26 / Res. NAC-DGERCGC26-00000027 art. 5.
    l10n_ec_software_provider_ruc = fields.Char(
        string="RUC del proveedor de facturación",
        config_parameter="l10n_ec.software_provider_ruc",
        help="Obligatorio para quien emite con un sistema de terceros. Viaja como "
             "<campoAdicional nombre=\"RUC Proveedor\"> en la información adicional "
             "de cada comprobante. Vacío = no se emite la etiqueta.",
    )

    # ── Identificación del adquirente ─────────────────────────────────────────
    l10n_ec_consumidor_final_ruc = fields.Char(
        string="Identificación de consumidor final",
        config_parameter="l10n_ec.consumidor_final_ruc",
    )
    l10n_ec_consumidor_final_limit = fields.Float(
        string="Límite de consumidor final (USD)",
        config_parameter="l10n_ec.consumidor_final_limit",
        help="Por encima de este importe hay que identificar al adquirente "
             "(Ficha §9.10).",
    )

    # ── Plazos ────────────────────────────────────────────────────────────────
    l10n_ec_annulment_day_limit = fields.Integer(
        string="Día límite de anulación",
        config_parameter="l10n_ec.annulment_day_limit",
        help="Día del MES SIGUIENTE hasta el que se puede anular un comprobante "
             "autorizado. Si el mes destino es más corto, se recorta a su último día.",
    )

    # ── Tarifas ───────────────────────────────────────────────────────────────
    l10n_ec_iva_rate = fields.Float(
        string="IVA general (%)",
        config_parameter="l10n_ec.iva_rate",
    )
    l10n_ec_iva_rate_construccion = fields.Float(
        string="IVA construcción (%)",
        config_parameter="l10n_ec.iva_rate_construccion",
    )

    # ── Forma de pago por defecto ─────────────────────────────────────────────
    #
    # Se guarda el CÓDIGO de la tabla 24, no el id, porque es lo que va en
    # <formaPago>. El Many2one existe sólo para que en la interfaz sea un
    # desplegable con los nombres del catálogo y no un código a ciegas.
    l10n_ec_default_payment_method_id = fields.Many2one(
        "l10n_ec.payment.method",
        string="Forma de pago por defecto",
        compute="_compute_l10n_ec_default_payment_method_id",
        inverse="_inverse_l10n_ec_default_payment_method_id",
        readonly=False,
        store=False,
        help="Se usa cuando la factura no indica una forma de pago concreta.",
    )

    # ── URLs (avanzado) ───────────────────────────────────────────────────────
    l10n_ec_sri_reception_url_test = fields.Char(
        string="Recepción (pruebas)",
        config_parameter="l10n_ec.sri_reception_url_test",
    )
    l10n_ec_sri_authorization_url_test = fields.Char(
        string="Autorización (pruebas)",
        config_parameter="l10n_ec.sri_authorization_url_test",
    )
    l10n_ec_sri_reception_url_prod = fields.Char(
        string="Recepción (producción)",
        config_parameter="l10n_ec.sri_reception_url_prod",
    )
    l10n_ec_sri_authorization_url_prod = fields.Char(
        string="Autorización (producción)",
        config_parameter="l10n_ec.sri_authorization_url_prod",
    )
    l10n_ec_sri_ruc_api_url = fields.Char(
        string="API de consulta de RUC",
        config_parameter="l10n_ec.sri_ruc_api_url",
    )

    # ── Compras: DE 045-2025 ──────────────────────────────────────────────────
    #
    # Estaban declarados en `purchase_order.py` sin ninguna vista que los mostrara,
    # así que eran inalcanzables. Viven aquí para que se puedan configurar.
    l10n_ec_penalty_rate_daily = fields.Float(
        string="Penalidad diaria por retraso (%)",
        config_parameter="l10n_ec.penalty_rate_daily",
        help="DE 045-2025: tasa de penalidad por cada día de retraso en la entrega.",
    )
    l10n_ec_penalty_cap_percent = fields.Float(
        string="Tope de penalidad (%)",
        config_parameter="l10n_ec.penalty_cap_percent",
        help="DE 045-2025: porcentaje máximo de penalidad sobre el total del pedido.",
    )

    # ── Forma de pago: código <-> registro ────────────────────────────────────

    @api.depends_context("company")
    def _compute_l10n_ec_default_payment_method_id(self):
        code = self.env["ir.config_parameter"].sudo().get_param(
            "l10n_ec.default_payment_method_code"
        )
        method = self.env["l10n_ec.payment.method"].search(
            [("code", "=", code)], limit=1
        ) if code else self.env["l10n_ec.payment.method"]
        for record in self:
            record.l10n_ec_default_payment_method_id = method

    def _inverse_l10n_ec_default_payment_method_id(self):
        for record in self:
            self.env["ir.config_parameter"].sudo().set_param(
                "l10n_ec.default_payment_method_code",
                record.l10n_ec_default_payment_method_id.code or "",
            )

    # ── Validación ────────────────────────────────────────────────────────────

    @api.constrains("l10n_ec_software_provider_ruc")
    def _check_l10n_ec_software_provider_ruc(self):
        """El RUC del proveedor viaja al SRI: si se rellena, que sea un RUC.

        Vacío es válido — significa "no emitir la etiqueta" —, pero un valor con
        letras o con longitud equivocada sólo se descubriría como rechazo del SRI.
        """
        for record in self:
            ruc = (record.l10n_ec_software_provider_ruc or "").strip()
            if ruc and (not ruc.isdigit() or len(ruc) != 13):
                raise ValidationError(_(
                    "El RUC del proveedor de facturación debe tener 13 dígitos "
                    "numéricos (recibido: '%s').", ruc
                ))
