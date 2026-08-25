# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def l10n_ec_run_isolated(records, method_name):
    """Ejecuta `method_name` registro a registro, aislando los fallos.

    Cada iteración va en su propio savepoint: si una revienta se deshace sólo su
    parte y la cola continúa. Sin esto, un comprobante con datos incompletos abortaba
    la ejecución entera del cron y ninguno de los siguientes se procesaba.

    Es una función de módulo y no un método porque la usan dos modelos distintos
    (`account.move` y `l10n_ec.retention`) y no comparten herencia.
    """
    processed = 0
    for record in records:
        try:
            with record.env.cr.savepoint():
                getattr(record, method_name)()
            processed += 1
        except Exception as exc:  # noqa: BLE001 — el cron nunca debe caerse
            _logger.warning(
                "SRI: %s falló sobre %s: %s", method_name, record.display_name, exc
            )
    return processed


class AccountMove(models.Model):
    """
    Extends account.move with SRI integration logic.
    Field definitions inherited from l10n_ec_edi.

    Note: 2026 Consumidor Final validations are handled by l10n_ec_edi module.
    """

    _inherit = "account.move"

    # Additional fields not in l10n_ec_edi
    l10n_ec_authorization_date = fields.Datetime(
        string="Authorization Date", copy=False
    )
    # `l10n_ec_sri_error` se declara en l10n_ec_edi: lo escriben los dos módulos.

    def action_send_sri(self):
        """Genera clave, XML, firma y transmite al SRI."""
        for move in self:
            if move.l10n_ec_sri_status in ["authorized", "sent"]:
                continue

            if move.state != "posted":
                raise UserError(_(
                    "El comprobante %s debe estar publicado antes de enviarlo al SRI.",
                    move.display_name,
                ))

            # 0. Requisitos, todos de una vez y ANTES de generar la clave de acceso:
            #    si el envío va a fallar, que no se gaste un secuencial en el intento.
            #    Aquí sí se exige el certificado, porque este flujo firma.
            sri_xml = self.env["l10n_ec.sri.xml"]
            sri_xml._check_document_type_supported(move)
            sri_xml._check_emission_requirements(move, require_certificate=True)

            # 1. Clave de acceso. Se genera UNA sola vez y se conserva: la Ficha
            #    (§5.10) exige que un reenvío use la misma clave y el mismo
            #    secuencial. Regenerarla duplicaría el comprobante en el SRI.
            if not move.l10n_ec_sri_access_key:
                move.l10n_ec_sri_access_key = self.env[
                    "l10n_ec.sri.xml"
                ].generate_access_key(move)

            # 2. XML (ya incluye el prólogo UTF-8)
            xml_content = self.env["l10n_ec.sri.xml"].render_xml(move)
            if not isinstance(xml_content, bytes):
                xml_content = xml_content.encode("utf-8")

            # 3. Firma
            signed_xml = self._sign_xml(xml_content)
            move.l10n_ec_xml_data = base64.b64encode(signed_xml)

            # 4. Envío, con la compañía del documento (no env.company: en
            #    multiempresa eso podía enviar al ambiente de otra).
            response = self.env["l10n_ec.sri.service"].send_document(
                move.company_id, signed_xml
            )
            move._l10n_ec_apply_reception_response(response)

    def _l10n_ec_apply_reception_response(self, response):
        """Traduce la respuesta de recepción a un estado del comprobante.

        Matiz que antes faltaba y que causaba duplicados: un DEVUELTA con el
        identificador 43 ("clave de acceso registrada") o 70 ("clave de acceso en
        procesamiento") NO es un rechazo — significa que el comprobante YA está en
        el SRI. La Ficha (§11 nota 2) prohíbe expresamente reenviarlo o regenerarlo
        con otra clave hasta tener respuesta, hasta 24 horas.
        """
        self.ensure_one()
        status = response.get("status")
        messages = response.get("messages", [])

        if status == "RECIBIDA":
            self.l10n_ec_sri_status = "sent"
            self.l10n_ec_sri_error = False
            self.l10n_ec_sri_retryable = False
            return

        already_at_sri = {"43", "70"} & set(response.get("identifiers", []))
        if already_at_sri:
            self.l10n_ec_sri_status = "sent"
            self.l10n_ec_sri_retryable = False
            self.l10n_ec_sri_error = _(
                "El SRI ya tiene este comprobante (código %s). No se reenvía: se "
                "consultará su autorización.", ", ".join(sorted(already_at_sri))
            )
            return

        self.l10n_ec_sri_status = "rejected"
        self.l10n_ec_sri_error = "\n".join(messages) or status

        # Un fallo de transporte se distingue por no traer identificadores de mensaje
        # del SRI: nadie al otro lado evaluó el comprobante. Eso sí se reintenta; un
        # DEVUELTA con identificadores es un rechazo de contenido y no.
        self.l10n_ec_sri_retryable = (
            status == "ERROR" and not response.get("identifiers")
        )

    def action_check_sri(self):
        """
        Ping Check Status service (Real Implementation)
        """
        for move in self:
            if not move.l10n_ec_sri_access_key:
                raise UserError(_("No Access Key generated yet."))

            response = self.env["l10n_ec.sri.service"].check_authorization(
                move.company_id, move.l10n_ec_sri_access_key
            )
            status = response.get("status")

            if status == "AUTORIZADO":
                move.l10n_ec_sri_status = "authorized"
                move.l10n_ec_sri_error = False
                if response.get("date"):
                    from datetime import timezone as _tz
                    d = response["date"]
                    if hasattr(d, "tzinfo") and d.tzinfo is not None:
                        d = d.astimezone(_tz.utc).replace(tzinfo=None)
                    move.l10n_ec_authorization_date = d

                # La clave del servicio es "xml"; antes se leía "authorized_xml", que
                # no existe, así que el comprobante autorizado no se guardaba nunca.
                if response.get("xml"):
                    move.l10n_ec_xml_data = base64.b64encode(
                        response["xml"].encode("utf-8")
                    )

                # §4.7: entregar al receptor. Después de guardar el XML autorizado,
                # que es uno de los dos adjuntos.
                move._l10n_ec_try_send_to_customer()
            elif status in ("NO AUTORIZADO", "RECHAZADO"):
                move.l10n_ec_sri_status = "rejected"
                move.l10n_ec_sri_error = "\n".join(response.get("messages", []))
            else:
                # EN PROCESO / PPR / PENDING / ERROR: el SRI puede tardar hasta 24 h
                # (§7.5). Antes se ignoraban en silencio y el usuario no sabía nada.
                move.l10n_ec_sri_error = _(
                    "Estado en el SRI: %s. %s",
                    status or _("sin respuesta"),
                    " ".join(response.get("messages", [])),
                )

    def _sign_xml(self, xml_content):
        """
        Internal helper to call the signer lib.
        """
        self.ensure_one()
        certificate = self.company_id.l10n_ec_certificate_id
        if not certificate:
            raise UserError(_("No active Electronic Signature found for this company."))

        return certificate.sign_xml(xml_content)

    def _l10n_ec_get_ride_values(self):
        """Valores del RIDE. Lo llama la plantilla QWeb del informe."""
        self.ensure_one()
        return self.env["l10n_ec.sri.xml"].get_ride_values(self)

    # ------------------------------------------------------------------
    # Entrega al receptor (§4.7)
    # ------------------------------------------------------------------

    def action_l10n_ec_send_to_customer(self):
        """Botón: entrega el comprobante al receptor y espera al envío.

        Desde la interfaz interesa saber en el momento si el correo salió, así que va
        con `force_send`. El automatismo usa la misma lógica pero encolando.
        """
        return self._l10n_ec_send_to_customer(force_send=True)

    def _l10n_ec_send_to_customer(self, force_send=False):
        """Envía el comprobante autorizado al receptor, con XML y RIDE adjuntos.

        La Ficha §4.7 lo plantea como obligación del emisor, no como opción. Es
        idempotente por diseño: marca `l10n_ec_sent_to_partner` y el automatismo no
        vuelve a enviar, pero el botón manual sí permite reenviar cuando el cliente
        dice que no le llegó.
        """
        template = self.env.ref(
            "l10n_ec_sri.mail_template_l10n_ec_invoice", raise_if_not_found=False
        )
        if not template:
            raise UserError(_(
                "Falta la plantilla de correo del comprobante electrónico. "
                "Actualice el módulo l10n_ec_sri."
            ))

        for move in self:
            if move.l10n_ec_sri_status != "authorized":
                raise UserError(_(
                    "Sólo se entrega al cliente un comprobante autorizado. %s está "
                    "en estado '%s'.", move.display_name, move.l10n_ec_sri_status,
                ))
            if not move.partner_id.email:
                raise UserError(_(
                    "El cliente %s no tiene correo electrónico.",
                    move.partner_id.display_name,
                ))

            attachments = move._l10n_ec_build_delivery_attachments()
            template.send_mail(
                move.id,
                force_send=force_send,
                email_values={"attachment_ids": [attachment.id for attachment in attachments]},
            )
            move.l10n_ec_sent_to_partner = True

    def _l10n_ec_build_delivery_attachments(self):
        """XML autorizado + RIDE en PDF, como `ir.attachment`."""
        self.ensure_one()
        attachments = self.env["ir.attachment"]
        safe_name = (self.name or "comprobante").replace("/", "-")

        if self.l10n_ec_xml_data:
            attachments |= self.env["ir.attachment"].create({
                "name": "%s.xml" % safe_name,
                "datas": self.l10n_ec_xml_data,
                "mimetype": "application/xml",
                "res_model": self._name,
                "res_id": self.id,
            })

        report = self.env.ref(
            "l10n_ec_sri.action_report_invoice_ride", raise_if_not_found=False
        )
        if report:
            pdf, _dummy = report._render_qweb_pdf(report.report_name, [self.id])
            attachments |= self.env["ir.attachment"].create({
                "name": "%s.pdf" % safe_name,
                "datas": base64.b64encode(pdf),
                "mimetype": "application/pdf",
                "res_model": self._name,
                "res_id": self.id,
            })
        return attachments

    def _l10n_ec_try_send_to_customer(self):
        """Entrega automática, tolerante a fallos.

        Se invoca justo al pasar a autorizado. Un fallo de correo NO debe revertir la
        autorización ni abortar el cron: el comprobante ya está autorizado ante el
        SRI, que es lo irreversible. Se registra en el chatter y queda el botón
        manual.

        Va en savepoint propio por dos motivos: deshacer los adjuntos a medias, y
        —más importante— que un error de base de datos no deje la transacción
        abortada, porque entonces el `message_post` de aviso también fallaría.

        El correo se ENCOLA (`force_send=False`): el cron no debe quedarse esperando
        a un servidor SMTP lento. Lo entrega la cola de correo de Odoo.
        """
        self.ensure_one()
        if self.l10n_ec_sent_to_partner or not self.partner_id.email:
            return
        try:
            with self.env.cr.savepoint():
                self._l10n_ec_send_to_customer(force_send=False)
        except Exception as exc:  # noqa: BLE001
            _logger.warning(
                "No se pudo entregar %s al receptor: %s", self.display_name, exc
            )
            self.message_post(body=_(
                "No se pudo enviar el comprobante al cliente por correo: %s\n\n"
                "El comprobante SÍ está autorizado. Use el botón «Enviar al cliente» "
                "para reintentarlo.", exc,
            ))

    # ------------------------------------------------------------------
    # Cron: cerrar el ciclo asíncrono del §7.4
    # ------------------------------------------------------------------

    @api.model
    def _l10n_ec_cron_process_pending(self, limit=200, max_age_days=30, max_retries=5):
        """Hace avanzar los comprobantes atascados.

        La Ficha (§7.4) describe el consumo como asíncrono: se envía, se espera y se
        consulta la autorización aparte. Sin este cron nada hacía la segunda parte, y
        toda factura enviada se quedaba en 'sent' hasta que alguien pulsaba el botón.

        Dos colas en una sola pasada:
          1. `sent`     → consultar autorización.
          2. `rejected` con fallo de transporte → reintentar el envío.

        Un comprobante problemático no debe frenar a los demás, así que cada uno va en
        su savepoint y los errores se registran sin propagarse.
        """
        cutoff = fields.Date.subtract(fields.Date.today(), days=max_age_days)

        pending = self.search([
            ("l10n_ec_sri_status", "=", "sent"),
            ("l10n_ec_sri_access_key", "!=", False),
            ("invoice_date", ">=", cutoff),
        ], limit=limit)
        l10n_ec_run_isolated(pending, "action_check_sri")

        # §5.10: el reenvío usa la MISMA clave y secuencial, que ya están guardados.
        retryable = self.search([
            ("l10n_ec_sri_status", "=", "rejected"),
            ("l10n_ec_sri_retryable", "=", True),
            ("l10n_ec_sri_retry_count", "<", max_retries),
            ("invoice_date", ">=", cutoff),
        ], limit=limit)
        for move in retryable:
            move.l10n_ec_sri_retry_count += 1
        l10n_ec_run_isolated(retryable, "action_send_sri")

        return len(pending) + len(retryable)
