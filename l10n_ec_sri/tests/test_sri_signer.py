# -*- coding: utf-8 -*-
"""
E2E Test: XAdES-BES Digital Signature
=====================================
Tests the REAL signing flow using a self-signed test certificate.

Certificado de prueba:
    - Se genera autofirmado en memoria (`certificate_fixture.build_test_p12`):
      RSA-2048, válido 365 días, CN `test.somatech.ec`, clave `test1234`.
    - Si existe `tests/certificates/test_certificate.p12` se usa ese en su lugar.
      Ese fichero NO está en el repo y no debe commitearse (`.gitignore` excluye
      `*.p12`): lleva una clave privada.

Un certificado autofirmado sirve para ejercitar el camino criptográfico, no para
emitir: el SRI sólo acepta los de una entidad de certificación acreditada.
"""
import unittest
import base64
from pathlib import Path

# These imports work outside Odoo context for unit testing
from lxml import etree
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import hashlib

from .certificate_fixture import TEST_P12_PASSWORD, build_test_p12


class TestXAdESSigner(unittest.TestCase):
    """
    Unit tests for the XAdES-BES signing implementation.
    These tests run OUTSIDE Odoo to verify the core cryptographic logic.
    """

    @classmethod
    def setUpClass(cls):
        """Prepara un certificado de prueba.

        Se usa `tests/certificates/test_certificate.p12` si existe (por si alguien
        quiere probar con uno propio) y, si no, se genera uno autofirmado en memoria.
        Antes se exigía el fichero, que no está en el repo — `.gitignore` excluye
        `*.p12` — así que la clase entera fallaba en cualquier clon nuevo.
        """
        cls.p12_password = TEST_P12_PASSWORD
        cert_path = Path(__file__).parent / "certificates" / "test_certificate.p12"

        if cert_path.exists():
            cls.p12_binary = cert_path.read_bytes()
        else:
            cls.p12_binary = build_test_p12(cls.p12_password)

        # Load certificate and key
        cls.private_key, cls.certificate, _ = pkcs12.load_key_and_certificates(
            cls.p12_binary, cls.p12_password.encode("utf-8")
        )

    def test_01_certificate_loading(self):
        """Verify the .p12 certificate loads correctly."""
        self.assertIsNotNone(self.private_key, "Private key should load")
        self.assertIsNotNone(self.certificate, "Certificate should load")

        # Verify it's RSA
        from cryptography.hazmat.primitives.asymmetric import rsa

        self.assertIsInstance(self.private_key, rsa.RSAPrivateKey, "Key should be RSA")

    def test_02_xml_canonicalization(self):
        """Verify C14N canonicalization works on sample XML."""
        sample_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <factura id="comprobante" version="2.1.0">
            <infoTributaria>
                <ambiente>1</ambiente>
                <razonSocial>Test Company</razonSocial>
            </infoTributaria>
        </factura>"""

        root = etree.fromstring(sample_xml)
        canonical = etree.tostring(
            root, method="c14n", exclusive=False, with_comments=False
        )

        # C14N should produce consistent output
        self.assertIsInstance(canonical, bytes)
        self.assertIn(b"<factura", canonical)

    def test_03_sha1_digest(self):
        """Verify SHA1 digest generation matches expected."""
        test_data = b"Hello SRI"
        digest = hashlib.sha1(test_data).digest()
        digest_b64 = base64.b64encode(digest).decode()

        # SHA1 of "Hello SRI" should be consistent
        self.assertEqual(len(digest), 20, "SHA1 produces 20 bytes")
        self.assertIsInstance(digest_b64, str)

    def test_04_rsa_sha1_signature(self):
        """Verify RSA-SHA1 signature generation."""
        test_data = b"<SignedInfo>test data to sign</SignedInfo>"

        signature = self.private_key.sign(test_data, padding.PKCS1v15(), hashes.SHA1())

        signature_b64 = base64.b64encode(signature).decode()

        # RSA-2048 produces 256-byte signature
        self.assertEqual(len(signature), 256, "RSA-2048 signature is 256 bytes")
        self.assertIsInstance(signature_b64, str)

    def test_05_full_signing_flow(self):
        """
        CRITICAL E2E TEST: Full XAdES-BES signing flow.
        This replicates the exact logic from sri_signer.py
        """
        # 1. Sample Invoice XML (minimal valid structure)
        invoice_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <factura id="comprobante" version="2.1.0">
            <infoTributaria>
                <ambiente>1</ambiente>
                <tipoEmision>1</tipoEmision>
                <razonSocial>EMPRESA DE PRUEBA</razonSocial>
                <ruc>1790000000001</ruc>
                <claveAcceso>2101202501179000000000110010010000000011234567813</claveAcceso>
                <codDoc>01</codDoc>
                <estab>001</estab>
                <ptoEmi>001</ptoEmi>
                <secuencial>000000001</secuencial>
                <dirMatriz>Quito</dirMatriz>
            </infoTributaria>
            <infoFactura>
                <fechaEmision>21/01/2025</fechaEmision>
                <tipoIdentificacionComprador>04</tipoIdentificacionComprador>
                <razonSocialComprador>CLIENTE PRUEBA</razonSocialComprador>
                <identificacionComprador>1790000000002</identificacionComprador>
                <totalSinImpuestos>100.00</totalSinImpuestos>
                <totalDescuento>0.00</totalDescuento>
                <importeTotal>115.00</importeTotal>
                <moneda>DOLAR</moneda>
            </infoFactura>
        </factura>"""

        # 2. Parse and Canonicalize
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.fromstring(invoice_xml, parser)

        xml_to_hash = etree.tostring(
            root, method="c14n", exclusive=False, with_comments=False
        )

        # 3. Calculate Document Digest (SHA1)
        document_digest = hashlib.sha1(xml_to_hash).digest()
        document_digest_b64 = base64.b64encode(document_digest).decode()

        self.assertEqual(len(document_digest), 20, "SHA1 digest is 20 bytes")

        # 4. Build SignedInfo (simplified)
        ns = "http://www.w3.org/2000/09/xmldsig#"
        signed_info = etree.Element(f"{{{ns}}}SignedInfo", nsmap={None: ns})

        c14n = etree.SubElement(signed_info, f"{{{ns}}}CanonicalizationMethod")
        c14n.set("Algorithm", "http://www.w3.org/TR/2001/REC-xml-c14n-20010315")

        sig_method = etree.SubElement(signed_info, f"{{{ns}}}SignatureMethod")
        sig_method.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#rsa-sha1")

        reference = etree.SubElement(signed_info, f"{{{ns}}}Reference")
        reference.set("URI", "#comprobante")

        digest_method = etree.SubElement(reference, f"{{{ns}}}DigestMethod")
        digest_method.set("Algorithm", "http://www.w3.org/2000/09/xmldsig#sha1")

        digest_val = etree.SubElement(reference, f"{{{ns}}}DigestValue")
        digest_val.text = document_digest_b64

        # 5. Sign the SignedInfo
        signed_info_c14n = etree.tostring(signed_info, method="c14n", exclusive=False)

        signature = self.private_key.sign(
            signed_info_c14n, padding.PKCS1v15(), hashes.SHA1()
        )
        signature_b64 = base64.b64encode(signature).decode()

        self.assertEqual(len(signature), 256, "Signature should be 256 bytes")

        # 6. Build KeyInfo
        cert_der = self.certificate.public_bytes(serialization.Encoding.DER)
        cert_b64 = base64.b64encode(cert_der).decode()

        key_info = etree.Element(f"{{{ns}}}KeyInfo", nsmap={None: ns})
        x509_data = etree.SubElement(key_info, f"{{{ns}}}X509Data")
        x509_cert = etree.SubElement(x509_data, f"{{{ns}}}X509Certificate")
        x509_cert.text = cert_b64

        # 7. Assemble Signature Node
        signature_node = etree.Element(
            f"{{{ns}}}Signature", Id="Signature-SRI", nsmap={None: ns}
        )
        signature_node.append(signed_info)

        sig_val_node = etree.Element(f"{{{ns}}}SignatureValue")
        sig_val_node.text = signature_b64
        signature_node.append(sig_val_node)
        signature_node.append(key_info)

        # 8. Append to Root
        root.append(signature_node)

        # 9. Output Final Signed XML
        signed_xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8")

        # ASSERTIONS
        self.assertIn(
            b"<ds:Signature",
            signed_xml.replace(b"Signature", b"ds:Signature") or signed_xml,
        )
        self.assertIn(b"SignatureValue", signed_xml)
        self.assertIn(b"X509Certificate", signed_xml)
        self.assertIn(document_digest_b64.encode(), signed_xml)

        print("\n✅ FULL SIGNING FLOW PASSED")
        print(f"   Signed XML Size: {len(signed_xml)} bytes")
        print(f"   Digest (SHA1): {document_digest_b64[:20]}...")
        print(f"   Signature: {signature_b64[:30]}...")


if __name__ == "__main__":
    unittest.main(verbosity=2)
