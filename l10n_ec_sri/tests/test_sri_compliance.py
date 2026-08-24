# -*- coding: utf-8 -*-
"""Cumplimiento de la Ficha Técnica SRI 2.34 en la factura electrónica."""
from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriCompliance(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.write({
            "vat": "1791251237001",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.company.write({
            "street": "Av. República E7-197 y Almagro",
            "l10n_ec_sri_environment": "test",
            "l10n_ec_forced_accounting": True,
        })
        cls.env["account.chart.template"].try_loading(
            "ec", cls.company, install_demo=False
        )

        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.journal.write({"l10n_ec_entity": "002", "l10n_ec_emission": "003"})

        cls.tax15 = cls.env["account.tax"].search([
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 15.0),
            ("company_id", "=", cls.company.id),
        ], limit=1)

        cls.partner = cls.env["res.partner"].create({
            "name": "CLIENTE DE PRUEBA S.A.",
            "vat": "1791251237001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
            "street": "Av. Amazonas N35-123",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Servicio de prueba", "default_code": "SRV-01", "type": "service",
        })

    def _make_invoice(self, quantity=2, price_unit=100.0, discount=0.0):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": quantity,
                "price_unit": price_unit,
                "discount": discount,
                "tax_ids": [(6, 0, self.tax15.ids)],
            })],
        })
        invoice.action_post()
        invoice.l10n_ec_sri_access_key = self.env["l10n_ec.sri.xml"].generate_access_key(
            invoice
        )
        return invoice

    def test_modulo_11_ejemplo_de_la_ficha(self):
        """La Ficha trae un ejemplo trabajado: la cadena 41261533 da 6."""
        self.assertEqual(
            self.env["l10n_ec.sri.xml"]._get_modulo_11("41261533"), "6"
        )

    def test_clave_de_acceso_49_digitos_numericos(self):
        invoice = self._make_invoice()
        key = invoice.l10n_ec_sri_access_key
        self.assertEqual(len(key), 49)
        self.assertTrue(key.isdigit(), "La clave de acceso debe ser íntegramente numérica")

    def test_clave_y_xml_no_pueden_discrepar(self):
        """Origen del error 58 del SRI: el cuerpo decía 001 y la clave otra cosa."""
        invoice = self._make_invoice()
        key = invoice.l10n_ec_sri_access_key
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )

        def text(tag):
            return root.findtext(f".//{tag}")

        self.assertEqual(text("codDoc"), key[8:10])
        self.assertEqual(text("ambiente"), key[23])
        self.assertEqual(text("estab"), key[24:27])
        self.assertEqual(text("ptoEmi"), key[27:30])
        self.assertEqual(text("secuencial"), key[30:39])
        self.assertEqual(text("claveAcceso"), key)
        # El establecimiento sale del diario, no de un literal.
        self.assertEqual(text("estab"), "002")
        self.assertEqual(text("ptoEmi"), "003")

    def test_bloque_pagos_es_obligatorio(self):
        """Sin <pagos> el comprobante no pasa el esquema (error 35)."""
        invoice = self._make_invoice()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        pagos = root.findall(".//pagos/pago")
        self.assertTrue(pagos, "El comprobante debe llevar al menos una forma de pago")
        self.assertTrue(root.findtext(".//pagos/pago/formaPago"))

    def test_descuento_se_reporta(self):
        """Con descuento, los totales deben cuadrar o el SRI da error 52."""
        invoice = self._make_invoice(quantity=2, price_unit=100.0, discount=10.0)
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        self.assertEqual(root.findtext(".//totalDescuento"), "20.00")
        self.assertEqual(root.findtext(".//detalle/descuento"), "20.00")

        sin_impuestos = float(root.findtext(".//totalSinImpuestos"))
        importe_total = float(root.findtext(".//importeTotal"))
        impuestos = sum(
            float(node.findtext("valor"))
            for node in root.findall(".//totalConImpuestos/totalImpuesto")
        )
        propina = float(root.findtext(".//propina"))
        self.assertAlmostEqual(importe_total, sin_impuestos + impuestos + propina, 2)

    def test_codigo_porcentaje_sale_del_catalogo(self):
        """Tabla 17: el IVA 15 % es el código 4, y debe venir de l10n_ec_type."""
        self.assertEqual(self.tax15.tax_group_id.l10n_ec_type, "vat15")
        codigo, porcentaje = self.env["l10n_ec.sri.xml"]._get_tax_sri_codes(self.tax15)
        self.assertEqual(codigo, "2")
        self.assertEqual(porcentaje, "4")

    def test_prologo_utf8(self):
        """La Ficha exige codificación UTF-8 (tabla 7)."""
        invoice = self._make_invoice()
        xml = self.env["l10n_ec.sri.xml"].render_xml(invoice)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))

    def test_raiz_lleva_id_comprobante(self):
        """La firma referencia URI="#comprobante"; sin ese id no hay firma válida."""
        invoice = self._make_invoice()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        self.assertEqual(root.get("id"), "comprobante")
        self.assertEqual(root.get("version"), "1.1.0")
