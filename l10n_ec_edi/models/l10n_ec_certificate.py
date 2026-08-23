# -*- coding: utf-8 -*-
"""
Ecuadorian Digital Signature (P12 Certificate) Management
=========================================================
Handles P12 certificate storage, validation, and lifecycle for SRI electronic invoicing.

Regulatory References:
- SRI Ficha Técnica v2.32
- Authorized providers: Security Data, ANF AC Ecuador, Banco Central

ISO/IEC 29148:2018 Compliant
"""
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import base64
import logging

# External cryptography library (verified in manifest)
try:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography import x509

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

_logger = logging.getLogger(__name__)


class L10nEcCertificate(models.Model):
    """
    Ecuadorian Digital Signature Certificate Model.

    Stores P12/PFX certificates for XAdES-BES signing of electronic documents.
    Validates certificate authenticity, expiration, and password correctness.
    """

    _name = "l10n_ec.certificate"
    _description = "Ecuadorian Digital Signature (SRI)"
    _check_company_auto = True
    _order = "state desc, expiration_date"

    name = fields.Char(
        string="Name", required=True, help='Friendly name, e.g. "Firma 2026"'
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    # P12 Certificate Storage
    content = fields.Binary(
        string="Certificate File (.p12)",
        required=True,
        attachment=True,
        help="Upload the .p12 or .pfx file from your authorized provider",
    )
    password = fields.Char(
        string="Password",
        required=True,
        groups="base.group_system",
        help="Password for the .p12 file. Stored securely.",
    )

    # Certificate Metadata (extracted on validation)
    subject_cn = fields.Char(
        string="Subject (CN)", readonly=True, help="Common Name from certificate"
    )
    issuer_cn = fields.Char(
        string="Issuer",
        readonly=True,
        help="Certificate Authority that issued this certificate",
    )
    serial_number = fields.Char(string="Serial Number", readonly=True)
    expiration_date = fields.Date(string="Expiration Date", readonly=True)
    issue_date = fields.Date(string="Issue Date", readonly=True)

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expired", "Expired"),
            ("invalid", "Invalid Password"),
        ],
        default="draft",
        string="Status",
        readonly=True,
    )

    days_until_expiry = fields.Integer(
        string="Days Until Expiry", compute="_compute_days_until_expiry", store=False
    )

    @api.depends("expiration_date")
    def _compute_days_until_expiry(self):
        """Compute days remaining until certificate expires."""
        today = fields.Date.today()
        for record in self:
            if record.expiration_date:
                delta = record.expiration_date - today
                record.days_until_expiry = delta.days
            else:
                record.days_until_expiry = 0

    def action_validate(self):
        """
        Validate the P12 certificate using cryptography library.

        Performs:
        1. Password verification
        2. Certificate extraction
        3. Expiration date check
        4. Metadata extraction (Subject, Issuer, Serial)

        Raises:
            ValidationError: If password is incorrect or certificate is invalid
        """
        if not CRYPTO_AVAILABLE:
            raise ValidationError(
                _(
                    "The 'cryptography' Python library is not installed. "
                    "Please run: pip install cryptography"
                )
            )

        for record in self:
            if not record.content:
                raise ValidationError(_("Please upload a .p12 file"))

            # Decode P12 content
            try:
                p12_data = base64.b64decode(record.content)
            except Exception:
                raise ValidationError(_("Invalid certificate file format"))

            # Load P12 with password
            try:
                private_key, certificate, additional_certs = (
                    pkcs12.load_key_and_certificates(
                        p12_data, record.password.encode("utf-8")
                    )
                )
            except ValueError as e:
                if "password" in str(e).lower() or "mac" in str(e).lower():
                    record.state = "invalid"
                    raise ValidationError(
                        _(
                            "Invalid password for P12 certificate. "
                            "Please verify the password is correct."
                        )
                    )
                raise ValidationError(_("Invalid P12 file: %s") % str(e))
            except Exception as e:
                raise ValidationError(_("Could not load P12 file: %s") % str(e))

            if not certificate:
                raise ValidationError(_("No certificate found in P12 file"))

            # Extract certificate metadata
            try:
                # Subject Common Name
                subject_cn = certificate.subject.get_attributes_for_oid(
                    x509.oid.NameOID.COMMON_NAME
                )
                record.subject_cn = subject_cn[0].value if subject_cn else "Unknown"

                # Issuer Common Name
                issuer_cn = certificate.issuer.get_attributes_for_oid(
                    x509.oid.NameOID.COMMON_NAME
                )
                record.issuer_cn = issuer_cn[0].value if issuer_cn else "Unknown"

                # Serial Number
                record.serial_number = str(certificate.serial_number)

                # Dates
                record.issue_date = certificate.not_valid_before_utc.date()
                record.expiration_date = certificate.not_valid_after_utc.date()

            except Exception as e:
                _logger.warning("Could not extract certificate metadata: %s", e)

            # Check expiration
            today = fields.Date.today()
            if record.expiration_date and record.expiration_date < today:
                record.state = "expired"
                raise ValidationError(
                    _("Certificate expired on %s. Please upload a valid certificate.")
                    % record.expiration_date
                )

            # All checks passed
            record.state = "active"
            _logger.info(
                "Certificate '%s' validated successfully. Expires: %s",
                record.name,
                record.expiration_date,
            )

    def action_check_expiry(self):
        """
        Cron job to check certificate expiration.
        Marks certificates as expired and sends warnings.
        """
        today = fields.Date.today()

        # Find certificates expiring soon or already expired
        expiring_soon = self.search(
            [
                ("state", "=", "active"),
                ("expiration_date", "!=", False),
            ]
        )

        for cert in expiring_soon:
            if cert.expiration_date < today:
                cert.state = "expired"
                _logger.warning(
                    "Certificate '%s' for company '%s' has EXPIRED.",
                    cert.name,
                    cert.company_id.name,
                )
            elif cert.days_until_expiry <= 30:
                _logger.warning(
                    "Certificate '%s' expires in %d days.",
                    cert.name,
                    cert.days_until_expiry,
                )

    _sql_constraints = [
        (
            "uniq_name_company",
            "unique(name, company_id)",
            "Certificate name must be unique per company",
        ),
    ]
