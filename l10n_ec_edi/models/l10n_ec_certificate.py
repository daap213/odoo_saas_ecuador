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
from odoo.exceptions import UserError, ValidationError
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
    # Chatter y actividades para que el aviso de caducidad llegue a una persona y no
    # se quede en un WARNING del log que nadie lee hasta que ya es tarde.
    _inherit = ["mail.thread", "mail.activity.mixin"]
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
        # El .p12 contiene la clave privada de firma: quien lo descargue puede firmar
        # comprobantes en nombre de la empresa. Se protege igual que la contraseña.
        groups="base.group_system",
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

    def sign_xml(self, xml_bytes):
        """Firma un XML con este certificado y devuelve los bytes firmados.

        `content` (el .p12) y `password` están restringidos a base.group_system,
        pero cualquier usuario autorizado a emitir debe poder firmar. La lectura
        privilegiada se concentra aquí, en un único método acotado, en lugar de
        repartir .sudo() por los seis puntos que antes leían ambos campos.
        """
        self.ensure_one()

        # sudo() ANTES de leer nada: el ACL de lectura es amplio, pero `content` y
        # `password` están restringidos por campo a base.group_system. Si el estado se
        # comprobara sobre `self` sin privilegios, cualquier flujo de emisión que
        # cambie ese ACL en el futuro rompería con AccessError en vez de con el
        # mensaje útil de abajo.
        certificate = self.sudo()

        if certificate.state != "active":
            raise UserError(
                _("El certificado '%s' no está activo (estado: %s). "
                  "Valídelo antes de emitir comprobantes.")
                % (certificate.name, certificate.state)
            )

        return self.env["l10n_ec.sri.signer"].sign_xml(
            xml_bytes, certificate.content, certificate.password
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
                cert._l10n_ec_notify_expiry(_(
                    "El certificado de firma electrónica «%(name)s» CADUCÓ el "
                    "%(date)s. Hasta que se sustituya no se puede emitir ningún "
                    "comprobante electrónico.",
                    name=cert.name, date=cert.expiration_date,
                ))
            elif cert.days_until_expiry <= 30:
                _logger.warning(
                    "Certificate '%s' expires in %d days.",
                    cert.name,
                    cert.days_until_expiry,
                )
                cert._l10n_ec_notify_expiry(_(
                    "El certificado de firma electrónica «%(name)s» caduca en "
                    "%(days)s días (%(date)s). Conviene renovarlo antes: sin "
                    "certificado vigente la facturación electrónica se detiene.",
                    name=cert.name, days=cert.days_until_expiry,
                    date=cert.expiration_date,
                ))

    def _l10n_ec_notify_expiry(self, message):
        """Deja el aviso donde alguien lo vea, no sólo en el log.

        Un WARNING en el log del servidor no lo lee nadie hasta que ya es tarde. Se
        registra en el chatter del certificado y se crea una actividad para el
        responsable, que es lo que hace que la renovación ocurra a tiempo.

        Es best-effort: si no hay un responsable identificable, el cron no debe
        caerse por eso.
        """
        self.ensure_one()
        try:
            self.message_post(body=message)

            user = self.company_id.partner_id.user_ids[:1] or self.env.ref(
                "base.user_admin", raise_if_not_found=False
            )
            if user:
                # Sin duplicar: si ya hay una actividad viva sobre este certificado,
                # el cron diario no debe crear una nueva cada día.
                existing = self.env["mail.activity"].search_count([
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("user_id", "=", user.id),
                ])
                if not existing:
                    self.activity_schedule(
                        "mail.mail_activity_data_todo",
                        summary=_("Renovar certificado de firma electrónica"),
                        note=message,
                        user_id=user.id,
                    )
        except Exception as exc:  # noqa: BLE001 — avisar no debe romper el cron
            _logger.warning(
                "No se pudo notificar la caducidad del certificado %s: %s",
                self.display_name, exc,
            )

    _uniq_name_company = models.Constraint(
        "UNIQUE(name, company_id)",
        "Certificate name must be unique per company",
    )
