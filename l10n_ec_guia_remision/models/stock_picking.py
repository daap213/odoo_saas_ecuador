# -*- coding: utf-8 -*-
from odoo import api, models, fields, _
from odoo.exceptions import UserError

# Una sola definicion de los codigos 43/70 y un solo aislador de fallos
# para los tres emisores.
from odoo.addons.l10n_ec_edi.models.sri_service import ALREADY_RECEIVED_CODES
from odoo.addons.l10n_ec_sri.models.account_move import l10n_ec_run_isolated
import base64
from datetime import timezone


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # Transport Info
    l10n_ec_transport_reason = fields.Selection(
        [
            ("ventas", "Venta"),
            ("traslado", "Traslado entre establecimientos"),
            ("devolucion", "Devolución"),
            ("consignacion", "Consignación"),
            ("exportacion", "Exportación"),
            ("otros", "Otros"),
        ],
        string="Reason for Transport",
        default="ventas",
        copy=False,
    )

    l10n_ec_start_date = fields.Date(
        string="Start Date", default=fields.Date.context_today
    )
    l10n_ec_end_date = fields.Date(string="End Date", default=fields.Date.context_today)

    # Driver & Vehicle
    l10n_ec_driver_id = fields.Many2one("l10n_ec.driver", string="Driver")
    l10n_ec_vehicle_id = fields.Many2one("l10n_ec.vehicle", string="Vehicle")

    # Datos que el Anexo 3 exige y no existían.
    l10n_ec_route = fields.Char(
        string="Ruta",
        size=300,
        copy=False,
        help="Recorrido del transporte. Obligatorio: viaja en <ruta>.",
    )
    l10n_ec_sustento_move_id = fields.Many2one(
        "account.move",
        string="Comprobante de sustento",
        check_company=True,
        copy=False,
        domain="[('move_type', 'in', ('out_invoice', 'out_refund')), "
               "('state', '=', 'posted')]",
        help="Factura que sustenta el traslado. De ella salen <codDocSustento>, "
             "<numDocSustento>, <numAutDocSustento> y <fechaEmisionDocSustento>.",
    )
    l10n_ec_customs_document = fields.Char(
        string="Documento aduanero único",
        size=20,
        copy=False,
        help="Sólo para importaciones y exportaciones (<docAduaneroUnico>).",
    )
    l10n_ec_destination_establishment = fields.Char(
        string="Establecimiento de destino",
        size=3,
        copy=False,
        help="Código del establecimiento de destino (<codEstabDestino>).",
    )

    # SRI Integration Fields (Direct Link to Shared Logic)
    l10n_ec_guia_number = fields.Char(
        string="Número de guía",
        size=17,
        copy=False,
        readonly=True,
        index=True,
        help="001-001-000000001. Se asigna una sola vez, desde la secuencia del "
             "diario de guías, y NO se deriva del nombre del albarán: ese contador "
             "es por almacén y colisiona entre almacenes.",
    )
    l10n_ec_sri_access_key = fields.Char(string="SRI Access Key", copy=False)
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Borrador"),
            ("signed", "Firmado"),
            ("sent", "Enviado"),
            ("authorized", "Autorizado"),
            ("rejected", "Devuelto (corregible)"),
            # Ver el comentario del mismo estado en `l10n_ec_edi/account_move.py`.
            ("rejected_final", "Rechazado definitivamente"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    # `l10n_ec_sri_error` y no `l10n_ec_sri_response`: el mismo nombre significaba
    # "campo obsoleto que nadie escribe" en `account.move` y "unico canal de
    # diagnostico" aqui, que es la peor clase de divergencia.
    l10n_ec_sri_error = fields.Text(string="Error del SRI", copy=False)
    l10n_ec_authorization_date = fields.Datetime(
        string="Fecha de autorización",
        copy=False,
        readonly=True,
        help="La que devuelve el SRI al autorizar. Faltaba, así que la guía "
             "autorizada no conservaba cuándo lo fue.",
    )
    l10n_ec_sri_retryable = fields.Boolean(
        string="Reintentable",
        copy=False,
        help="Un fallo de transporte se reintenta; un rechazo de contenido no.",
    )
    l10n_ec_sri_retry_count = fields.Integer(
        string="Reintentos", copy=False, default=0
    )
    l10n_ec_xml_data = fields.Binary("XML File", attachment=True)

    # ── Contrato con `l10n_ec.sri.xml` ───────────────────────────────────────
    #
    # `_get_document_components` delega en este método cuando el modelo emisor lo
    # implementa. Así la guía usa EXACTAMENTE la misma clave de acceso, el mismo
    # módulo 11 y el mismo código numérico determinista que la factura, en vez de la
    # copia paralela que tenía.

    def _l10n_ec_get_guia_journal(self):
        """Diario del que salen establecimiento y punto de emisión."""
        self.ensure_one()
        journal = (
            self.picking_type_id.l10n_ec_guia_journal_id
            or self.company_id.l10n_ec_guia_journal_id
        )
        if not journal:
            raise UserError(_(
                "No hay diario configurado para las guías de remisión.\n\n"
                "Indíquelo en el tipo de operación '%s' (Inventario > Configuración > "
                "Tipos de operación) o, para toda la empresa, en la ficha de la "
                "compañía. De ese diario salen el establecimiento y el punto de "
                "emisión que el SRI valida contra su RUC.",
                self.picking_type_id.display_name,
            ))
        return journal

    def _l10n_ec_assign_guia_number(self):
        """Asigna `001-001-000000001`, una sola vez y por diario.

        Nunca se deriva de `picking.name` (`WH/OUT/00001`): ese contador es por
        almacén, se reinicia y colisiona entre almacenes. El del SRI es por
        (establecimiento, punto de emisión, tipo de comprobante).
        """
        self.ensure_one()
        if self.l10n_ec_guia_number:
            return self.l10n_ec_guia_number
        journal = self._l10n_ec_get_guia_journal()
        sequential = journal._l10n_ec_get_sri_sequence("06").next_by_id()
        self.l10n_ec_guia_number = "{}-{}-{}".format(
            (journal.l10n_ec_entity or "").strip().zfill(3),
            (journal.l10n_ec_emission or "").strip().zfill(3),
            str(sequential).zfill(9),
        )
        return self.l10n_ec_guia_number

    def _l10n_ec_sri_components(self):
        """Componentes que la clave de acceso y el XML tienen que compartir."""
        self.ensure_one()
        journal = self._l10n_ec_get_guia_journal()
        number = self._l10n_ec_assign_guia_number()
        return {
            "establishment": (journal.l10n_ec_entity or "").strip().zfill(3),
            "emission_point": (journal.l10n_ec_emission or "").strip().zfill(3),
            "sequential": number.split("-")[-1],
            # No existe `ec_dt_06` en los tipos de documento del l10n_ec oficial, así
            # que el 06 es una constante y no una lectura de catálogo.
            "document_code": "06",
            "environment": (
                "2" if self.company_id.l10n_ec_sri_environment == "production" else "1"
            ),
        }

    def _l10n_ec_sri_emission_date(self):
        self.ensure_one()
        return (
            self.l10n_ec_start_date
            or (self.date_done.date() if self.date_done else False)
            or fields.Date.context_today(self)
        )

    def _generate_access_key(self):
        """Clave de acceso de 49 dígitos, con el generador compartido.

        Antes usaba `AccessKey.generate` de `l10n_ec_edi`, que rellena el código
        numérico con `random.randint`: cada reenvío producía una clave distinta y el
        comprobante se duplicaba en el SRI. La Ficha §5.10 exige reenviar con la MISMA
        clave. El generador de `l10n_ec.sri.xml` la deriva del secuencial.
        """
        for record in self:
            if not record.l10n_ec_sri_access_key:
                record.l10n_ec_sri_access_key = self.env[
                    "l10n_ec.sri.xml"
                ].generate_access_key(record)

    def _l10n_ec_get_ride_values(self):
        """Valores del RIDE. Lo llama la plantilla QWeb del informe."""
        self.ensure_one()
        return self.env["l10n_ec.sri.xml"].get_guia_ride_values(self)

    def action_send_guia_sri(self):
        """Genera clave, XML, firma y transmite la guia al SRI.

        Reescrito para que sea el mismo flujo que el de la factura. Lo anterior
        divergia en todo lo que importa: no tenia guarda de reenvio (pulsar dos veces
        volvia a transmitir un comprobante ya recibido), no trataba los codigos 43 y
        70, no comprobaba la caducidad del certificado, no exigia que el albaran
        estuviera validado, y envolvia todo en un `except Exception` que escribia el
        error en un campo de texto sin cambiar el estado: al usuario el boton le
        parecia no hacer nada.

        Y sobre todo: el secuencial se consumia ANTES de validar el cuerpo. La
        secuencia es de PostgreSQL y no es transaccional, asi que cada intento
        fallido quemaba un numero y el reintento producia una clave de acceso
        distinta — justo lo que prohibe el 5.10.
        """
        for record in self:
            if record.l10n_ec_sri_status in ("authorized", "sent"):
                continue

            if record.l10n_ec_sri_status == "rejected_final":
                raise UserError(_(
                    "El SRI rechazo definitivamente la guia %(doc)s y su clave de "
                    "acceso ya quedo registrada, asi que reenviarla no puede "
                    "autorizarla.\n\nMotivo:\n%(error)s\n\nEmita una guia nueva.",
                    doc=record.display_name,
                    error=record.l10n_ec_sri_error or _("sin detalle"),
                ))

            if record.state != "done":
                raise UserError(_(
                    "La guia %s ampara mercaderia que ya viaja: valide el albaran "
                    "antes de transmitirla al SRI.", record.display_name,
                ))

            # 0. TODOS los requisitos primero, incluido el certificado, y ANTES de
            #    tocar la secuencia. Si algo falta, no se gasta un numero.
            self.env["l10n_ec.sri.xml"]._check_guia_requirements(
                record, require_certificate=True
            )

            # 1. Numero y clave, una sola vez y conservados (5.10).
            record._generate_access_key()

            # 2. XML por el dispatcher compartido.
            xml_content = self.env["l10n_ec.sri.xml"].render_xml(record)

            # 3. Firma.
            signed_xml = record.company_id.l10n_ec_certificate_id.sign_xml(
                xml_content.encode("utf-8")
            )
            record.l10n_ec_xml_data = base64.b64encode(signed_xml)

            # 4. Envio, con la compania del documento.
            response = self.env["l10n_ec.sri.service"].send_document(
                record.company_id, signed_xml
            )
            record._l10n_ec_apply_reception_response(response)

    def _l10n_ec_apply_reception_response(self, response):
        """Traduce la respuesta de recepcion a un estado de la guia.

        Misma logica que la de `account.move`, incluidos los codigos 43 y 70: un
        DEVUELTA con esos identificadores no es un rechazo sino "ya lo tengo", y la
        Ficha (11 nota 2) prohibe reenviar.
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
                "El SRI ya tiene esta guia (codigo %s). No se reenvia: se consultara "
                "su autorizacion.", ", ".join(sorted(already_at_sri))
            )
            return

        self.l10n_ec_sri_status = "rejected"
        self.l10n_ec_sri_error = "\n".join(messages) or status
        self.l10n_ec_sri_retryable = (
            status == "ERROR" and not response.get("identifiers")
        )

    def action_check_guia_sri(self):
        """Consulta la autorizacion de la guia.

        No existia. La guia se quedaba en 'sent' para siempre: el estado 'authorized'
        era inalcanzable y la condicion `invisible` del boton que lo comprobaba nunca
        llegaba a cumplirse.
        """
        for record in self:
            if not record.l10n_ec_sri_access_key:
                raise UserError(_(
                    "La guia %s todavia no tiene clave de acceso.",
                    record.display_name,
                ))

            response = self.env["l10n_ec.sri.service"].check_authorization(
                record.company_id, record.l10n_ec_sri_access_key
            )
            status = response.get("status")

            if status == "AUTORIZADO":
                record.l10n_ec_sri_status = "authorized"
                record.l10n_ec_sri_error = False
                if response.get("date"):
                    date = response["date"]
                    if getattr(date, "tzinfo", None) is not None:
                        date = date.astimezone(timezone.utc).replace(tzinfo=None)
                    record.l10n_ec_authorization_date = date
                if response.get("xml"):
                    record.l10n_ec_xml_data = base64.b64encode(
                        response["xml"].encode("utf-8")
                    )
            elif status in ("NO AUTORIZADO", "RECHAZADO"):
                record.l10n_ec_sri_status = "rejected_final"
                record.l10n_ec_sri_retryable = False
                record.l10n_ec_sri_error = "\n".join(response.get("messages", []))
            else:
                # EN PROCESO / PPR / ERROR: el SRI puede tardar hasta 24 h (7.5).
                record.l10n_ec_sri_error = _(
                    "Estado en el SRI: %s. %s",
                    status or _("sin respuesta"),
                    " ".join(response.get("messages", [])),
                )

    @api.model
    def _l10n_ec_cron_process_guias(self, limit=200, max_retries=5):
        """Hace avanzar las guias atascadas, igual que el cron de las facturas."""
        pending = self.search([
            ("l10n_ec_sri_status", "=", "sent"),
            ("l10n_ec_sri_access_key", "!=", False),
        ], limit=limit)
        l10n_ec_run_isolated(pending, "action_check_guia_sri")

        retryable = self.search([
            ("l10n_ec_sri_status", "=", "rejected"),
            ("l10n_ec_sri_retryable", "=", True),
            ("l10n_ec_sri_retry_count", "<", max_retries),
        ], limit=limit)
        for picking in retryable:
            picking.l10n_ec_sri_retry_count += 1
        l10n_ec_run_isolated(retryable, "action_send_guia_sri")

        return len(pending) + len(retryable)
