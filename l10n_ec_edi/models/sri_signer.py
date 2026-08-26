# -*- coding: utf-8 -*-
"""
XAdES-BES v1.3.2 ENVELOPED — Ecuador SRI
Traducción fiel de xml-signing.service.ts (core-billing-ec).

Algoritmo : RSA-SHA1
Hash      : SHA-1
C14N      : http://www.w3.org/TR/2001/REC-xml-c14n-20010315

SignedInfo referencia tres elementos:
  1. #comprobante       — el documento
  2. #Certificate1      — KeyInfo
  3. #SignedProperties  — propiedades XAdES (obligatorio)
"""
import base64
import datetime
import hashlib
import logging
import re

from lxml import etree
from odoo import models, _
from odoo.exceptions import UserError

try:
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.x509.oid import NameOID
except ImportError:
    logging.getLogger(__name__).warning("cryptography not installed")

_logger = logging.getLogger(__name__)

NS_DS   = 'http://www.w3.org/2000/09/xmldsig#'
NS_ETSI = 'http://uri.etsi.org/01903/v1.3.2#'

_ISSUER_OID_MAP = {
    NameOID.COMMON_NAME:               'CN',
    NameOID.ORGANIZATION_NAME:         'O',
    NameOID.ORGANIZATIONAL_UNIT_NAME:  'OU',
    NameOID.COUNTRY_NAME:              'C',
    NameOID.STATE_OR_PROVINCE_NAME:    'ST',
    NameOID.LOCALITY_NAME:             'L',
    NameOID.EMAIL_ADDRESS:             'EMAILADDRESS',
}


