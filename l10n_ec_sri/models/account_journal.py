# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Secuencias del comprobante de retención, una por diario.

El SRI numera por (establecimiento, punto de emisión, tipo de comprobante). Una
secuencia global —que es lo que había: `l10n_ec.retention` con `company_id` a False—
significa que dos puntos de emisión comparten contador, así que el 001-002 arranca en
el número donde lo dejó el 001-001. Eso produce huecos en una serie y saltos en la
otra; el SRI tolera los huecos, pero la numeración deja de ser auditable.

La secuencia se crea perezosamente la primera vez que un diario emite: así no hace
falta sembrar nada por adelantado ni saber de antemano cuántos puntos de emisión
tendrá el cliente.
"""
from odoo import _, fields, models
from odoo.exceptions import UserError

# `standard` y no `no_gap`: el SRI prohíbe REUTILIZAR un secuencial, no tener huecos.
# `no_gap` serializa las escrituras concurrentes sobre el mismo diario y se convierte
# en un cuello de botella en cuanto hay varios usuarios emitiendo a la vez.
_SEQUENCE_IMPLEMENTATION = "standard"


class AccountJournal(models.Model):
    _inherit = "account.journal"

    # Interruptor de la liquidación de compra (codDoc 03).
    #
    # Es a la vez la puerta del dominio de tipos de documento y la del auto-envío: sin
    # él, marcar como liquidación cualquier factura de proveedor cambiaría su
    # numeración (la liquidación la emite el COMPRADOR y se autonumera; una factura de
    # proveedor lleva el número que puso el proveedor).
    l10n_ec_allow_purchase_liquidation = fields.Boolean(
        string="Emite liquidaciones de compra",
        help="Permite elegir el tipo de documento 03 en las facturas de proveedor de "
             "este diario y numerarlas con su establecimiento y punto de emisión. "
             "Actívelo sólo en un diario dedicado a liquidaciones de compra.",
    )

    def _l10n_ec_sequence_code(self, document_code):
        self.ensure_one()
        return "l10n_ec.sri.%s.journal.%s" % (document_code, self.id)

    def _l10n_ec_get_sri_sequence(self, document_code):
        """Secuencia de 9 dígitos de este diario para un tipo de comprobante."""
        self.ensure_one()
        entity = (self.l10n_ec_entity or "").strip()
        emission = (self.l10n_ec_emission or "").strip()
        if not entity or not emission:
            raise UserError(_(
                "El diario '%s' no tiene establecimiento y punto de emisión SRI.\n\n"
                "Configúrelos en Contabilidad > Configuración > Diarios.",
                self.display_name,
            ))

        code = self._l10n_ec_sequence_code(document_code)
        Sequence = self.env["ir.sequence"].sudo()
        sequence = Sequence.search(
            [("code", "=", code), ("company_id", "=", self.company_id.id)], limit=1
        )
        if not sequence:
            sequence = Sequence.create({
                "name": "SRI %s — %s (%s-%s)" % (
                    document_code, self.name, entity, emission,
                ),
                "code": code,
                "implementation": _SEQUENCE_IMPLEMENTATION,
                "padding": 9,
                "number_next": 1,
                "number_increment": 1,
                "company_id": self.company_id.id,
            })
        return sequence

    def _l10n_ec_next_retention_sequential(self):
        """Siguiente secuencial de 9 dígitos para el comprobante de retención (07)."""
        self.ensure_one()
        return self._l10n_ec_get_sri_sequence("07").next_by_id()
