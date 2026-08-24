# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    """Cálculo del ICE ecuatoriano sobre el motor de impuestos de Odoo 19.

    Antes este archivo sobrescribía `_compute_amount`, método que Odoo 19 ELIMINÓ.
    Al no existir ya en la clase padre, el override no lo llamaba nadie y el ICE
    simplemente no se aplicaba: un impuesto que desaparecía en silencio.

    La API nueva evalúa cada impuesto en tres pasadas, y la que corresponde depende
    del `amount_type`:
      - `_eval_tax_amount_fixed_amount`   -> impuestos 'fixed'   (ICE específico)
      - `_eval_tax_amount_price_excluded` -> impuestos 'percent' (ICE ad valorem)
      - `_eval_tax_amount_price_included` -> precio con impuesto incluido

    Por eso cada tipo de categoría ICE exige un `amount_type` concreto en el
    impuesto, y así el override sólo actúa en la pasada correcta. La tarifa sigue
    viniendo de la categoría (`l10n_ec.ice.category`), que es el dato que publica
    el SRI, y no del campo `amount` del impuesto.
    """

    _inherit = "account.tax"

    l10n_ec_ice_category_id = fields.Many2one(
        "l10n_ec.ice.category", string="ICE Category (SRI)"
    )

    def _is_l10n_ec_ice(self):
        """True si este impuesto es un ICE ecuatoriano configurado."""
        self.ensure_one()
        return bool(
            self.l10n_ec_ice_category_id
            and (not self.country_id or self.country_id.code == "EC")
        )

    @api.constrains("l10n_ec_ice_category_id", "amount_type")
    def _check_l10n_ec_ice_amount_type(self):
        """El amount_type decide en qué pasada se evalúa: si no cuadra con el tipo
        de ICE, el override nunca se ejecuta y el impuesto vuelve a calcularse mal
        en silencio. Mejor impedirlo al configurar."""
        expected = {
            "specific": "fixed",
            "specific_content": "fixed",
            "ad_valorem": "percent",
        }
        for tax in self:
            category = tax.l10n_ec_ice_category_id
            if not category:
                continue
            needed = expected.get(category.type)
            if needed and tax.amount_type != needed:
                raise ValidationError(
                    _(
                        "El impuesto ICE '%(tax)s' usa la categoría '%(cat)s' (tipo "
                        "%(ctype)s), que exige 'Tipo de importe' = %(needed)s, pero "
                        "tiene %(actual)s. Con otro valor el ICE no se calcularía.",
                        tax=tax.display_name,
                        cat=category.display_name,
                        ctype=category.type,
                        needed=needed,
                        actual=tax.amount_type,
                    )
                )

    def _eval_taxes_computation_prepare_product_fields(self):
        """Pide al motor que exponga este campo del producto dentro de
        `evaluation_context['product']`. El core devuelve un set() vacío y existe
        justo para que los módulos añadan lo que necesiten: el contexto no lleva el
        registro del producto, sólo un diccionario con los campos declarados aquí.
        """
        return super()._eval_taxes_computation_prepare_product_fields() | {
            "l10n_ec_ice_unit_content"
        }

    def _eval_tax_amount_fixed_amount(self, batch, raw_base, evaluation_context):
        """ICE específico: importe fijo por unidad, y para alcohol/azúcar
        multiplicado además por el contenido del producto."""
        self.ensure_one()
        category = self.l10n_ec_ice_category_id
        if (
            self._is_l10n_ec_ice()
            and category.type in ("specific", "specific_content")
            and self.amount_type == "fixed"
        ):
            sign = -1 if evaluation_context["price_unit"] < 0.0 else 1
            content = 1.0
            if category.type == "specific_content":
                content = (
                    evaluation_context["product"].get("l10n_ec_ice_unit_content") or 1.0
                )
            return sign * evaluation_context["quantity"] * content * category.specific_rate
        return super()._eval_tax_amount_fixed_amount(batch, raw_base, evaluation_context)

    def _eval_tax_amount_price_excluded(self, batch, raw_base, evaluation_context):
        """ICE ad valorem: porcentaje sobre la base, tomando la tarifa de la
        categoría en lugar del campo `amount` del impuesto."""
        self.ensure_one()
        category = self.l10n_ec_ice_category_id
        if (
            self._is_l10n_ec_ice()
            and category.type == "ad_valorem"
            and self.amount_type == "percent"
        ):
            return raw_base * category.ad_valorem_rate / 100.0
        return super()._eval_tax_amount_price_excluded(
            batch, raw_base, evaluation_context
        )