class SriSigner(models.AbstractModel):
    _name = "l10n_ec.sri.signer"
    _description = "XAdES-BES Signer Service"

    def sign_xml(self, xml_content_bytes, p12_binary, p12_password):
        if isinstance(p12_content := p12_binary, (str, bytes)):
            p12_content = base64.b64decode(p12_binary)
        try:
            private_key, certificate, _ = pkcs12.load_key_and_certificates(
                p12_content, p12_password.encode('utf-8')
            )
        except Exception as e:
            raise UserError(_("Certificado inválido o contraseña incorrecta: %s") % e)

        xml_str = xml_content_bytes.decode('utf-8') if isinstance(xml_content_bytes, bytes) else xml_content_bytes

        # 1. Digest del documento
        doc_digest = self._sha1_b64(self._c14n_str(xml_str))

        # 2. Datos del certificado
        cert_der     = certificate.public_bytes(serialization.Encoding.DER)
        cert_b64     = base64.b64encode(cert_der).decode()
        cert_digest  = self._sha1_b64(cert_der.decode('latin-1'), 'latin-1')
        issuer_dn    = self._build_issuer_dn(certificate)
        serial_dec   = str(certificate.serial_number)

        # 3. Hora Ecuador UTC-5
        ec_now      = datetime.datetime.utcnow() - datetime.timedelta(hours=5)
        signing_time = ec_now.strftime('%Y-%m-%dT%H:%M:%S') + '-05:00'

        # 4. KeyInfo
        ki_xml    = self._build_key_info(cert_b64, private_key)
        ki_digest = self._sha1_b64(self._c14n_str(ki_xml))

        # 5. SignedProperties
        sp_xml    = self._build_signed_properties(signing_time, cert_digest, issuer_dn, serial_dec)
        sp_digest = self._sha1_b64(self._c14n_str(sp_xml))

        # 6. SignedInfo → firma RSA-SHA1
        si_xml       = self._build_signed_info(doc_digest, ki_digest, sp_digest)
        si_canonical = self._c14n_str(si_xml)
        sig_value    = base64.b64encode(
            private_key.sign(si_canonical.encode('utf-8'), padding.PKCS1v15(), hashes.SHA1())
        ).decode()

        # 7. Ensamblar <ds:Signature> e insertar al final del elemento raíz
        signature_xml = self._build_signature(
            si_xml, sig_value, cert_b64, private_key,
            signing_time, cert_digest, issuer_dn, serial_dec,
        )
        return self._insert_signature(xml_str, signature_xml).encode('utf-8')

    # ── Fragmentos XML ────────────────────────────────────────────────────────

    def _build_signed_info(self, doc_digest, ki_digest, sp_digest):
        return (
            f'<ds:SignedInfo xmlns:ds="{NS_DS}" xmlns:etsi="{NS_ETSI}">'
                f'<ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
                f'<ds:SignatureMethod Algorithm="{NS_DS}rsa-sha1"/>'
                f'<ds:Reference Id="Ref0" URI="#comprobante">'
                    f'<ds:Transforms>'
                        f'<ds:Transform Algorithm="{NS_DS}enveloped-signature"/>'
                    f'</ds:Transforms>'
                    f'<ds:DigestMethod Algorithm="{NS_DS}sha1"/>'
                    f'<ds:DigestValue>{doc_digest}</ds:DigestValue>'
                f'</ds:Reference>'
                f'<ds:Reference URI="#Certificate1">'
                    f'<ds:DigestMethod Algorithm="{NS_DS}sha1"/>'
                    f'<ds:DigestValue>{ki_digest}</ds:DigestValue>'
                f'</ds:Reference>'
                f'<ds:Reference Type="http://uri.etsi.org/01903#SignedProperties" URI="#SignedProperties">'
                    f'<ds:DigestMethod Algorithm="{NS_DS}sha1"/>'
                    f'<ds:DigestValue>{sp_digest}</ds:DigestValue>'
                f'</ds:Reference>'
            f'</ds:SignedInfo>'
        )

    def _build_key_info(self, cert_b64, private_key):
        pub     = private_key.public_key()
        nums    = pub.public_numbers()
        mod_b64 = base64.b64encode(
            nums.n.to_bytes((nums.n.bit_length() + 7) // 8, 'big')
        ).decode()
        exp_hex = format(nums.e, 'x').zfill(6)
        exp_b64 = base64.b64encode(bytes.fromhex(exp_hex)).decode()
        return (
            f'<ds:KeyInfo xmlns:ds="{NS_DS}" xmlns:etsi="{NS_ETSI}" Id="Certificate1">'
                f'<ds:X509Data>'
                    f'<ds:X509Certificate>{cert_b64}</ds:X509Certificate>'
                f'</ds:X509Data>'
                f'<ds:KeyValue>'
                    f'<ds:RSAKeyValue>'
                        f'<ds:Modulus>{mod_b64}</ds:Modulus>'
                        f'<ds:Exponent>{exp_b64}</ds:Exponent>'
                    f'</ds:RSAKeyValue>'
                f'</ds:KeyValue>'
            f'</ds:KeyInfo>'
        )

    def _build_signed_properties(self, signing_time, cert_digest, issuer_dn, serial_dec):
        esc = self._escape_xml
        return (
            f'<etsi:SignedProperties xmlns:etsi="{NS_ETSI}" xmlns:ds="{NS_DS}" Id="SignedProperties">'
                f'<etsi:SignedSignatureProperties>'
                    f'<etsi:SigningTime>{signing_time}</etsi:SigningTime>'
                    f'<etsi:SigningCertificate>'
                        f'<etsi:Cert>'
                            f'<etsi:CertDigest>'
                                f'<ds:DigestMethod Algorithm="{NS_DS}sha1"/>'
                                f'<ds:DigestValue>{cert_digest}</ds:DigestValue>'
                            f'</etsi:CertDigest>'
                            f'<etsi:IssuerSerial>'
                                f'<ds:X509IssuerName>{esc(issuer_dn)}</ds:X509IssuerName>'
                                f'<ds:X509SerialNumber>{serial_dec}</ds:X509SerialNumber>'
                            f'</etsi:IssuerSerial>'
                        f'</etsi:Cert>'
                    f'</etsi:SigningCertificate>'
                f'</etsi:SignedSignatureProperties>'
                # El ejemplo del Anexo 14 —la referencia contra la que valida el
                # SRI— cierra SignedSignatureProperties y añade este bloque. No es
                # obligatorio en XAdES-BES puro, pero es lo que el SRI publica, y
                # omitirlo es el motivo más repetido de rechazo en certificación.
                #
                # `ObjectReference` apunta al Id de la ds:Reference del documento,
                # que aquí es Ref0. Va DENTRO de SignedProperties, que se digesta y
                # se firma, así que el digest lo recoge por construcción.
                f'<etsi:SignedDataObjectProperties>'
                    f'<etsi:DataObjectFormat ObjectReference="#Ref0">'
                        f'<etsi:Description>contenido comprobante</etsi:Description>'
                        f'<etsi:MimeType>text/xml</etsi:MimeType>'
                    f'</etsi:DataObjectFormat>'
                f'</etsi:SignedDataObjectProperties>'
            f'</etsi:SignedProperties>'
        )

    def _build_signature(self, si_xml, sig_value, cert_b64, private_key,
                         signing_time, cert_digest, issuer_dn, serial_dec):
        ki_xml = self._build_key_info(cert_b64, private_key)
        sp_xml = self._build_signed_properties(signing_time, cert_digest, issuer_dn, serial_dec)
        # `Id="Signature"` NO es decorativo: `QualifyingProperties` apunta a
        # `Target="#Signature"`, y sin el atributo esa referencia quedaba colgando.
        # Añadirlo no altera ningún digest: la referencia al documento lleva la
        # transformada `enveloped-signature`, que elimina este elemento antes de
        # canonicalizar, y los otros dos digests son sobre KeyInfo y
        # SignedProperties, que no cambian.
        return (
            f'<ds:Signature xmlns:ds="{NS_DS}" xmlns:etsi="{NS_ETSI}" Id="Signature">'
                + si_xml
                + f'<ds:SignatureValue Id="SignatureValue">{sig_value}</ds:SignatureValue>'
                + ki_xml
                + f'<ds:Object>'
                    f'<etsi:QualifyingProperties Target="#Signature">'
                        + sp_xml +
                    f'</etsi:QualifyingProperties>'
                f'</ds:Object>'
            f'</ds:Signature>'
        )

    def _insert_signature(self, xml_str, signature_xml):
        match = re.search(r'(</[a-zA-Z:]+>)\s*$', xml_str)
        if not match:
            raise ValueError("Elemento raíz del XML no encontrado")
        close_tag = match.group(0).rstrip()
        pos = xml_str.rfind(close_tag)
        return xml_str[:pos] + signature_xml + xml_str[pos:]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _c14n_str(self, xml_str):
        """Canonical XML 1.0 (sin comentarios) sobre el elemento raíz del string."""
        doc = etree.fromstring(xml_str.encode('utf-8'))
        return etree.tostring(doc, method='c14n', exclusive=False, with_comments=False).decode('utf-8')

    def _sha1_b64(self, data, encoding='utf-8'):
        if isinstance(data, str):
            data = data.encode(encoding)
        return base64.b64encode(hashlib.sha1(data).digest()).decode()

    def _build_issuer_dn(self, certificate):
        """
        RFC 2253: atributos en orden inverso, separados por coma SIN espacio.
        E → EMAILADDRESS  (coincide con X509Certificate.getIssuerX500Principal en Java).
        """
        attrs = list(certificate.issuer)[::-1]
        parts = []
        for attr in attrs:
            name = _ISSUER_OID_MAP.get(attr.oid, attr.oid.dotted_string)
            parts.append(f"{name}={attr.value}")
        return ','.join(parts)

    def _escape_xml(self, s):
        return (s.replace('&', '&amp;').replace('<', '&lt;')
                 .replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;'))
