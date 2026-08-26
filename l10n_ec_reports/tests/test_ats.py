# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Anexo Transaccional Simplificado.

El modulo no tenia ni un test, y era el que contenia el fallo mas caro del
repositorio: un comprobante mal formado lo rechaza el SRI en el acto, pero **un ATS
con datos inventados el SRI lo acepta**, y la diferencia no aparece hasta el cruce de
informacion.
"""
from lxml import etree

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ec", "regulatory")
class TestAtsCommon(TransactionCase):
    """Andamiaje: compania ecuatoriana, diarios con establecimiento y un periodo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.write({
            "vat": "1791251237001",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.company.write({
            "street": "Av. Republica E7-197",
            "l10n_ec_sri_environment": "test",
            "l10n_ec_forced_accounting": True,
        })
        cls.env["account.chart.template"].try_loading(
            "ec", cls.company, install_demo=False
        )
        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.sale_journal.write({"l10n_ec_entity": "002", "l10n_ec_emission": "003"})
        cls.purchase_journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.purchase_journal.write({
            "l10n_ec_entity": "002", "l10n_ec_emission": "005",
        })

        cls.tax_sale = cls.env["account.tax"].search([
            ("type_tax_use", "=", "sale"), ("amount", "=", 15.0),
            ("company_id", "=", cls.company.id),
        ], limit=1)
        cls.tax_purchase = cls.env["account.tax"].search([
            ("type_tax_use", "=", "purchase"), ("amount", "=", 15.0),
            ("company_id", "=", cls.company.id),
        ], limit=1)

        cls.customer = cls.env["res.partner"].create({
            "name": "CLIENTE ATS S.A.",
            "vat": "1791251237001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.supplier = cls.env["res.partner"].create({
            "name": "PROVEEDOR ATS",
            "vat": "1710034065001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.product = cls.env["product.product"].create({
            "name": "Servicio ATS", "default_code": "ATS-01", "type": "service",
        })

    def _wizard(self):
        return self.env["l10n_ec.ats.wizard"].create({
            "date_month": "08",
            "date_year": "2026",
            "company_id": self.company.id,
        })

    def _invoice(self, move_type, partner, journal, taxes, number=None,
                 price_unit=100.0):
        move = self.env["account.move"].create({
            "move_type": move_type,
            "partner_id": partner.id,
            "journal_id": journal.id,
            "invoice_date": fields.Date.to_date("2026-08-10"),
            "l10n_latam_document_type_id": self.env.ref("l10n_ec.ec_dt_01").id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": price_unit,
                "tax_ids": [(6, 0, taxes.ids)],
            })],
        })
        move.l10n_latam_document_type_id = self.env.ref("l10n_ec.ec_dt_01")
        if number:
            move.l10n_latam_document_number = number
        move.action_post()
        move.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(move)
        return move


@tagged("post_install", "-at_install", "l10n_ec", "regulatory")
class TestAtsGeneration(TestAtsCommon):

    def test_el_ats_se_genera(self):
        """Antes lanzaba AttributeError en la primera factura: leia
        `l10n_ec_authorization`, un campo que no existe en `account.move`."""
        self._invoice("in_invoice", self.supplier, self.purchase_journal,
                      self.tax_purchase, number="002-005-000000001")
        xml = self._wizard().generate_xml()
        root = etree.fromstring(xml)
        self.assertEqual(root.tag, "iva")
        self.assertEqual(root.findtext("IdInformante"), "1791251237001")
        self.assertEqual(len(root.findall(".//detalleCompras")), 1)

    def test_no_declara_numeros_inventados(self):
        """`("001","001","999999999")`, `"9999999999"` y `"0000000000"` eran los
        respaldos: numeros de comprobantes que no existen."""
        self._invoice("in_invoice", self.supplier, self.purchase_journal,
                      self.tax_purchase, number="002-005-000000001")
        self._invoice("out_invoice", self.customer, self.sale_journal,
                      self.tax_sale)
        content = self._wizard().generate_xml().decode("utf-8")
        for invented in ("9999999999", "999999999", "0000000000"):
            self.assertNotIn(invented, content)

    def test_el_numero_declarado_es_el_real(self):
        self._invoice("in_invoice", self.supplier, self.purchase_journal,
                      self.tax_purchase, number="002-005-000000042")
        root = etree.fromstring(self._wizard().generate_xml())
        purchase = root.find(".//detalleCompras")
        self.assertEqual(purchase.findtext("establecimiento"), "002")
        self.assertEqual(purchase.findtext("puntoEmision"), "005")
        self.assertEqual(purchase.findtext("secuencial"), "000000042")

    def test_un_numero_mal_formado_no_se_sustituye_por_uno_inventado(self):
        """Antes se caia a `("001", "001", "999999999")`: un comprobante que no
        existe, con un establecimiento que puede no estar en el RUC del emisor.

        Se prueba sobre el resolutor y no sobre una factura publicada porque el
        nucleo de Odoo ya impide dejar un numero mal formado en una publicada; el
        respaldo defendia de un caso que la capa de arriba nunca produce, y de paso
        tapaba los que si llegan (facturas sin numero, importadas o migradas).
        """
        wizard = self._wizard()
        self.assertIsNone(
            wizard._l10n_ec_document_parts(
                self.env["account.move"].new({
                    "l10n_latam_document_number": "SIN-FORMATO"})))
        self.assertIsNone(
            wizard._l10n_ec_document_parts(
                self.env["account.move"].new({"l10n_latam_document_number": False})))
        self.assertEqual(
            wizard._l10n_ec_document_parts(
                self.env["account.move"].new({
                    "l10n_latam_document_number": "002-005-000000042"})),
            ("002", "005", "000000042"),
        )

    def test_una_compra_sin_numero_valido_detiene_el_anexo(self):
        """El listado sale entero: de uno en uno obligaria a regenerar el anexo
        tantas veces como facturas defectuosas haya."""
        wizard = self._wizard()
        broken = self.env["account.move"].new({
            "l10n_latam_document_number": "SIN-FORMATO"})
        with self.assertRaises(UserError) as capture:
            wizard._l10n_ec_check_numbers(broken)
        self.assertIn("001-001-000000001", str(capture.exception))

    def test_la_autorizacion_es_la_clave_de_acceso(self):
        """Anexo 2: en el esquema offline el numero de autorizacion ES la clave."""
        invoice = self._invoice("in_invoice", self.supplier, self.purchase_journal,
                                self.tax_purchase, number="002-005-000000001")
        root = etree.fromstring(self._wizard().generate_xml())
        self.assertEqual(
            root.find(".//detalleCompras").findtext("autorizacion"),
            invoice.l10n_ec_sri_access_key,
        )


