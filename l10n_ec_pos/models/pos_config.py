# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PosConfig(models.Model):
    _inherit = "pos.config"

    l10n_ec_sri_active = fields.Boolean(
        string="Facturación electrónica SRI", default=True
    )

    l10n_ec_journal_id = fields.Many2one(
        "account.journal",
        string="Diario SRI del punto de venta",
        domain="[('type', '=', 'sale'), ('company_id', '=', company_id)]",
        check_company=True,
        help="De este diario salen el establecimiento, el punto de emisión y el "
             "secuencial de los comprobantes que emite esta caja.",
    )

    # Establecimiento y punto de emisión REALES, los del diario. Antes eran dos
    # campos de texto libre con `default="001"`: toda caja de toda empresa nacía
    # declarando el establecimiento 001, existiera o no en el RUC del emisor, y
    # dos cajas distintas podían compartir punto de emisión sin que nada avisara.
    l10n_ec_entity = fields.Char(
        related="l10n_ec_journal_id.l10n_ec_entity",
        string="Establecimiento",
        readonly=True,
    )
    l10n_ec_emission_point = fields.Char(
        related="l10n_ec_journal_id.l10n_ec_emission",
        string="Punto de emisión",
        readonly=True,
    )

    l10n_ec_default_partner_id = fields.Many2one(
        "res.partner",
        string="Cliente por defecto (Consumidor Final)",
        check_company=True,
    )

    @api.constrains("l10n_ec_sri_active", "l10n_ec_journal_id")
    def _check_l10n_ec_journal(self):
        """Sin diario no hay establecimiento ni secuencial que poner en la clave.

        Se comprueba al configurar la caja y no al cobrar: descubrirlo con el cliente
        delante es exactamente el momento en que no se puede resolver.
        """
        for config in self:
            if not config.l10n_ec_sri_active:
                continue
            journal = config.l10n_ec_journal_id
            if not journal:
                raise ValidationError(_(
                    "El punto de venta '%s' emite comprobantes electrónicos y no "
                    "tiene diario SRI asignado. De él salen el establecimiento, el "
                    "punto de emisión y el secuencial.", config.display_name,
                ))
            missing = []
            if not (journal.l10n_ec_entity or "").strip():
                missing.append(_("establecimiento"))
            if not (journal.l10n_ec_emission or "").strip():
                missing.append(_("punto de emisión"))
            if missing:
                raise ValidationError(_(
                    "Al diario '%(journal)s' le falta %(missing)s, y el SRI valida "
                    "esos códigos contra los establecimientos registrados en el RUC "
                    "del emisor.",
                    journal=journal.display_name,
                    missing=" y ".join(missing),
                ))
