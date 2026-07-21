# -*- coding: utf-8 -*-
from odoo import models, fields, api

SRI_URLS = {
    "test": {
        "reception": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "authorization": "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    },
    "production": {
        "reception": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
        "authorization": "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    },
}


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
        check_company=True,
        help="Select the active P12 certificate for signing.",
    )

    l10n_ec_withhold_agent = fields.Boolean("Withholding Agent")
    l10n_ec_withhold_resolution = fields.Char("Resolution Number")
    l10n_ec_special_resolution = fields.Char("Special Contributor Resolution")
    l10n_ec_forced_accounting = fields.Boolean("Forced to keep Accounting")
    l10n_ec_commercial_name = fields.Char("Commercial Name")

    # URLs: recomputed automatically when the environment changes, but stored
    # and editable so an administrator can still override them if SRI changes
    # its endpoints.
    l10n_ec_sri_reception_url = fields.Char(
        string="SRI Reception URL",
        compute="_compute_l10n_ec_sri_urls",
        store=True,
        readonly=False,
    )
    l10n_ec_sri_authorization_url = fields.Char(
        string="SRI Authorization URL",
        compute="_compute_l10n_ec_sri_urls",
        store=True,
        readonly=False,
    )

    @api.depends("l10n_ec_sri_environment")
    def _compute_l10n_ec_sri_urls(self):
        """Point the SRI webservice URLs to the selected environment.

        Values are taken from the system parameters seeded by l10n_ec_base
        (l10n_ec.sri_reception_url_test, ...), falling back to the official
        SRI endpoints if the parameters were removed.
        """
        get_param = self.env["ir.config_parameter"].sudo().get_param
        for company in self:
            env = company.l10n_ec_sri_environment or "test"
            suffix = "prod" if env == "production" else "test"
            company.l10n_ec_sri_reception_url = get_param(
                f"l10n_ec.sri_reception_url_{suffix}",
                SRI_URLS[env]["reception"],
            )
            company.l10n_ec_sri_authorization_url = get_param(
                f"l10n_ec.sri_authorization_url_{suffix}",
                SRI_URLS[env]["authorization"],
            )
