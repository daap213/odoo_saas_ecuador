# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_ec_sri_environment = fields.Selection(
        [("test", "Test"), ("production", "Production")],
        string="SRI Environment",
        default="test",
    )

    # Linked to the robust Certificate model instead of simple binary
    l10n_ec_certificate_id = fields.Many2one(
        "l10n_ec.certificate",
        string="SRI Electronic Signature",
        domain=[("state", "=", "active")],
        help="Select the active P12 certificate for signing.",
    )

    l10n_ec_withhold_agent = fields.Boolean("Withholding Agent")
    l10n_ec_withhold_resolution = fields.Char(
        "Resolution Number",
        help="Anexo 21: número de la resolución de agente de retención, sin ceros a "
             "la izquierda. Viaja en <agenteRetencion> (numérico, máximo 8).",
    )
    l10n_ec_special_resolution = fields.Char("Special Contributor Resolution")
    l10n_ec_big_taxpayer_resolution = fields.Char(
        "Gran Contribuyente - Resolución",
        help="Anexo 24: número de la resolución que califica a la empresa como Gran "
             "Contribuyente. Se emite en <infoAdicional>.",
    )

    def l10n_ec_rimpe_legend(self):
        """Leyenda RIMPE del Anexo 22, con el texto y la longitud exactos.

        La Ficha fija el contenido literal: 27 caracteres para el régimen RIMPE y 45
        para negocio popular, acentos incluidos. Devuelve cadena vacía si la empresa
        no está en RIMPE, en cuyo caso la etiqueta no debe emitirse.
        """
        self.ensure_one()
        taxpayer_type = self.partner_id.l10n_ec_taxpayer_type
        if taxpayer_type == "rimpe_e":
            return "CONTRIBUYENTE RÉGIMEN RIMPE"
        if taxpayer_type == "rimpe_p":
            return "CONTRIBUYENTE NEGOCIO POPULAR - RÉGIMEN RIMPE"
        return ""
    l10n_ec_forced_accounting = fields.Boolean("Forced to keep Accounting")
    l10n_ec_commercial_name = fields.Char("Commercial Name")

    # URLs
    l10n_ec_sri_reception_url = fields.Char(
        string="SRI Reception URL",
        default="https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    )
    l10n_ec_sri_authorization_url = fields.Char(
        string="SRI Authorization URL",
        default="https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    )
