# -*- coding: utf-8 -*-
from odoo.tests import common, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install")
class TestEcIdentity(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestEcIdentity, cls).setUpClass()
        cls.ec = cls.env.ref("base.ec")

    def test_valid_ruc_natural(self):
        """Test valid RUC Natural (13 digits, ends in 001)"""
        partner = self.env["res.partner"].create(
            {
                "name": "Valid RUC Natural",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "ruc",
                "vat": "1710034065001",  # 1710034065 is valid cedula
            }
        )
        self.assertTrue(partner)

    def test_valid_ruc_private(self):
        """Test valid RUC Private (3rd digit 9)"""
        # Example: 1790016919001 (Corporación Favorita approx, strictly need valid mod11)
        # Using a known valid generator output or mocking just the Mod11 logic if needed.
        # Let's use 1791251237001 (Valid Public/Private)
        partner = self.env["res.partner"].create(
            {
                "name": "Valid RUC Private",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "ruc",
                "vat": "1791251237001",
            }
        )
        self.assertTrue(partner)

    def test_valid_cedula(self):
        """Test valid Cedula (10 digits)"""
        partner = self.env["res.partner"].create(
            {
                "name": "Valid Cedula",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "cedula",
                "vat": "1710034065",
            }
        )
        self.assertTrue(partner)

    def test_invalid_length(self):
        """Test invalid length RUC"""
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Invalid Length",
                    "country_id": self.ec.id,
                    "l10n_ec_identifier_type": "ruc",
                    "vat": "123",
                }
            )

    def test_invalid_mod10(self):
        """Test invalid Modulo 10 Check Digit"""
        with self.assertRaises(ValidationError):
            self.env["res.partner"].create(
                {
                    "name": "Invalid Check Digit",
                    "country_id": self.ec.id,
                    "l10n_ec_identifier_type": "cedula",
                    "vat": "1710034069",  # Last digit modified
                }
            )

    def test_pasaporte(self):
        """Pasaporte accepts alphanumeric > 5 chars.

        En Odoo 19 no basta con l10n_ec_identifier_type: base_vat valida `vat`
        contra el formato del país y rechaza un pasaporte si el partner no declara
        un l10n_latam.identification.type marcado como NO-VAT. Sin ese campo, crear
        un partner extranjero con pasaporte falla con ValidationError de base_vat,
        que es lo que ocurría aquí.
        """
        # Se usa el tipo de Ecuador si el l10n_ec oficial está instalado (lo hace
        # solo: declara auto_install sobre `account`), y si no el genérico de
        # l10n_latam_base. No vale buscar por is_vat=False sin más: eso también
        # devuelve "Citizenship", que exige 10 dígitos y vuelve a fallar.
        passport_type = self.env.ref(
            "l10n_ec.ec_passport", raise_if_not_found=False
        ) or self.env.ref("l10n_latam_base.it_pass")
        partner = self.env["res.partner"].create(
            {
                "name": "Foreigner",
                "country_id": self.ec.id,
                "l10n_ec_identifier_type": "pasaporte",
                "l10n_latam_identification_type_id": passport_type.id,
                "vat": "PASS123456",
            }
        )
        self.assertTrue(partner)
