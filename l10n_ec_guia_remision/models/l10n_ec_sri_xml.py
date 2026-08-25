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
    def _get_waybill_values(self, record):
        """Valores de la guía de remisión (Anexo 3, versión 1.1.0).

        `record` es un `stock.picking`, no un `account.move`: no tiene impuestos, ni
        totales, ni comprador. El destinatario es el `partner_id` del albarán y el
        transportista sale de `l10n_ec.driver`.
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

        sustento = record.l10n_ec_sustento_move_id
        return {
            "record": record,
            "picking": record,
            "company": company,
            "partner": record.partner_id,
            "driver": driver,
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
        }
