# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Comprobantes electrónicos del punto de venta.

Reescrito para usar la misma orquestación que la factura y la guía. Lo anterior era
una **tercera** implementación de la clave de acceso, y la que peor envejecía:

* usaba `AccessKey.generate`, que rellena el código numérico con `random.randint`;
  cada vez que se recalculaba salía una clave distinta y el comprobante se duplicaba
  en el SRI. Es el mismo fallo que `l10n_ec_sri` y `l10n_ec_guia_remision` documentan
  haber eliminado;
* tomaba el establecimiento y el punto de emisión de dos campos de texto de la caja,
  con `default="001"`;
* sacaba el secuencial filtrando los dígitos de `pos_reference` y quedándose con los
  nueve últimos: dos cajas o dos sesiones podían producir el mismo número, y el
  contador no tenía ninguna relación con la serie que el SRI espera por
  (establecimiento, punto de emisión, tipo de comprobante).

Ahora la caja declara sus componentes con el mismo método que el albarán de la guía
(`_l10n_ec_sri_components`), de modo que `l10n_ec.sri.xml.generate_access_key` la
trata igual que a cualquier otro comprobante: mismo módulo 11, mismo código numérico
determinista y misma serie.
"""
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    l10n_ec_sri_access_key = fields.Char(
        string="Clave de acceso SRI", copy=False, size=49,
        help="49 dígitos. Se genera una sola vez y se conserva: la Ficha §5.10 "
             "exige que un reenvío use la misma clave.",
    )
    l10n_ec_document_number = fields.Char(
        string="Número del comprobante", copy=False, size=17,
        help="001-001-000000001, del diario SRI de la caja.",
    )
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Borrador"),
            ("signed", "Firmado"),
            ("sent", "Enviado"),
            ("authorized", "Autorizado"),
            ("rejected", "Devuelto (corregible)"),
            ("rejected_final", "Rechazado definitivamente"),
        ],
        string="Estado SRI",
        default="draft",
        copy=False,
        index=True,
    )
    l10n_ec_authorization_date = fields.Datetime(
        string="Fecha de autorización", copy=False, readonly=True
    )

    # ------------------------------------------------------------------
    # Componentes compartidos con el generador de claves de acceso
    # ------------------------------------------------------------------

    def _l10n_ec_get_pos_journal(self):
        """Diario del que salen establecimiento, punto de emisión y secuencial."""
        self.ensure_one()
        journal = self.config_id.l10n_ec_journal_id
        if not journal:
            raise UserError(_(
                "El punto de venta '%s' no tiene diario SRI asignado, así que no hay "
                "establecimiento ni punto de emisión que poner en la clave de "
                "acceso.", self.config_id.display_name,
            ))
        return journal

    def _l10n_ec_assign_document_number(self):
        """Asigna `001-001-000000001`, una sola vez y por diario."""
        self.ensure_one()
        if self.l10n_ec_document_number:
            return self.l10n_ec_document_number
        journal = self._l10n_ec_get_pos_journal()
        sequential = journal._l10n_ec_get_sri_sequence("01").next_by_id()
        self.l10n_ec_document_number = "{}-{}-{}".format(
            (journal.l10n_ec_entity or "").strip().zfill(3),
            (journal.l10n_ec_emission or "").strip().zfill(3),
            str(sequential).zfill(9),
        )
        return self.l10n_ec_document_number

    def _l10n_ec_sri_components(self):
        """Lo que la clave de acceso y el comprobante tienen que compartir.

        Mismo contrato que el albarán de la guía: `l10n_ec.sri.xml` lo consulta a
        través de `_get_document_components` cuando el registro no es un
        `account.move`.
        """
        self.ensure_one()
        journal = self._l10n_ec_get_pos_journal()
        number = self._l10n_ec_assign_document_number()
        return {
            "establishment": (journal.l10n_ec_entity or "").strip().zfill(3),
            "emission_point": (journal.l10n_ec_emission or "").strip().zfill(3),
            "sequential": number.split("-")[-1],
            "document_code": "01",
            "environment": (
                "2" if self.company_id.l10n_ec_sri_environment == "production"
                else "1"
            ),
        }

    def _l10n_ec_sri_emission_date(self):
        self.ensure_one()
        return (
            self.date_order.date() if self.date_order
            else fields.Date.context_today(self)
        )

    def _generate_pos_access_key(self):
        """Clave de acceso con el generador compartido y determinista."""
        for order in self:
            if order.l10n_ec_sri_access_key:
                continue
            order.l10n_ec_sri_access_key = self.env[
                "l10n_ec.sri.xml"
            ].generate_access_key(order)

    # ------------------------------------------------------------------
    # Enganche con la venta
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            if not order.config_id.l10n_ec_sri_active:
                continue
            if order.l10n_ec_sri_access_key:
                continue
            # Un fallo de configuración no puede impedir cobrar: el error queda
            # registrado y el comprobante se completa desde el backoffice. En una
            # caja, detener la venta por un dato de configuración es peor que
            # emitirla con retraso.
            try:
                with self.env.cr.savepoint():
                    order._generate_pos_access_key()
            except UserError as error:
                _logger.warning(
                    "Sin clave de acceso SRI para el pedido %s: %s",
                    order.display_name, error,
                )
        return orders

    def _prepare_invoice_vals(self):
        """La factura del pedido hereda el número y la clave ya emitidos.

        Si la factura se numerara por su cuenta, el ticket que se llevó el cliente y
        el XML que recibe el SRI declararían dos comprobantes distintos.
        """
        values = super()._prepare_invoice_vals()
        if not self.config_id.l10n_ec_sri_active:
            return values
        if self.config_id.l10n_ec_journal_id:
            values["journal_id"] = self.config_id.l10n_ec_journal_id.id
        if self.l10n_ec_document_number:
            values["l10n_latam_document_number"] = self.l10n_ec_document_number
        if self.l10n_ec_sri_access_key:
            values["l10n_ec_sri_access_key"] = self.l10n_ec_sri_access_key
        return values
