# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Certificado PKCS#12 autofirmado para las pruebas de firma.

Los tests de firma exigían `tests/certificates/test_certificate.p12`, un fichero que
**no está en el repo** — `.gitignore` excluye `*.p12`, y con razón: un `.p12` lleva la
clave privada. El resultado era que `setUpClass` reventaba con `FileNotFoundError` y
toda la clase quedaba en error en cualquier máquina recién clonada.

Aquí se genera al vuelo, en memoria, y se cachea por proceso. No toca el disco, así que
no hay nada que ignorar ni que limpiar.

Sirve para ejercitar el camino criptográfico (cargar el PKCS#12, canonicalizar, firmar
con RSA-SHA1 y validar los digests), que es lo que las pruebas comprueban. **No sirve
para emitir de verdad**: el SRI sólo acepta certificados de una entidad de certificación
acreditada.
"""
import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

TEST_P12_PASSWORD = "test1234"

_CACHE = {}


def build_test_p12(password=TEST_P12_PASSWORD, common_name="test.somatech.ec"):
    """Devuelve los bytes de un `.p12` autofirmado RSA-2048, válido un año.

    2048 bits porque es el mínimo que exige la Ficha (§6.2) y lo que usan los
    certificados reales; generar 2048 tarda lo suficiente como para que merezca la
    pena cachear el resultado entre clases de test.
    """
    key = (password, common_name)
    if key in _CACHE:
        return _CACHE[key]

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "EC"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Somatech.dev"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # `datetime.now(timezone.utc)` y no `utcnow()`: este último está deprecado desde
    # Python 3.12 y la imagen de Odoo 19 va por encima de esa versión.
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(private_key, hashes.SHA256())
    )

    p12_bytes = pkcs12.serialize_key_and_certificates(
        name=common_name.encode("utf-8"),
        key=private_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password.encode("utf-8")
        ),
    )
    _CACHE[key] = p12_bytes
    return p12_bytes


def build_expired_test_p12(password=TEST_P12_PASSWORD):
    """Igual que el anterior pero caducado ayer, para probar el bloqueo por caducidad."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "caducado.somatech.ec"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=400))
        .not_valid_after(now - datetime.timedelta(days=1))
        .sign(private_key, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(
        name=b"caducado",
        key=private_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(
            password.encode("utf-8")
        ),
    )
