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
    l10n_ec_withhold_resolution = fields.Char("Resolution Number")
    l10n_ec_special_resolution = fields.Char("Special Contributor Resolution")
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