@tagged("post_install", "-at_install", "l10n_ec", "regulatory")
class TestAtsBases(TestAtsCommon):
    """Las bases salen del mismo resolutor que el XML, no del nombre del grupo."""

    def test_una_venta_gravada_va_a_baseImpGrav(self):
        self._invoice("out_invoice", self.customer, self.sale_journal,
                      self.tax_sale, price_unit=200.0)
        sale = etree.fromstring(self._wizard().generate_xml()).find(".//detalleVentas")
        self.assertEqual(sale.findtext("baseImpGrav"), "200.00")
        self.assertEqual(sale.findtext("montoIva"), "30.00")

    def test_una_linea_sin_impuestos_no_se_declara_como_tarifa_cero(self):
        """`baseNoGraIva` iba fijo a 0.00 y lo no objeto de IVA se sumaba a la base
        imponible, que es una casilla distinta del formulario."""
        self._invoice("out_invoice", self.customer, self.sale_journal,
                      self.env["account.tax"], price_unit=50.0)
        sale = etree.fromstring(self._wizard().generate_xml()).find(".//detalleVentas")
        self.assertEqual(sale.findtext("baseNoGraIva"), "50.00")
        self.assertEqual(sale.findtext("baseImpGrav"), "0.00")

    def test_renombrar_el_grupo_de_impuestos_no_cambia_el_anexo(self):
        """La clasificacion salia de `tax_group_id.name`: renombrar el grupo hacia
        que el IVA dejara de contarse, en silencio."""
        self._invoice("out_invoice", self.customer, self.sale_journal,
                      self.tax_sale, price_unit=100.0)
        antes = etree.fromstring(self._wizard().generate_xml())
        self.tax_sale.tax_group_id.name = "Un nombre cualquiera"
        despues = etree.fromstring(self._wizard().generate_xml())
        self.assertEqual(
            antes.find(".//detalleVentas").findtext("montoIva"),
            despues.find(".//detalleVentas").findtext("montoIva"),
        )

    def test_las_notas_de_credito_entran_en_el_anexo(self):
        """El filtro era `out_invoice` a secas: una devolucion no se declaraba y las
        ventas del periodo salian infladas."""
        invoice = self._invoice("out_invoice", self.customer, self.sale_journal,
                                self.tax_sale)
        note = invoice._reverse_moves([{
            "invoice_date": invoice.invoice_date,
            "journal_id": self.sale_journal.id,
            "l10n_latam_document_type_id": self.env.ref("l10n_ec.ec_dt_04").id,
        }])
        note.l10n_ec_modification_reason = "Devolucion"
        note.action_post()
        note.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(note)

        codes = [
            node.findtext("tipoComprobante")
            for node in etree.fromstring(self._wizard().generate_xml())
            .findall(".//detalleVentas")
        ]
        self.assertIn("04", codes, "la nota de credito debe declararse")


@tagged("post_install", "-at_install", "l10n_ec", "regulatory")
class TestAtsPartyFlags(TestAtsCommon):

    def test_parte_relacionada_sale_del_contacto(self):
        """La plantilla escribia `<parteRelVentas>NO</parteRelVentas>` para todos,
        ignorando el campo `l10n_ec_related_party` que ya existia."""
        self.customer.l10n_ec_related_party = True
        self._invoice("out_invoice", self.customer, self.sale_journal, self.tax_sale)
        sale = etree.fromstring(self._wizard().generate_xml()).find(".//detalleVentas")
        self.assertEqual(sale.findtext("parteRelVentas"), "SI")

    def test_el_establecimiento_sale_del_diario(self):
        """`company.l10n_ec_entity` ni siquiera existe como campo: se leia con
        `or '001'`, asi que toda empresa declaraba sus ventas al establecimiento
        001."""
        self._invoice("out_invoice", self.customer, self.sale_journal, self.tax_sale)
        establishment = etree.fromstring(
            self._wizard().generate_xml()).find(".//ventaEst")
        self.assertEqual(establishment.findtext("codEstab"), "002")
