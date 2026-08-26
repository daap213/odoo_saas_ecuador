# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Comprobantes electronicos del punto de venta.

El modulo no tenia ni un test, y generaba las claves de acceso con
`AccessKey.generate`, que rellena el codigo numerico con `random.randint`: el mismo
fallo que `l10n_ec_sri` y `l10n_ec_guia_remision` documentan haber eliminado.
"""
from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


class PosSriCommon(TransactionCase):

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
        })
        cls.env["account.chart.template"].try_loading(
            "ec", cls.company, install_demo=False
        )
        cls.journal = cls.env["account.journal"].create({
            "name": "Caja 002-004",
            "code": "POS24",
            "type": "sale",
            "company_id": cls.company.id,
            "l10n_ec_entity": "002",
            "l10n_ec_emission": "004",
        })
        cls.config = cls.env["pos.config"].create({
            "name": "Caja de prueba SRI",
            "company_id": cls.company.id,
            "l10n_ec_sri_active": True,
            "l10n_ec_journal_id": cls.journal.id,
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "CLIENTE POS S.A.",
            "vat": "1791251237001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.session = cls.env["pos.session"].create({
            "config_id": cls.config.id,
            "user_id": cls.env.user.id,
        })

    def _order(self, amount=115.0):
        return self.env["pos.order"].create({
            "session_id": self.session.id,
            "company_id": self.company.id,
            "partner_id": self.partner.id,
            "date_order": fields.Datetime.to_datetime("2026-08-25 10:00:00"),
            "amount_total": amount,
            "amount_tax": 15.0,
            "amount_paid": amount,
            "amount_return": 0.0,
        })


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestPosAccessKey(PosSriCommon):

    def test_la_clave_tiene_49_digitos(self):
        order = self._order()
        key = order.l10n_ec_sri_access_key
        self.assertTrue(key, "el pedido debe salir con clave de acceso")
        self.assertEqual(len(key), 49)
        self.assertTrue(key.isdigit())

    def test_la_clave_es_determinista(self):
        """Con `random.randint` cada recalculo daba una clave distinta y el
        comprobante se duplicaba en el SRI. La Ficha 5.10 exige la misma."""
        order = self._order()
        first = order.l10n_ec_sri_access_key
        order.l10n_ec_sri_access_key = False
        order._generate_pos_access_key()
        self.assertEqual(order.l10n_ec_sri_access_key, first)

    def test_el_establecimiento_sale_del_diario_no_de_un_001_fijo(self):
        order = self._order()
        key = order.l10n_ec_sri_access_key
        self.assertEqual(key[24:27], "002", "establecimiento del diario")
        self.assertEqual(key[27:30], "004", "punto de emision del diario")

    def test_la_clave_y_el_numero_describen_el_mismo_comprobante(self):
        order = self._order()
        establishment, emission, sequential = (
            order.l10n_ec_document_number.split("-")
        )
        key = order.l10n_ec_sri_access_key
        self.assertEqual(key[24:27], establishment)
        self.assertEqual(key[27:30], emission)
        self.assertEqual(key[30:39], sequential)

    def test_el_secuencial_no_sale_de_filtrar_digitos_de_la_referencia(self):
        """Se sacaba de `pos_reference` quedandose con los nueve ultimos digitos:
        dos cajas o dos sesiones podian producir el mismo numero."""
        first = self._order()
        second = self._order()
        self.assertNotEqual(
            first.l10n_ec_document_number, second.l10n_ec_document_number
        )
        self.assertNotEqual(
            first.l10n_ec_sri_access_key, second.l10n_ec_sri_access_key
        )

    def test_el_ambiente_de_pruebas_es_1(self):
        """Tabla 4: 1 = pruebas, 2 = produccion."""
        self.assertEqual(self._order().l10n_ec_sri_access_key[23], "1")

    def test_produccion_es_2(self):
        self.company.l10n_ec_sri_environment = "production"
        self.assertEqual(self._order().l10n_ec_sri_access_key[23], "2")

    def test_el_tipo_de_comprobante_es_factura(self):
        self.assertEqual(self._order().l10n_ec_sri_access_key[8:10], "01")


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestPosConfiguration(PosSriCommon):

    def test_una_caja_sin_diario_no_se_puede_guardar(self):
        """Descubrirlo con el cliente delante es el momento en que no se puede
        resolver, asi que se comprueba al configurar."""
        with self.assertRaises(ValidationError):
            self.env["pos.config"].create({
                "name": "Caja sin diario",
                "company_id": self.company.id,
                "l10n_ec_sri_active": True,
            })

    def test_un_diario_sin_establecimiento_tampoco(self):
        incomplete = self.env["account.journal"].create({
            "name": "Diario incompleto",
            "code": "INCP",
            "type": "sale",
            "company_id": self.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env["pos.config"].create({
                "name": "Caja con diario incompleto",
                "company_id": self.company.id,
                "l10n_ec_sri_active": True,
                "l10n_ec_journal_id": incomplete.id,
            })

    def test_sin_facturacion_electronica_no_se_exige_diario(self):
        config = self.env["pos.config"].create({
            "name": "Caja sin SRI",
            "company_id": self.company.id,
            "l10n_ec_sri_active": False,
        })
        self.assertFalse(config.l10n_ec_journal_id)

    def test_el_establecimiento_se_lee_del_diario(self):
        """Eran dos campos de texto con default '001'."""
        self.assertEqual(self.config.l10n_ec_entity, "002")
        self.assertEqual(self.config.l10n_ec_emission_point, "004")
        field = self.env["pos.config"]._fields["l10n_ec_entity"]
        self.assertTrue(field.related, "debe venir del diario, no teclearse")

    def test_un_fallo_de_configuracion_no_impide_cobrar(self):
        """En una caja, detener la venta por un dato de configuracion es peor que
        emitir el comprobante con retraso."""
        self.config.l10n_ec_journal_id.l10n_ec_entity = False
        order = self._order()
        self.assertFalse(order.l10n_ec_sri_access_key)
        self.assertTrue(order.id, "el pedido se registra igual")
