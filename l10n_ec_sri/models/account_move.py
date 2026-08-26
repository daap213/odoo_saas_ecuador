# -*- coding: utf-8 -*-
import base64
import logging

from odoo import api, models, fields, _
from odoo.exceptions import UserError

# Una sola definicion de los codigos 43/70 para los tres emisores: estaban
# reimplementados como literal en cada uno, asi que un cambio de la Ficha habria
# que acordarse de aplicarlo tres veces.
from odoo.addons.l10n_ec_edi.models.sri_service import ALREADY_RECEIVED_CODES

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


def l10n_ec_flag_for_attention(record, summary, note):
    """Abre una actividad sobre el comprobante para que alguien lo mire.

    Hasta ahora, un comprobante que salia de las colas del cron —rechazo definitivo,
    reintentos agotados, envio muy antiguo sin resolver— no dejaba ninguna senal: ni
    chatter, ni actividad, ni filtro en la vista. Simplemente dejaba de moverse, y
    nadie se enteraba hasta que el cliente reclamaba la factura.

    Es idempotente: si ya hay una actividad abierta con el mismo resumen, no crea
    otra. Un cron cada 30 minutos generaria 48 avisos diarios por documento.
    """
    existing = record.activity_ids.filtered(
        lambda activity: activity.summary == summary
    )
    if existing:
        return existing[:1]
    return record.activity_schedule(
        "mail.mail_activity_data_todo",
        summary=summary,
        note=note,
        user_id=(record.invoice_user_id.id
                 if "invoice_user_id" in record._fields and record.invoice_user_id
                 else record.create_uid.id),
    )


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

    # ── Documento rectificado (notas de crédito y de débito) ──────────────────
    #
    # `codDocModificado`, `numDocModificado` y `fechaEmisionDocSustento` son
    # OBLIGATORIOS en 04 y 05. Se siembran desde `reversed_entry_id` (nota de crédito
    # creada con el asistente de reversión) o `debit_origin_id` (nota de débito del
    # módulo `account_debit_note`), pero quedan editables: un `out_refund` creado a
    # mano no tiene ninguno de los dos, y sin estos datos el comprobante no se puede
    # emitir. Por eso son compute+store+readonly=False y no `related`.
    # Un compute POR CAMPO, no uno compartido. Odoo marca todo un grupo de compute
    # como "puesto a mano" en cuanto el usuario escribe en cualquiera de sus campos:
    # con un único `_compute_l10n_ec_modified_doc`, rellenar el motivo dejaba los
    # otros tres a False para siempre.
    l10n_ec_modified_doc_type_id = fields.Many2one(
        "l10n_latam.document.type",
        string="Tipo de documento modificado",
        copy=False,
        compute="_compute_l10n_ec_modified_doc_type_id",
        store=True,
        readonly=False,
        help="Tipo del comprobante que esta nota rectifica (<codDocModificado>).",
    )
    l10n_ec_modified_doc_number = fields.Char(
        string="Número del documento modificado",
        copy=False,
        size=17,
        compute="_compute_l10n_ec_modified_doc_number",
        store=True,
        readonly=False,
        help="Formato 001-001-000000001, con guiones (<numDocModificado>).",
    )
    l10n_ec_modified_doc_date = fields.Date(
        string="Fecha del documento modificado",
        copy=False,
        compute="_compute_l10n_ec_modified_doc_date",
        store=True,
        readonly=False,
        help="Fecha de emisión del comprobante rectificado "
             "(<fechaEmisionDocSustento>).",
    )
    l10n_ec_modification_reason = fields.Char(
        string="Motivo de la modificación",
        copy=False,
        size=300,
        compute="_compute_l10n_ec_modification_reason",
        store=True,
        readonly=False,
        help="Texto libre que explica por qué se emite la nota (<motivo>).",
    )

    def _l10n_ec_get_modified_move(self):
        """El comprobante que esta nota rectifica, si Odoo lo conoce.

        `reversed_entry_id` sólo se rellena cuando la nota de crédito nace del
        asistente de reversión; `debit_origin_id` lo aporta `account_debit_note`. Un
        documento creado a mano no tiene ninguno, y ahí el usuario rellena los campos.
        """
        self.ensure_one()
        return self.reversed_entry_id or self.debit_origin_id

    @api.depends("reversed_entry_id", "debit_origin_id")
    def _compute_l10n_ec_modified_doc_type_id(self):
        for move in self:
            origin = move._l10n_ec_get_modified_move()
            move.l10n_ec_modified_doc_type_id = (
                origin.l10n_latam_document_type_id if origin
                else move.l10n_ec_modified_doc_type_id
            )

    @api.depends("reversed_entry_id", "debit_origin_id")
    def _compute_l10n_ec_modified_doc_number(self):
        for move in self:
            origin = move._l10n_ec_get_modified_move()
            move.l10n_ec_modified_doc_number = (
                origin.l10n_latam_document_number if origin
                else move.l10n_ec_modified_doc_number
            )

    @api.depends("reversed_entry_id", "debit_origin_id")
    def _compute_l10n_ec_modified_doc_date(self):
        for move in self:
            origin = move._l10n_ec_get_modified_move()
            move.l10n_ec_modified_doc_date = (
                origin.invoice_date if origin else move.l10n_ec_modified_doc_date
            )

    @api.depends("reversed_entry_id", "debit_origin_id")
    def _compute_l10n_ec_modification_reason(self):
        for move in self:
            origin = move._l10n_ec_get_modified_move()
            if origin and not move.l10n_ec_modification_reason:
                move.l10n_ec_modification_reason = (move.ref or "")[:300]
            else:
                move.l10n_ec_modification_reason = move.l10n_ec_modification_reason

    # ── Liquidación de compra (codDoc 03) ────────────────────────────────────
    #
    # Dos cosas del `l10n_ec` oficial impiden emitirla, y las dos hay que
    # sortearlas con overrides DELIBERADAMENTE estrechos: cualquier exceso de
    # alcance rompe las facturas de proveedor normales.

    def _l10n_ec_is_purchase_liquidation(self):
        """¿Es este asiento una liquidación de compra?"""
        self.ensure_one()
        return (
            self.move_type == "in_invoice"
            and self.l10n_latam_document_type_id.internal_type
            == "purchase_liquidation"
        )

    def _get_l10n_latam_documents_domain(self):
        """Deja elegir el tipo 03 en los diarios marcados como de liquidación.

        El oficial fuerza `internal_type = 'invoice'` para `in_invoice`, con lo que
        `purchase_liquidation` no entra nunca en el dominio y el tipo 03 no es
        seleccionable. Aquí se amplía ESE filtro y sólo ese, y sólo cuando el diario
        lleva `l10n_ec_allow_purchase_liquidation`.

        Se manipula el dominio que devuelve `super()` porque depende de la forma
        interna de un módulo que no controlamos: si el oficial cambia esa tupla, este
        override deja de encontrarla y la liquidación vuelve a no ser seleccionable —
        de forma visible, no silenciosa. Hay un test que lo vigila.
        """
        domain = super()._get_l10n_latam_documents_domain()
        # No se comprueba `country_code`: `l10n_ec_allow_purchase_liquidation` sólo
        # existe en este módulo y sólo significa algo en Ecuador, así que tenerlo
        # marcado YA es la declaración de intenciones. Además `country_code` sale de
        # `account_fiscal_country_id`, que no siempre está poblado en un borrador
        # recién creado, y con él la condición fallaba en silencio.
        if not (
            self.move_type == "in_invoice"
            and self.journal_id.l10n_ec_allow_purchase_liquidation
        ):
            return domain

        # Hay DOS cláusulas de `internal_type` que dejan fuera la liquidación, y vienen
        # de módulos distintos:
        #
        #   ('internal_type', 'in', ['invoice','debit_note','all'])  <- l10n_latam_invoice_document
        #   ('internal_type', '=',  'invoice')                       <- l10n_ec oficial
        #
        # Ampliar sólo la segunda no sirve de nada: la primera sigue filtrando. Por eso
        # se recorre el dominio y se añade `purchase_liquidation` a CUALQUIER condición
        # sobre `internal_type`, sea cual sea su forma.
        widened = []
        for condition in domain:
            if (
                isinstance(condition, (list, tuple))
                and len(condition) == 3
                and condition[0] == "internal_type"
            ):
                values = (
                    [condition[2]] if condition[1] == "="
                    else list(condition[2])
                )
                if "purchase_liquidation" not in values:
                    values.append("purchase_liquidation")
                widened.append(("internal_type", "in", values))
            else:
                widened.append(condition)
        return widened

    def _get_l10n_ec_documents_allowed(self, identification_code):
        """Añade el tipo 03 a la lista blanca por tipo de identificación.

        El oficial construye esa lista con `_DOCUMENTS_MAPPING`, indexada por el
        código ATS del tipo de identificación del partner, y la impone con
        `('id', 'in', allowed_documents.ids)`. Ampliar sólo el `internal_type` no
        basta: este segundo filtro deja fuera igualmente la liquidación.
        """
        allowed = super()._get_l10n_ec_documents_allowed(identification_code)
        if (
            self.move_type == "in_invoice"
            and self.journal_id.l10n_ec_allow_purchase_liquidation
        ):
            liquidation = self.env.ref("l10n_ec.ec_dt_03", raise_if_not_found=False)
            if liquidation:
                allowed |= liquidation
        return allowed

    def _is_manual_document_number(self):
        """La liquidación de compra la numera el emisor, no el proveedor.

        `l10n_latam_invoice_document` decide "manual" por el tipo de diario: en una
        factura de proveedor el número lo pone el proveedor. Pero en una liquidación
        el emisor somos nosotros, así que tiene que autonumerarse desde nuestro
        establecimiento y punto de emisión.

        El override es de una sola condición a propósito: si se ampliara, TODA factura
        de proveedor empezaría a autonumerarse y pisaría el número del proveedor.
        """
        if self._l10n_ec_is_purchase_liquidation():
            return False
        return super()._is_manual_document_number()

    def action_send_sri(self):
        """Genera clave, XML, firma y transmite al SRI."""
        for move in self:
            if move.l10n_ec_sri_status in ("authorized", "sent"):
                continue

            # Un rechazo definitivo no se reenvia: la clave ya esta registrada en el
            # SRI y el reenvio solo devuelve el codigo 43. Hay que emitir un
            # comprobante nuevo, con secuencial nuevo.
            if move.l10n_ec_sri_status == "rejected_final":
                raise UserError(_(
                    "El SRI rechazo definitivamente %(doc)s y su clave de acceso ya "
                    "quedo registrada: reenviarla solo devuelve el codigo 43 "
                    "('clave de acceso registrada'), nunca una autorizacion.\n\n"
                    "Motivo del rechazo:\n%(error)s\n\n"
                    "Corrija el dato en un comprobante NUEVO: este ya consumio su "
                    "secuencial.",
                    doc=move.display_name,
                    error=move.l10n_ec_sri_error or _("sin detalle"),
                ))

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

        already_at_sri = ALREADY_RECEIVED_CODES & set(response.get("identifiers", []))
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
                # Terminal, no "rejected": el SRI ya registro la clave. Ver el
                # comentario del campo de estado.
                move.l10n_ec_sri_status = "rejected_final"
                move.l10n_ec_sri_retryable = False
                move.l10n_ec_sri_error = "\n".join(response.get("messages", []))
                move._l10n_ec_notify_terminal_rejection()
            else:
                # EN PROCESO / PPR / PENDING / ERROR: el SRI puede tardar hasta 24 h
                # (§7.5). Antes se ignoraban en silencio y el usuario no sabía nada.
                move.l10n_ec_sri_error = _(
                    "Estado en el SRI: %s. %s",
                    status or _("sin respuesta"),
                    " ".join(response.get("messages", [])),
                )

    def _l10n_ec_notify_terminal_rejection(self):
        """Avisa de que el comprobante no se puede recuperar reenviandolo."""
        self.ensure_one()
        l10n_ec_flag_for_attention(
            self,
            _("El SRI rechazo definitivamente este comprobante"),
            _(
                "La clave de acceso ya quedo registrada en el SRI, asi que reenviar "
                "este comprobante devolvera siempre el codigo 43. Hay que emitir uno "
                "nuevo con la correccion.\n\nMotivo:\n%s",
                self.l10n_ec_sri_error or _("sin detalle"),
            ),
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

        # La cola de consulta NO se acota por fecha. Antes se descartaban los envios
        # de mas de `max_age_days`, con lo que un comprobante que el SRI hubiera
        # autorizado el dia 31 se quedaba en 'sent' para siempre: el cron ya no
        # volvia a preguntar por el nunca.
        pending = self.search([
            ("l10n_ec_sri_status", "=", "sent"),
            ("l10n_ec_sri_access_key", "!=", False),
        ], order="invoice_date asc", limit=limit)
        l10n_ec_run_isolated(pending, "action_check_sri")

        # Lo que sigue sin resolverse pasado el plazo si merece que alguien lo mire:
        # la Ficha da al SRI 24 h (7.5), no un mes.
        for move in pending.filtered(
            lambda m: m.l10n_ec_sri_status == "sent"
            and m.invoice_date and m.invoice_date < cutoff
        ):
            l10n_ec_flag_for_attention(
                move,
                _("Comprobante enviado al SRI y sin resolver"),
                _(
                    "Se transmitio hace mas de %s dias y el SRI sigue sin autorizarlo "
                    "ni negarlo. Conviene consultarlo en el portal del SRI con la "
                    "clave de acceso %s.", max_age_days, move.l10n_ec_sri_access_key,
                ),
            )

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

        # Los que agotaron los reintentos salen de la cola en silencio. Avisar.
        exhausted = self.search([
            ("l10n_ec_sri_status", "=", "rejected"),
            ("l10n_ec_sri_retryable", "=", True),
            ("l10n_ec_sri_retry_count", ">=", max_retries),
        ], limit=limit)
        for move in exhausted:
            l10n_ec_flag_for_attention(
                move,
                _("Reintentos de envio al SRI agotados"),
                _(
                    "Se intento transmitir %(n)s veces sin exito. El cron ya no lo "
                    "reintentara.\n\nUltimo error:\n%(error)s",
                    n=move.l10n_ec_sri_retry_count,
                    error=move.l10n_ec_sri_error or _("sin detalle"),
                ),
            )

        return len(pending) + len(retryable)
