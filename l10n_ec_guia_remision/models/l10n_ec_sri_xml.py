# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Registra la guía de remisión (codDoc 06) en el dispatcher de `l10n_ec_sri`.

La dirección de la dependencia importa: `l10n_ec_guia_remision` depende de `stock` y
de `l10n_ec_sri`, nunca al revés. Si el dispatcher fuera un diccionario a nivel de
módulo habría que mutarlo en tiempo de import —un global compartido entre bases de
datos y workers—; siendo un método, basta con un `super()`.
"""
from odoo import _, api, models
from odoo.exceptions import UserError


class L10nEcSriXml(models.AbstractModel):
    _inherit = "l10n_ec.sri.xml"

    @api.model
    def _get_document_renderers(self):
        renderers = super()._get_document_renderers()
        renderers["06"] = (
            "l10n_ec_guia_remision.l10n_ec_guia_xml",
            "_get_waybill_values",
        )
        return renderers

    @api.model
    def _check_guia_requirements(self, record, require_certificate=False):
        """Todo lo que la guía necesita para poder emitirse.

        Estaba dentro de `_get_waybill_values`, es decir DESPUÉS de que
        `generate_access_key` hubiera consumido el secuencial: cada intento fallido
        quemaba un número de la secuencia de PostgreSQL —que no es transaccional, de
        modo que el rollback no lo devolvía— y el reintento producía una clave de
        acceso distinta. El 5.10 exige exactamente lo contrario: reenviar con la
        MISMA clave.

        Al ser público, el flujo de envío lo llama primero y el render lo vuelve a
        llamar; comprobar dos veces es barato y garantiza que nadie renderice sin
        validar.
        """
        company = record.company_id
        driver = record.l10n_ec_driver_id
        vehicle = record.l10n_ec_vehicle_id

        missing = []
        if not driver:
            missing.append(_("transportista"))
        elif not driver.identification_number:
            missing.append(_("identificación del transportista"))
        if not vehicle or not vehicle.license_plate:
            missing.append(_("placa del vehículo"))
        if not record.partner_id:
            missing.append(_("destinatario"))
        if not (record.l10n_ec_route or "").strip():
            missing.append(_("ruta del transporte"))
        if not record.move_ids:
            missing.append(_("al menos una línea de producto"))
        if not (company.street or "").strip():
            missing.append(_("dirección de la matriz en la compañía"))

        ruc = (company.vat or "").strip()
        if len(ruc) != 13 or not ruc.isdigit():
            missing.append(_(
                "RUC de la compañía con 13 dígitos numéricos (actual: '%s')",
                ruc or "",
            ))

        # El diario decide establecimiento y punto de emisión, y de ahí sale el
        # secuencial. Si falta, no hay número que asignar.
        journal = (
            record.picking_type_id.l10n_ec_guia_journal_id
            or company.l10n_ec_guia_journal_id
        )
        if not journal:
            missing.append(_(
                "diario de guías de remisión (en el tipo de operación o en la "
                "compañía)"
            ))
        else:
            if not (journal.l10n_ec_entity or "").strip():
                missing.append(_(
                    "establecimiento SRI en el diario '%s'", journal.display_name))
            if not (journal.l10n_ec_emission or "").strip():
                missing.append(_(
                    "punto de emisión SRI en el diario '%s'", journal.display_name))

        if require_certificate:
            missing.extend(self._get_signing_problems(company))

        if missing:
            raise UserError(_(
                "Faltan datos obligatorios para emitir la guía %(doc)s:\n\n- %(list)s",
                doc=record.display_name,
                list="\n- ".join(missing),
            ))

        start = record.l10n_ec_start_date or record._l10n_ec_sri_emission_date()
        end = record.l10n_ec_end_date or start
        if end < start:
            raise UserError(_(
                "La fecha de fin del transporte (%(fin)s) es anterior a la de inicio "
                "(%(ini)s).", fin=end, ini=start,
            ))

    @api.model
    def _get_waybill_values(self, record):
        """Valores de la guía de remisión (Anexo 3, versión 1.1.0).

        `record` es un `stock.picking`, no un `account.move`: no tiene impuestos, ni
        totales, ni comprador. El destinatario es el `partner_id` del albarán y el
        transportista sale de `l10n_ec.driver`.
        """
        company = record.company_id
        driver = record.l10n_ec_driver_id
        vehicle = record.l10n_ec_vehicle_id

        self._check_guia_requirements(record)

        start = record.l10n_ec_start_date or record._l10n_ec_sri_emission_date()
        end = record.l10n_ec_end_date or start

        sustento = record.l10n_ec_sustento_move_id
        # Tabla 6 del transportista en Python. El `dict.get(..., "04")` que había
        # en la plantilla declaraba RUC ecuatoriano para un transportista
        # extranjero, que es justo el caso del tránsito internacional.
        carrier_id_type, carrier_id = self._get_identification_code(
            driver.identification_type,
            driver.identification_number,
            country_code=driver.country_code or None,
            allow_final_consumer=False,
        )
        return {
            "record": record,
            "picking": record,
            "company": company,
            "partner": record.partner_id,
            "driver": driver,
            "carrier_id_type": carrier_id_type,
            "carrier_id": carrier_id,
            "vehicle": vehicle,
            "access_key": record.l10n_ec_sri_access_key,
            "components": record._l10n_ec_sri_components(),
            "start_date": start.strftime("%d/%m/%Y"),
            "end_date": end.strftime("%d/%m/%Y"),
            # La etiqueta legible del Selection, no su clave: el SRI espera texto
            # libre y "ventas" no significa nada para quien lea el comprobante.
            "transport_reason": dict(
                record._fields["l10n_ec_transport_reason"].selection
            ).get(record.l10n_ec_transport_reason, record.l10n_ec_transport_reason or ""),
            "sustento": {
                "cod_doc": (sustento.l10n_latam_document_type_id.code or "").zfill(2)
                if sustento else "",
                "number": sustento.l10n_latam_document_number or "" if sustento else "",
                # Anexo 2: en el esquema offline el número de autorización ES la clave
                # de acceso del comprobante que sustenta.
                "authorization": sustento.l10n_ec_sri_access_key or "" if sustento else "",
                "date": sustento.invoice_date.strftime("%d/%m/%Y")
                if sustento and sustento.invoice_date else "",
            } if sustento else False,
            "additional_info": self._get_additional_info(record),
            "rimpe_legend": company.l10n_ec_rimpe_legend(),
            "quantity": lambda value: "%.6f" % (value or 0.0),
            "clip": lambda value, size: (value or "")[:size],
            "product_code": self._get_product_code,
        }

    @api.model
    def get_guia_ride_values(self, picking):
        """Valores del RIDE de la guia de remision (06).

        Vive aqui y no en `l10n_ec_sri` por lo mismo que el generador de su XML: el
        marco comun del RIDE no depende de `stock`, y la guia si. Reutiliza ese marco
        entero, de modo que la cabecera del emisor y el bloque de autorizacion siguen
        maquetados en un unico sitio.
        """
        company = picking.company_id
        sri = self.env["l10n_ec.sri.xml"]
        driver = picking.l10n_ec_driver_id
        vehicle = picking.l10n_ec_vehicle_id
        components = picking._l10n_ec_sri_components()
        start = picking.l10n_ec_start_date or picking._l10n_ec_sri_emission_date()
        carrier_id_type, carrier_id = sri._get_identification_code(
            driver.identification_type,
            driver.identification_number,
            country_code=driver.country_code or None,
            allow_final_consumer=False,
        )
        dest_id_type, dest_id = sri._get_partner_identification(
            picking.partner_id, allow_final_consumer=False
        )

        return {
            "record": picking,
            "company": company,
            "partner": picking.partner_id,
            "document_title": "GUÍA DE REMISIÓN",
            "document_code": "06",
            "body_template": "l10n_ec_guia_remision.report_ride_body_waybill",
            "counterparty_label": "Destinatario",
            "counterparty_id_label": "Identificación",
            "buyer_id_type": dest_id_type,
            "buyer_identification": dest_id,
            "document_number": "%s-%s-%s" % (
                components["establishment"],
                components["emission_point"],
                components["sequential"],
            ),
            "access_key": picking.l10n_ec_sri_access_key or "",
            "environment_label": (
                "PRODUCCIÓN" if components["environment"] == "2" else "PRUEBAS"
            ),
            "emission_date": start or "",
            "authorization_date": getattr(
                picking, "l10n_ec_authorization_date", False) or "",
            "start_date": start or "",
            "end_date": picking.l10n_ec_end_date or start or "",
            "carrier_name": driver.name or "",
            "carrier_id": carrier_id,
            "carrier_id_type": carrier_id_type,
            "plate": vehicle.license_plate or "",
            "route": picking.l10n_ec_route or "",
            "transport_reason": dict(
                picking._fields["l10n_ec_transport_reason"].selection
            ).get(picking.l10n_ec_transport_reason,
                  picking.l10n_ec_transport_reason or ""),
            "moves": picking.move_ids,
            # La guia no declara importes: solo mercaderia en transito. Por eso no
            # lleva ni formas de pago ni bloque de totales.
            "show_payments": False,
            "show_totals": False,
            "total_amount": "0.00",
            "modified": False,
            "motivos": [],
            "subtotals": [],
            "additional_info": sri._get_additional_info(picking),
            "rimpe_legend": company.l10n_ec_rimpe_legend(),
            "barcode": sri._get_access_key_barcode(picking.l10n_ec_sri_access_key),
            "product_code": sri._get_product_code,
            "money": lambda value: "%.2f" % (value or 0.0),
            "quantity": lambda value: "%.6f" % (value or 0.0),
        }
