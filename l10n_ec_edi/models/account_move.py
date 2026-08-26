# -*- coding: utf-8 -*-
import logging
from calendar import monthrange
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.l10n_ec_edi.models.access_key import AccessKey
import base64

_logger = logging.getLogger(__name__)

# =========================================================================
# SRI 2026 CONFIGURACIÓN
# Todos los valores regulatorios se leen de ir.config_parameter
# para permitir actualizaciones sin modificar código.
# NO HARDCODED DEFAULTS - System must be properly configured.
# =========================================================================


class AccountMove(models.Model):
    _inherit = "account.move"

    l10n_ec_sri_access_key = fields.Char(
        string="SRI Access Key", copy=False, help="49-digit Clave de Acceso"
    )
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Borrador"),
            ("signed", "Firmado"),
            ("sent", "Enviado"),
            ("authorized", "Autorizado"),
            ("rejected", "Devuelto (corregible)"),
            # Rechazo DEFINITIVO: el SRI evaluo el comprobante y lo nego. A
            # diferencia de un DEVUELTA en recepcion, aqui la clave de acceso ya
            # quedo registrada, asi que reenviarla devuelve el codigo 43 para
            # siempre. Sin este estado el ciclo era: NO AUTORIZADO -> rejected ->
            # el usuario reenvia -> 43 -> "ya lo tiene" -> sent -> el cron
            # consulta -> NO AUTORIZADO -> ... sin fin.
            ("rejected_final", "Rechazado definitivamente"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
        index=True,
    )
    l10n_ec_xml_data = fields.Binary("Signed XML", attachment=True, copy=False)

    # Único sitio donde mirar cuando algo falla ante el SRI. Se declara aquí, en la
    # capa base, porque tanto el auto-envío de `action_post` (este módulo) como
    # `action_send_sri` (l10n_ec_sri) tienen que escribirlo, y l10n_ec_edi no puede
    # depender de l10n_ec_sri.
    l10n_ec_sri_error = fields.Text(
        string="Mensaje del SRI", copy=False,
        help="Último motivo de rechazo o error de transmisión devuelto por el SRI.",
    )

    # OBSOLETO: lo sustituye l10n_ec_sri_error. Antes convivían los dos —el
    # auto-envío escribía este y la vista mostraba el otro—, así que un fallo al
    # publicar la factura quedaba invisible para el usuario. Se conserva declarado
    # para no perder el contenido histórico; ya no lo escribe nadie.
    l10n_ec_sri_response = fields.Text("SRI Response (obsoleto)", copy=False)

    # Reintento automático. Sólo tiene sentido para fallos de TRANSPORTE (el SRI no
    # respondió). Un rechazo real del SRI nunca se reintenta tal cual: §5.10 obliga a
    # corregir la inconsistencia y reenviar con la MISMA clave y secuencial, y eso
    # requiere intervención humana.
    l10n_ec_sri_retryable = fields.Boolean(
        string="Reintentable", copy=False,
        help="El último intento falló por no poder contactar con el SRI, no porque "
             "el comprobante fuera rechazado. El cron puede reintentarlo.",
    )
    l10n_ec_sri_retry_count = fields.Integer(
        string="Reintentos", default=0, copy=False,
        help="Tope para no golpear el servicio del SRI en bucle.",
    )

    # Ficha §4.7: entregar el comprobante al receptor por correo es obligación del
    # emisor. Este campo evita que la entrega automática se repita en cada pasada
    # del cron, sin impedir el reenvío manual.
    l10n_ec_sent_to_partner = fields.Boolean(
        string="Entregado al cliente", copy=False, readonly=True,
        help="El comprobante autorizado ya se envió por correo al receptor.",
    )

    l10n_ec_payment_method_id = fields.Many2one(
        "l10n_ec.payment.method",
        string="Forma de Pago SRI",
        help="Tabla 24 de la Ficha Técnica. Alimenta el bloque <pagos>, que es "
             "obligatorio en el comprobante. Si se deja vacío se usa el parámetro "
             "l10n_ec.default_payment_method_code.",
    )

    # Purchses Extensions (ATS)
    l10n_ec_sustento_code = fields.Selection(
        [
            ("01", "01 - Crédito Tributario para IVA"),
            ("02", "02 - Costo o Gasto"),
            ("03", "03 - Activo Fijo"),
            ("04", "04 - Liquidación Gastos"),
            ("05", "05 - Liquidación Reembolsos"),
            ("06", "06 - Sin Crédito Tributario"),
            ("07", "07 - Pagos Reembolsos"),
        ],
        string="Sustento Tributario",
        help="SRI code explaining the purchase purpose (ATS)",
    )

    # =========================================================================
    # SRI 2026 REGULATORY VALIDATIONS
    # =========================================================================

    def _get_cf_ruc(self):
        """Retorna el RUC de Consumidor Final desde configuración."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.consumidor_final_ruc")
        )
        if not param:
            raise ValidationError(
                _(
                    "Missing configuration: l10n_ec.consumidor_final_ruc\n"
                    "Please install l10n_ec module or configure System Parameters."
                )
            )
        return param

    def _get_cf_limit(self):
        """Retorna el límite de factura CF desde configuración."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.consumidor_final_limit")
        )
        if not param:
            raise ValidationError(
                _(
                    "Missing configuration: l10n_ec.consumidor_final_limit\n"
                    "Please install l10n_ec module or configure System Parameters."
                )
            )
        return float(param)

    def _get_annulment_day(self):
        """Retorna el día límite para anulación desde configuración."""
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_ec.annulment_day_limit")
        )
        if not param:
            raise ValidationError(
                _(
                    "Missing configuration: l10n_ec.annulment_day_limit\n"
                    "Please install l10n_ec module or configure System Parameters."
                )
            )
        return int(param)

    @api.constrains("amount_total", "partner_id", "move_type")
    def _check_consumidor_final_limit(self):
        """
        SRI 2026 Rule: Consumidor Final invoices cannot exceed configured limit.
        Resolution NAC-DGERCGC25-00000017
        Default limit: $50 USD (configurable via l10n_ec.consumidor_final_limit)
        """
        for move in self:
            if move.move_type not in ("out_invoice", "out_refund"):
                continue

            cf_ruc = move._get_cf_ruc()
            cf_limit = move._get_cf_limit()

            if move.partner_id and move.partner_id.vat == cf_ruc:
                if move.amount_total > cf_limit:
                    raise ValidationError(
                        _(
                            "Regulación SRI 2026: Facturas a Consumidor Final (%s) "
                            "no pueden superar $%.2f USD.\n"
                            "Total actual: $%.2f"
                        )
                        % (cf_ruc, cf_limit, move.amount_total)
                    )

    def _l10n_ec_get_annulment_deadline(self, emission_date):
        """Fecha límite de anulación: día N del mes siguiente al de emisión.

        El día N sale de `l10n_ec.annulment_day_limit`, no de un literal: antes este
        método y `_check_cancellation_allowed` calculaban el mismo plazo por separado
        y sólo uno leía la configuración, así que cambiar el parámetro no cambiaba el
        comportamiento del constraint.

        El día se recorta al último del mes destino, porque un parámetro de 30 o 31
        haría reventar `date()` en los meses cortos.
        """
        annulment_day = self._get_annulment_day()
        year = emission_date.year + 1 if emission_date.month == 12 else emission_date.year
        month = 1 if emission_date.month == 12 else emission_date.month + 1
        return date(year, month, min(annulment_day, monthrange(year, month)[1]))

    @api.constrains("state")
    def _check_annulment_deadline(self):
        """Una factura autorizada sólo puede anularse hasta el día límite.

        Res. NAC-DGERCGC25-00000017.
        """
        for move in self:
            if move.state == "cancel" and move.l10n_ec_sri_status == "authorized":
                if move.invoice_date:
                    emission_date = move.invoice_date
                    today = date.today()
                    deadline = move._l10n_ec_get_annulment_deadline(emission_date)

                    if today > deadline:
                        raise ValidationError(
                            _(
                                "SRI 2026 (Res. NAC-DGERCGC25-00000017): "
                                "No se puede anular esta factura autorizada.\n\n"
                                "Fecha de emisión: %s\n"
                                "Fecha límite de anulación: %s\n"
                                "Fecha actual: %s"
                            )
                            % (emission_date, deadline, today)
                        )

    # 2026 Mandate: No cancellation of Consumidor Final
    def button_cancel_sri(self):
        """Cancel invoice with SRI 2026 validations."""
        for move in self:
            if move.l10n_ec_sri_status == "authorized":
                # Check for Consumidor Final Rule - use configurable RUC
                cf_ruc = move._get_cf_ruc()
                if move.partner_id.vat == cf_ruc:
                    raise UserError(
                        _(
                            "SRI 2026: Facturas autorizadas a Consumidor Final (%s) "
                            "no pueden ser anuladas."
                        )
                        % cf_ruc
                    )

                # Check annulment deadline
                move._check_cancellation_allowed()

        return super(AccountMove, self).button_cancel()

    def _check_cancellation_allowed(self):
        """Valida el plazo de anulación: día N del mes siguiente al de emisión."""
        self.ensure_one()

        if not self.invoice_date:
            return True

        annulment_day = self._get_annulment_day()
        today = date.today()
        emission = self.invoice_date
        deadline = self._l10n_ec_get_annulment_deadline(emission)

        if today > deadline:
            raise ValidationError(
                _(
                    "SRI 2026: No se puede anular.\n\n"
                    "Fecha límite: día %s del mes siguiente.\n"
                    "Emisión: %s | Límite: %s | Hoy: %s"
                )
                % (annulment_day, emission, deadline, today)
            )

        return True

    # =========================================================================
    # AUTO-SEND TO SRI ON POST (2026 IMMEDIATE TRANSMISSION REQUIREMENT)
    # =========================================================================

    def action_post(self):
        """
        Override to auto-send to SRI when configured.

        SRI 2026 (Res. NAC-DGERCGC25-00000017):
        Transmisión INMEDIATA de comprobantes electrónicos.
        """
        result = super(AccountMove, self).action_post()
        self._l10n_ec_auto_send_to_sri()
        return result

    def _l10n_ec_auto_send_to_sri(self):
        """Transmite al SRI al publicar, si el parametro lo pide.

        Tres correcciones sobre la version anterior, todas del mismo tipo: un fallo
        aqui NO debe dejar la factura publicada, sin enviar y sin que nada vuelva a
        intentarlo.

        1. **Savepoint.** El `except` capturaba cualquier excepcion y a continuacion
           escribia en el registro. Si la excepcion venia de la base de datos, el
           cursor quedaba abortado y ese `write` reventaba tambien, tumbando el
           `action_post` entero: publicar una factura fallaba por un problema de red.
        2. **Estado 'rejected' y `retryable`.** Se dejaba en 'draft', y las dos colas
           del cron filtran 'sent' y 'rejected'. Un fallo de red al publicar
           significaba que nadie volvia a intentarlo jamas.
        3. **Sin certificado no es "saltar en silencio".** Queda escrito en el
           comprobante, que es donde el usuario lo va a buscar.
        """
        auto_send = (
            self.env["ir.config_parameter"].sudo()
            .get_param("l10n_ec.auto_send_sri", "False")
        )
        if auto_send.lower() not in ("true", "1", "yes"):
            return

        for move in self:
            if move.company_id.country_id.code != "EC":
                continue
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            if not hasattr(move, "action_send_sri"):
                continue

            certificate = move.company_id.l10n_ec_certificate_id
            if not certificate or certificate.state != "active":
                _logger.warning(
                    "Envio automatico al SRI omitido en %s: no hay certificado activo",
                    move.name,
                )
                move.l10n_ec_sri_error = _(
                    "El envio automatico se omitio: la compania no tiene un "
                    "certificado de firma activo."
                )
                move.l10n_ec_sri_retryable = True
                continue

            # El savepoint acota el fallo: si algo revienta, se deshace SOLO el
            # intento de envio y el cursor queda utilizable para dejar constancia.
            try:
                with self.env.cr.savepoint():
                    move.action_send_sri()
            except Exception as error:
                _logger.exception("Envio automatico al SRI fallido en %s", move.name)
                move.l10n_ec_sri_error = _(
                    "El envio automatico al SRI fallo al publicar:\n\n%s", error
                )
                # 'rejected' + retryable para que el cron lo recoja. En 'draft' no
                # entra en ninguna de sus dos colas.
                if move.l10n_ec_sri_status in (False, "draft"):
                    move.l10n_ec_sri_status = "rejected"
                    move.l10n_ec_sri_retryable = True
