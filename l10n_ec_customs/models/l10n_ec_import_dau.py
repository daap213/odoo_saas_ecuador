# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class L10nEcImportDau(models.Model):
    """
    Declaración Aduanera Única (Import)

    Legal basis:
    - COPCI Art. 108-190: DAU requirements
    - LORTI Art. 75: ISD (Impuesto Salida Divisas)
    """

    _name = "l10n_ec.import.dau"
    _description = "Declaración Aduanera Única (Import)"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("DAU Number", required=True, tracking=True)
    date = fields.Date("Declaration Date", default=fields.Date.context_today)
    partner_id = fields.Many2one("res.partner", string="Customs Broker/Supplier")

    picking_id = fields.Many2one("stock.picking", string="Related Receipt")
    invoice_id = fields.Many2one("account.move", string="Commercial Invoice")

    # Values
    fob_value = fields.Float(
        "FOB Value", compute="_compute_fob_total", store=True, tracking=True
    )
    freight = fields.Float("Freight")
    insurance = fields.Float("Insurance")
    cif_value = fields.Float("CIF Value", compute="_compute_cif", store=True)

    # Taxes
    total_ad_valorem = fields.Float(
        "Total Ad Valorem", compute="_compute_taxes", store=True
    )
    total_fodinfa = fields.Float("Total FODINFA", compute="_compute_taxes", store=True)
    total_iva = fields.Float(
        "Total IVA Importación", compute="_compute_taxes", store=True
    )

    # ISD - LORTI Art. 75
    isd_applicable = fields.Boolean(
        string="ISD Aplicable",
        default=True,
        help="LORTI Art. 75: 5% standard, 2.5% monetary remittances, 0% exempt goods",
    )
    isd_rate = fields.Selection(
        [
            ("0.05", "5% - Standard"),
            ("0.025", "2.5% - Monetary remittances"),
            ("0", "0% - Exempt (goods, study abroad, health)"),
        ],
        string="ISD Rate",
        default="0.05",
    )
    isd_exemption_reason = fields.Text(
        string="ISD Exemption Reason", help="If 0%, document the legal exemption reason"
    )
    total_isd = fields.Float(
        "Total ISD",
        compute="_compute_isd",
        store=True,
        help="LORTI Art. 75: Applied to payment value (CIF + duties + taxes)",
    )

    state = fields.Selection(
        [("draft", "Draft"), ("calculated", "Calculated"), ("done", "Done")],
        default="draft",
    )

    line_ids = fields.One2many("l10n_ec.import.dau.line", "dau_id", string="Lines")

    @api.depends("line_ids.valor_fob_line")
    def _compute_fob_total(self):
        for rec in self:
            rec.fob_value = sum(line.valor_fob_line for line in rec.line_ids)

    @api.depends("fob_value", "freight", "insurance")
    def _compute_cif(self):
        for rec in self:
            rec.cif_value = rec.fob_value + rec.freight + rec.insurance

    @api.depends("line_ids.ad_valorem_amount", "cif_value")
    def _compute_taxes(self):
        ICP = self.env["ir.config_parameter"].sudo()

        # Get rates from config - NO HARDCODED FALLBACKS
        fodinfa_param = ICP.get_param("l10n_ec.fodinfa")
        iva_param = ICP.get_param("l10n_ec.customs_iva")

        if not fodinfa_param or not iva_param:
            # UserError, no ValueError: esto corre dentro de un compute almacenado, y
            # un ValueError ahí impide hasta abrir la lista de declaraciones.
            raise UserError(_(
                "Faltan las tasas aduaneras.\n\n"
                "Configure 'l10n_ec.fodinfa' y 'l10n_ec.customs_iva' en Ajustes > "
                "Técnico > Parámetros del sistema, con el modo desarrollador activo."
            ))

        fodinfa_rate = float(fodinfa_param)
        iva_rate = float(iva_param)

        for rec in self:
            rec.total_ad_valorem = sum(line.ad_valorem_amount for line in rec.line_ids)
            rec.total_fodinfa = rec.cif_value * fodinfa_rate

            # IVA Base = CIF + AdValorem + Fodinfa
            base_iva = rec.cif_value + rec.total_ad_valorem + rec.total_fodinfa
            rec.total_iva = base_iva * iva_rate

    @api.depends(
        "cif_value",
        "total_ad_valorem",
        "total_fodinfa",
        "total_iva",
        "isd_applicable",
        "isd_rate",
    )
    def _compute_isd(self):
        """
        Calculate ISD - LORTI Art. 75

        ISD base is the total payment value sent abroad.
        Rates:
        - 5%: Standard rate for payments abroad
        - 2.5%: Monetary remittances
        - 0%: Exempt (goods import, study abroad, medical)
        """
        for rec in self:
            if not rec.isd_applicable or not rec.isd_rate:
                rec.total_isd = 0.0
            else:
                # ISD is applied to the total payment value (CIF + all duties/taxes)
                isd_base = rec.cif_value + rec.total_ad_valorem + rec.total_fodinfa
                rate = float(rec.isd_rate)
                rec.total_isd = isd_base * rate

    def action_calculate(self):
        for rec in self:
            rec._compute_cif()
            rec._compute_taxes()
        self.write({"state": "calculated"})


class L10nEcImportDauLine(models.Model):
    _name = "l10n_ec.import.dau.line"
    _description = "DAU Line"

    dau_id = fields.Many2one("l10n_ec.import.dau", required=True)
    product_id = fields.Many2one("product.product", string="Product")
    tariff_id = fields.Many2one("l10n_ec.tariff.heading", string="Tariff Heading")

    valor_fob_line = fields.Float("FOB (Line)")
    cif_line = fields.Float("CIF (Line)", compute="_compute_cif_line", store=True)

    ad_valorem_amount = fields.Float(
        "Ad Valorem", compute="_compute_duties", store=True
    )

    @api.depends("dau_id.cif_value", "dau_id.fob_value", "valor_fob_line")
    def _compute_cif_line(self):
        for rec in self:
            header = rec.dau_id
            if header.fob_value and header.fob_value > 0:
                # Ratio: Header CIF / Header FOB
                ratio = header.cif_value / header.fob_value
                rec.cif_line = rec.valor_fob_line * ratio
            else:
                # Fallback if no FOB (shouldn't happen if lines exist)
                rec.cif_line = rec.valor_fob_line

    @api.depends("tariff_id", "cif_line")
    def _compute_duties(self):
        for rec in self:
            if rec.tariff_id:
                # Ad Valorem applied to CIF Line
                rec.ad_valorem_amount = rec.cif_line * (
                    rec.tariff_id.ad_valorem / 100.0
                )
            else:
                rec.ad_valorem_amount = 0.0
