# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Guía de remisión electrónica (codDoc 06) — Anexo 3 de la Ficha 2.34.

Este módulo NO tenía tests. Por eso convivían cuatro fallos que hacían imposible
emitir una sola guía, y ninguno se manifestaba al instalar: todos esperaban a que
alguien pulsara el botón.
"""
from lxml import etree

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestGuiaRemision(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({
            "vat": "1791251237001",
            "street": "Av. Amazonas y Naciones Unidas",
            "l10n_ec_sri_environment": "test",
        })

        # El establecimiento y el punto de emisión salen del diario, que es lo único
        # que el SRI valida contra los establecimientos registrados en el RUC.
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "sale")], limit=1
        ) or cls.env["account.journal"].create({
            "name": "Guías de prueba", "code": "GUIP", "type": "sale",
            "company_id": cls.company.id,
        })
        cls.journal.write({"l10n_ec_entity": "003", "l10n_ec_emission": "004"})
        cls.company.l10n_ec_guia_journal_id = cls.journal

        cls.driver = cls.env["l10n_ec.driver"].create({
            "name": "Juan Pérez",
            "identification_type": "cedula",
            "identification_number": "1710034065",
            "license_number": "LIC-99999",
        })
        cls.vehicle = cls.env["l10n_ec.vehicle"].create({
            "name": "Camión 01", "license_plate": "PCM4567",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "Cliente Destinatario",
            "vat": "1791251237001",
            "street": "Calle Destino 123",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Producto de prueba", "default_code": "PRD-001",
        })

    def _make_picking(self, **overrides):
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "=", self.company.id)], limit=1
        )
        values = {
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": picking_type.default_location_dest_id.id,
            "l10n_ec_driver_id": self.driver.id,
            "l10n_ec_vehicle_id": self.vehicle.id,
            "l10n_ec_route": "Quito - Ambato vía Panamericana",
            # Sin `name`: `stock.move` ya no lo tiene en Odoo 19.
            "move_ids": [(0, 0, {
                "product_id": self.product.id,
                "product_uom_qty": 3.0,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": picking_type.default_location_dest_id.id,
            })],
        }
        values.update(overrides)
        return self.env["stock.picking"].create(values)

    def test_la_plantilla_existe_con_el_xmlid_correcto(self):
        """El render apuntaba a `l10n_ec_stock.l10n_ec_guia_xml`, del nombre viejo.

        Como el XMLID sólo aparecía en Python y nunca como `ref=` en un XML, el módulo
        instalaba sin quejarse y sólo reventaba al pulsar "Enviar al SRI".
        """
        self.assertTrue(
            self.env.ref("l10n_ec_guia_remision.l10n_ec_guia_xml", raise_if_not_found=False),
            "La plantilla de la guía tiene que resolver por su XMLID actual",
        )

    def test_el_06_esta_registrado_en_el_dispatcher(self):
        renderers = self.env["l10n_ec.sri.xml"]._get_document_renderers()
        self.assertIn("06", renderers)
        template, method = renderers["06"]
        self.assertEqual(template, "l10n_ec_guia_remision.l10n_ec_guia_xml")
        self.assertTrue(hasattr(self.env["l10n_ec.sri.xml"], method))

    def test_estab_y_pto_salen_del_diario_no_de_001(self):
        """Antes se cableaba `001`/`001` y se inventaba el punto de emisión."""
        picking = self._make_picking()
        components = picking._l10n_ec_sri_components()

        self.assertEqual(components["establishment"], "003")
        self.assertEqual(components["emission_point"], "004")
        self.assertEqual(components["document_code"], "06")

    def test_el_numero_se_formatea_y_no_sale_del_albaran(self):
        """`WH/OUT/00001` es un contador por almacén: colisiona entre almacenes."""
        picking = self._make_picking()
        numero = picking._l10n_ec_assign_guia_number()

        self.assertRegex(numero, r"^003-004-\d{9}$")
        self.assertNotIn("WH", numero)

    def test_la_clave_de_acceso_es_determinista(self):
        """§5.10: un reenvío usa la MISMA clave.

        `AccessKey.generate` rellenaba el código numérico con `random.randint`, así
        que cada reintento producía otra clave y duplicaba el comprobante en el SRI.
        """
        picking = self._make_picking()
        picking._generate_access_key()
        primera = picking.l10n_ec_sri_access_key

        picking.l10n_ec_sri_access_key = False
        picking._generate_access_key()

        self.assertEqual(len(primera), 49)
        self.assertTrue(primera.isdigit())
        self.assertEqual(primera, picking.l10n_ec_sri_access_key)

    def test_sin_diario_de_guias_falla_con_mensaje_claro(self):
        self.company.l10n_ec_guia_journal_id = False
        picking = self._make_picking()
        picking.picking_type_id.l10n_ec_guia_journal_id = False

        with self.assertRaises(UserError):
            picking._l10n_ec_sri_components()

    def test_el_xml_lleva_los_tags_obligatorios(self):
        picking = self._make_picking()
        picking._generate_access_key()
        xml = self.env["l10n_ec.sri.xml"].render_xml(picking)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertEqual(root.tag, "guiaRemision")
        self.assertEqual(root.get("version"), "1.1.0")
        self.assertEqual(root.findtext(".//codDoc"), "06")
        for tag in ("obligadoContabilidad", "ruta", "placa",
                    "fechaIniTransporte", "fechaFinTransporte"):
            self.assertIsNotNone(
                root.find(".//%s" % tag), "Falta <%s> en la guía" % tag
            )

    def test_el_transportista_va_con_su_identificacion_no_con_la_licencia(self):
        """`<rucTransportista>` emitía `license_number`, que es la licencia."""
        picking = self._make_picking()
        picking._generate_access_key()
        xml = self.env["l10n_ec.sri.xml"].render_xml(picking)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertEqual(root.findtext(".//rucTransportista"), "1710034065")
        self.assertEqual(root.findtext(".//tipoIdentificacionTransportista"), "05")

    def test_la_cantidad_lleva_seis_decimales(self):
        """La versión 1.1.0 admite 6 decimales; se emitían 2."""
        picking = self._make_picking()
        picking._generate_access_key()
        xml = self.env["l10n_ec.sri.xml"].render_xml(picking)
        root = etree.fromstring(xml.encode("utf-8"))

        cantidad = root.findtext(".//detalle/cantidad")
        self.assertRegex(cantidad, r"^\d+\.\d{6}$")

    def test_el_detalle_usa_codigoInterno(self):
        picking = self._make_picking()
        picking._generate_access_key()
        xml = self.env["l10n_ec.sri.xml"].render_xml(picking)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertIsNotNone(root.find(".//detalle/codigoInterno"))
        self.assertIsNone(root.find(".//detalle/codigoPrincipal"))

    def test_sin_ruta_no_se_emite(self):
        picking = self._make_picking(l10n_ec_route=False)
        with self.assertRaises(UserError):
            self.env["l10n_ec.sri.xml"].render_xml(picking)

    def test_la_clave_y_el_cuerpo_no_pueden_discrepar(self):
        """Estab, ptoEmi y secuencial del XML tienen que ser los de la clave."""
        picking = self._make_picking()
        picking._generate_access_key()
        xml = self.env["l10n_ec.sri.xml"].render_xml(picking)
        root = etree.fromstring(xml.encode("utf-8"))
        clave = picking.l10n_ec_sri_access_key

        self.assertEqual(root.findtext(".//estab"), clave[24:27])
        self.assertEqual(root.findtext(".//ptoEmi"), clave[27:30])
        self.assertEqual(root.findtext(".//secuencial"), clave[30:39])
        self.assertEqual(root.findtext(".//codDoc"), clave[8:10])
