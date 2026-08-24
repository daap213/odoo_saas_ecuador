# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ec_ice")
class TestICECalculation(TransactionCase):
    """Cálculo del ICE sobre el motor de impuestos de Odoo 19.

    Reescrito por dos motivos:

    1. Usaba `account.tax.compute_all()`, eliminado en Odoo 19. La API nueva es
       `_prepare_base_line_for_taxes_computation` -> `_add_tax_details_in_base_line`,
       y el resultado vive en base_line["tax_details"]["taxes_data"].
    2. Creaba categorías ICE con los códigos 3031 / 3680 / 3072, que YA existen en
       data/l10n_ec.ice.category.csv. Mientras la restricción de unicidad se ignoraba
       (era `_sql_constraints`) eso pasaba desapercibido; ahora es un
       `models.Constraint` real y duplicarlas rompe el setUpClass. Se reutilizan las
       categorías sembradas, que además ya traen las tarifas oficiales.

    También se corrige `amount_type`: el original usaba "code", que ni siquiera es un
    valor válido de la selección (group / fixed / percent / division). El amount_type
    decide en qué pasada evalúa el motor cada impuesto, así que tiene que casar con el
    tipo de categoría ICE.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.country_id = cls.env.ref("base.ec")
        ecuador = cls.env.ref("base.ec")

        # Categorías sembradas por el módulo (no se recrean).
        cls.ice_alcohol = cls.env.ref("l10n_ec_ice.ice_3031")  # specific_content 10.30
        cls.ice_plastic = cls.env.ref("l10n_ec_ice.ice_3680")  # specific 0.08
        cls.ice_perfume = cls.env.ref("l10n_ec_ice.ice_3072")  # ad_valorem 20 %

        Tax = cls.env["account.tax"]
        cls.tax_ice_alcohol = Tax.create({
            "name": "ICE Alcohol 3031",
            "amount_type": "fixed",
            "amount": 0.0,  # la tarifa la aporta la categoría
            "l10n_ec_ice_category_id": cls.ice_alcohol.id,
            "country_id": ecuador.id,
        })
        cls.tax_ice_plastic = Tax.create({
            "name": "ICE Fundas 3680",
            "amount_type": "fixed",
            "amount": 0.0,
            "l10n_ec_ice_category_id": cls.ice_plastic.id,
            "country_id": ecuador.id,
        })
        cls.tax_ice_perfume = Tax.create({
            "name": "ICE Perfumes 3072",
            "amount_type": "percent",
            "amount": 0.0,
            "l10n_ec_ice_category_id": cls.ice_perfume.id,
            "country_id": ecuador.id,
        })

        Product = cls.env["product.product"]
        cls.product_whisky = Product.create({
            "name": "Whisky 750ml 40%",
            "l10n_ec_ice_category_id": cls.ice_alcohol.id,
            "l10n_ec_ice_unit_content": 0.30,  # 0.75 L * 40 % = 0.30 L puros
            "list_price": 50.00,
        })
        cls.product_bag = Product.create({
            "name": "Funda plástica",
            "l10n_ec_ice_category_id": cls.ice_plastic.id,
        })
        cls.product_perfume = Product.create({
            "name": "Perfume 100ml",
            "l10n_ec_ice_category_id": cls.ice_perfume.id,
        })

    def _ice_amount(self, tax, product, quantity, price_unit):
        """Importe del impuesto según el motor real de Odoo 19."""
        AccountTax = self.env["account.tax"]
        base_line = AccountTax._prepare_base_line_for_taxes_computation(
            None,
            price_unit=price_unit,
            quantity=quantity,
            product_id=product,
            tax_ids=tax,
            # Sin moneda explícita el redondeo queda a 0 y el motor lanza
            # "precision_rounding must be positive".
            currency_id=self.company.currency_id,
        )
        AccountTax._add_tax_details_in_base_line(base_line, self.company)
        return sum(
            data["tax_amount"] for data in base_line["tax_details"]["taxes_data"]
        )

    def test_ice_specific_content_alcohol(self):
        """Alcohol: cantidad x litros puros x tarifa = 10 * 0.30 * 10.30 = 30.90."""
        amount = self._ice_amount(
            self.tax_ice_alcohol, self.product_whisky, quantity=10, price_unit=50.0
        )
        self.assertAlmostEqual(amount, 30.90, places=2)

    def test_ice_missing_content_defaults_to_one(self):
        """Sin contenido declarado el factor es 1.0: 1 * 1.0 * 10.30 = 10.30."""
        product_simple = self.env["product.product"].create({
            "name": "Alcohol sin contenido",
            "l10n_ec_ice_category_id": self.ice_alcohol.id,
        })
        amount = self._ice_amount(
            self.tax_ice_alcohol, product_simple, quantity=1, price_unit=100.0
        )
        self.assertAlmostEqual(amount, 10.30, places=2)

    def test_ice_specific_per_unit(self):
        """Fundas plásticas: cantidad x tarifa fija = 100 * 0.08 = 8.00."""
        amount = self._ice_amount(
            self.tax_ice_plastic, self.product_bag, quantity=100, price_unit=0.10
        )
        self.assertAlmostEqual(amount, 8.00, places=2)

    def test_ice_ad_valorem(self):
        """Perfumes: 20 % sobre la base = 2 * 150 * 20 % = 60.00."""
        amount = self._ice_amount(
            self.tax_ice_perfume, self.product_perfume, quantity=2, price_unit=150.0
        )
        self.assertAlmostEqual(amount, 60.00, places=2)

    def test_amount_type_must_match_category(self):
        """La restricción impide configurar un ICE con el amount_type equivocado."""
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.env["account.tax"].create({
                "name": "ICE mal configurado",
                "amount_type": "percent",  # la categoría es 'specific' -> exige 'fixed'
                "l10n_ec_ice_category_id": self.ice_plastic.id,
                "country_id": self.env.ref("base.ec").id,
            })
