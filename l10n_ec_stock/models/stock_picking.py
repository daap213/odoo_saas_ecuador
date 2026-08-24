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

    # SRI Integration Fields (Direct Link to Shared Logic)
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

    def _generate_access_key(self):
        """
        Calculates the 49-digit access key using the shared EDI utility.
        """
        for record in self:
            if (
                not record.l10n_ec_sri_access_key and record.l10n_ec_driver_id
            ):  # Only generate if driver assigned (proxy for ready)
                from odoo.addons.l10n_ec_edi.models.access_key import AccessKey

                env = (
                    "2"
                    if record.company_id.l10n_ec_sri_environment == "production"
                    else "1"
                )
                # Sequence handling: Stock Picking name is usually WH/OUT/00001
                # We need a proper sequence number.
                seq_num = record.name.split("/")[-1] if "/" in record.name else "0"
                # Remove non-digits
                seq_num = "".join(filter(str.isdigit, seq_num)) or "0"

                key = AccessKey.generate(
                    invoice_date=(
                        record.scheduled_date.date()
                        if record.scheduled_date
                        else fields.Date.today()
                    ),
                    doc_type="06",
                    ruc=record.company_id.vat,
                    environment=env,
                    establishment=getattr(
                        record.picking_type_id.warehouse_id,
                        "l10n_ec_establishment",
                        "001",
                    )
                    or "001",
                    emission_point="001",
                    sequential=seq_num,
                )
                record.l10n_ec_sri_access_key = key

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

            # 1. Render XML
            values = {
                "picking": record,
                "company": record.company_id,
                "environment": (
                    "1" if record.company_id.l10n_ec_sri_environment == "test" else "2"
                ),
                "access_key": record.l10n_ec_sri_access_key,
                "format_float": lambda x, p: ("%." + str(p) + "f") % x,
            }
            xml_content = self.env["ir.qweb"]._render(
                "l10n_ec_stock.l10n_ec_guia_xml", values
            )

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
