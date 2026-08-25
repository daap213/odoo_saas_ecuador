# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError
import base64


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
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("sent", "Sent"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    l10n_ec_sri_response = fields.Text("SRI Response")
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

    def action_send_guia_sri(self):
        """
        Generates XML, Signs it, and Sends to SRI using l10n_ec_edi utils.
        """
        for record in self:
            if not record.l10n_ec_driver_id or not record.l10n_ec_vehicle_id:
                raise UserError(
                    _("Driver and Vehicle are required for SRI Transmission.")
                )

            if not record.l10n_ec_sri_access_key:
                record._generate_access_key()

            # 1. XML por el dispatcher compartido: mismo prólogo UTF-8, mismos
            #    componentes que la clave de acceso, mismas validaciones. Antes esto
            #    renderizaba a mano y con un XMLID que ya no existía
            #    (`l10n_ec_stock.l10n_ec_guia_xml`, del nombre viejo del módulo), así
            #    que reventaba SIEMPRE al pulsar el botón.
            xml_content = self.env["l10n_ec.sri.xml"].render_xml(record)

            # 2. Sign
            certificate = record.company_id.l10n_ec_certificate_id
            if not certificate or certificate.state != "active":
                raise UserError(
                    _("SRI Error: No active Signing Certificate configured.")
                )

            try:
                # Use AbstractModels from l10n_ec_edi
                service = self.env["l10n_ec.sri.service"]

                signed_xml_bytes = certificate.sign_xml(xml_content.encode("utf-8"))

                # 3. Transmit
                env_code = (
                    "1" if record.company_id.l10n_ec_sri_environment == "test" else "2"
                )
                response_data = service.send_document(record.company_id, signed_xml_bytes)

                # 4. Process
                if response_data.get("status") == "RECIBIDA":
                    record.l10n_ec_sri_status = "sent"
                    record.l10n_ec_sri_response = (
                        "RECIBIDA. Waiting for Authorization..."
                    )
                else:
                    record.l10n_ec_sri_status = "rejected"
                    msgs = "\n".join(response_data.get("messages", []))
                    record.l10n_ec_sri_response = (
                        f"{response_data.get('status')}: {msgs}"
                    )

                record.l10n_ec_xml_data = base64.b64encode(signed_xml_bytes)

            except Exception as e:
                record.l10n_ec_sri_response = f"System Error: {str(e)}"
