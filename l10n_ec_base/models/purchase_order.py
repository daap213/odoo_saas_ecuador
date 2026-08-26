# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
#
# DE 045-2025: Penalty Calculation for Late Deliveries
# =====================================================
# Uses existing Odoo fields: date_planned (expected), picking.date_done (actual)
# Configuration via res.config.settings (standard Odoo pattern)

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


# Los dos parámetros de penalidad (DE 045-2025) se declaraban aquí en un
# `res.config.settings` que ningún XML mostraba nunca. Se han eliminado: el cálculo
# (`_compute_penalty`) los lee directamente de `ir.config_parameter`, así que aquel
# modelo no aportaba nada.
#
# Son valores REGULATORIOS —los fija un decreto, no el usuario— y por eso se
# configuran en Ajustes > Técnico > Parámetros del sistema, en modo desarrollador.
# Ver la cabecera de `l10n_ec_base/data/l10n_ec_sri_config.xml`.


class PurchaseOrder(models.Model):
    """
    Extends purchase.order with Ecuador penalty calculation per DE 045-2025.

    Uses EXISTING Odoo fields:
    - date_planned: Expected delivery date (already in purchase.order)
    - picking.date_done: Actual delivery date (from stock.picking)

    Uses res.config.settings for all regulatory values.
    """

    _inherit = "purchase.order"

    # Computed penalty fields
    l10n_ec_delay_days = fields.Integer(
        string="Días de Retraso",
        compute="_compute_penalty",
        store=True,
        help="Días de retraso en la entrega",
    )
    l10n_ec_penalty_amount = fields.Monetary(
        string="Monto Penalidad",
        compute="_compute_penalty",
        store=True,
        currency_field="currency_id",
        help="Penalidad calculada por retraso",
    )
    l10n_ec_penalty_capped = fields.Boolean(
        string="Penalidad Limitada",
        compute="_compute_penalty",
        store=True,
        help="Indica si la penalidad alcanzó el límite máximo",
    )
    l10n_ec_is_government_contract = fields.Boolean(
        string="Contrato Gubernamental",
        related="partner_id.l10n_ec_government_contractor",
        store=True,
        help="Se aplica régimen de penalidades DE 045-2025",
    )

    @api.depends("date_planned", "picking_ids.date_done", "amount_total")
    def _compute_penalty(self):
        """
        Computes delay days and penalty using EXISTING Odoo fields.
        - Expected: date_planned (standard purchase.order field)
        - Actual: max(picking.date_done) from related pickings
        """
        ICP = self.env["ir.config_parameter"].sudo()
        rate = float(ICP.get_param("l10n_ec.penalty_rate_daily", "0"))
        cap = float(ICP.get_param("l10n_ec.penalty_cap_percent", "0"))

        for order in self:
            order.l10n_ec_delay_days = 0
            order.l10n_ec_penalty_amount = 0.0
            order.l10n_ec_penalty_capped = False

            if not order.date_planned or not rate:
                continue

            # Get actual delivery from pickings (using existing Odoo field)
            done_pickings = order.picking_ids.filtered(
                lambda p: p.state == "done" and p.date_done
            )
            if not done_pickings:
                continue

            actual_delivery = max(done_pickings.mapped("date_done")).date()
            expected = order.date_planned.date()

            if actual_delivery > expected:
                delay = (actual_delivery - expected).days
                order.l10n_ec_delay_days = delay

                # Calculate penalty
                penalty = order.amount_total * (rate / 100) * delay

                # Apply cap if configured
                if cap > 0:
                    max_penalty = order.amount_total * (cap / 100)
                    if penalty > max_penalty:
                        order.l10n_ec_penalty_amount = max_penalty
                        order.l10n_ec_penalty_capped = True
                    else:
                        order.l10n_ec_penalty_amount = penalty
                else:
                    order.l10n_ec_penalty_amount = penalty

    @api.constrains("partner_id")
    def _check_uaf_for_government_contract(self):
        """
        DE 045-2025: Block contract confirmation if partner is government
        contractor without valid UAF certificate.
        """
        for order in self:
            partner = order.partner_id
            if partner.l10n_ec_government_contractor and not partner.l10n_ec_uaf_valid:
                raise ValidationError(
                    _(
                        "DE 045-2025: No se puede confirmar este pedido.\n\n"
                        "El proveedor '%s' es contratista del Estado pero no tiene "
                        "un Certificado UAF válido.\n\n"
                        "Por favor, solicite al proveedor que cargue su certificado "
                        "UAF antes de continuar."
                    )
                    % partner.name
                )
