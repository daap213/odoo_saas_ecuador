# -*- coding: utf-8 -*-
"""Códigos SRI de retención sobre `account.tax` — Ficha Técnica 2.34, tablas 19 y 20.

Este módulo es la ÚNICA fuente de los códigos que salen en el comprobante de
retención. Antes había tres catálogos paralelos (`l10n_ec.retention.code` en
l10n_ec_base y `l10n_ec.withholding.tax` en l10n_ec_withholding) y la emisión no
leía ninguno de los dos: la plantilla lee `account.tax`, y ese campo estaba vacío
en todo el repo, así que ninguna retención podía emitirse.
"""
from odoo import _, fields, models
from odoo.exceptions import ValidationError

# Tabla 19 — impuesto a retener, el <codigo> del bloque <impuesto>.
L10N_EC_RETENTION_TAX_RENTA = "1"
L10N_EC_RETENTION_TAX_VAT = "2"
L10N_EC_RETENTION_TAX_ISD = "6"

# Tabla 20 — <codigoRetencion> de la retención de IVA, por porcentaje retenido.
#
# Es una tabla cerrada y autoritativa, así que el código se puede DERIVAR del
# porcentaje del impuesto sin configuración manual. Ojo con los dos ceros: el 7 es
# "retención en cero" (Disp. Transitoria Única de la Res. NAC-DGERCGC15-00000284) y
# el 8 es "no procede retención"; no son intercambiables, y el 9 —que este repo
# etiquetaba como "no procede"— es en realidad el 10 %.
L10N_EC_VAT_WITHHOLD_CODE_BY_RATE = {
    10.0: "9",
    20.0: "10",
    30.0: "1",
    50.0: "11",
    70.0: "2",
    100.0: "3",
}

# Tabla 20 — retención de ISD. El código depende de la FECHA del comprobante, no
# del porcentaje: la tabla asigna 4580 a todos los tramos históricos (del 5 % al
# 3,5 %, hasta el 31-03-2024) y 4586 al 2,5 % vigente desde el 01-05-2025.
#
# Estaba fijado a "4586", así que reemitir o corregir un comprobante de un
# período anterior lo declaraba con un código que aún no existía. El límite es
# configurable porque es una fecha de vigencia normativa, no una constante del
# formato.
L10N_EC_ISD_CODE_HISTORIC = "4580"
L10N_EC_ISD_CODE_CURRENT = "4586"
L10N_EC_ISD_CURRENT_FROM = "2025-05-01"

# Clasificación de grupos del addon oficial `l10n_ec` → impuesto de la tabla 19.
L10N_EC_GROUP_TYPE_TO_RETENTION_TAX = {
    "withhold_income_sale": L10N_EC_RETENTION_TAX_RENTA,
    "withhold_income_purchase": L10N_EC_RETENTION_TAX_RENTA,
    "withhold_vat_sale": L10N_EC_RETENTION_TAX_VAT,
    "withhold_vat_purchase": L10N_EC_RETENTION_TAX_VAT,
}


class AccountTax(models.Model):
    """Código SRI de retención sobre el impuesto.

    La plantilla del comprobante de retención lee `tax_id.l10n_ec_code` para emitir
    <codigoRetencion> y `tax_id.l10n_ec_retention_type` para <codigo>.

    Ambos se resuelven en cascada (ver `l10n_ec_get_retention_code`): primero el
    valor fijado a mano, luego lo que aporte el addon oficial `l10n_ec`, y por
    último —sólo para IVA e ISD, cuyas tablas son cerradas— derivándolo del
    porcentaje. Los códigos de renta NO son derivables: la Ficha no los enumera y
    delega en el Catálogo del ATS, así que hay que configurarlos.
    """

    _inherit = "account.tax"

    l10n_ec_code = fields.Char(
        string="Código de Retención SRI",
        size=10,
        index="btree_not_null",
        help="Código con el que el SRI identifica esta retención: <codigoRetencion> "
             "del comprobante. Ej.: 303 (honorarios), 312 (bienes), 1 (IVA 30%). "
             "Si se deja vacío, para IVA e ISD se deduce del porcentaje (tabla 20).",
    )

    l10n_ec_retention_type = fields.Selection(
        [("1", "Renta"), ("2", "IVA"), ("6", "ISD")],
        string="Impuesto a Retener (SRI)",
        help="Tabla 19 de la Ficha Técnica: el <codigo> del bloque <impuesto> del "
             "comprobante de retención.",
    )

    _l10n_ec_code_format = models.Constraint(
        r"CHECK(l10n_ec_code IS NULL OR l10n_ec_code ~ '^[0-9A-Z]{1,10}$')",
        "El código de retención SRI debe ser alfanumérico en mayúsculas "
        "(por ejemplo 303, 343A o 3011).",
    )

    # ------------------------------------------------------------------
    # Resolución en cascada
    # ------------------------------------------------------------------

    def _l10n_ec_official_field(self, field_name):
        """Valor de un campo que aporta el addon oficial `l10n_ec`, si está.

        El oficial y este repo comparten nombre técnico de módulo, así que sólo uno
        de los dos se carga. No se puede asumir que sus campos existan.
        """
        self.ensure_one()
        if field_name in self._fields:
            return self[field_name] or False
        return False

    def _l10n_ec_resolve_retention_tax(self):
        """<codigo> de la tabla 19: 1 renta, 2 IVA, 6 ISD."""
        self.ensure_one()
        if self.l10n_ec_retention_type:
            return self.l10n_ec_retention_type
        group_type = self.tax_group_id and self.tax_group_id._l10n_ec_group_type()
        return L10N_EC_GROUP_TYPE_TO_RETENTION_TAX.get(group_type) or False

    def l10n_ec_get_retention_type(self):
        """<codigo> del bloque <impuesto>, exigiéndolo si no se puede deducir."""
        self.ensure_one()
        retention_tax = self._l10n_ec_resolve_retention_tax()
        if not retention_tax:
            raise ValidationError(_(
                "El impuesto de retención '%s' no indica qué impuesto retiene.\n\n"
                "Asígnelo en Contabilidad > Configuración > Impuestos, campo "
                "'Impuesto a Retener (SRI)': Renta, IVA o ISD (tabla 19 de la "
                "Ficha Técnica).", self.display_name,
            ))
        return retention_tax

    def _l10n_ec_isd_code(self, date=None):
        """Código de ISD vigente en `date` (tabla 20).

        Sin fecha se usa hoy, que es lo correcto para una emisión normal; la
        retención pasa la suya para que un comprobante de un período cerrado
        salga con el código que regía entonces.
        """
        threshold = self.env["ir.config_parameter"].sudo().get_param(
            "l10n_ec.isd_code_4586_from", L10N_EC_ISD_CURRENT_FROM
        )
        reference = date or fields.Date.context_today(self)
        if fields.Date.to_string(reference) >= threshold:
            return L10N_EC_ISD_CODE_CURRENT
        return L10N_EC_ISD_CODE_HISTORIC

    def l10n_ec_get_retention_code(self, date=None):
        """<codigoRetencion>, resuelto en cascada.

        Antes la plantilla caía a '000' cuando faltaba, lo que produce un comprobante
        que el SRI rechaza sin explicar por qué. Es preferible fallar al emitir.

        `date` es la fecha del comprobante, y sólo la usa el ISD, cuyo código
        cambió de 4580 a 4586 el 01-05-2025.
        """
        self.ensure_one()

        # 1. Valor fijado a mano en el impuesto: manda siempre.
        if self.l10n_ec_code:
            return self.l10n_ec_code

        # 2. Lo que traiga el addon oficial, si está instalado y lo trae.
        official = self._l10n_ec_official_field("l10n_ec_code_ats")
        if official:
            return official

        # 3. Deducción por porcentaje. Sólo IVA e ISD: sus tablas son cerradas.
        retention_tax = self._l10n_ec_resolve_retention_tax()
        rate = abs(self.amount or 0.0)
        if retention_tax == L10N_EC_RETENTION_TAX_VAT:
            derived = L10N_EC_VAT_WITHHOLD_CODE_BY_RATE.get(rate)
            if derived:
                return derived
        elif retention_tax == L10N_EC_RETENTION_TAX_ISD:
            return self._l10n_ec_isd_code(date)

        raise ValidationError(_(
            "El impuesto de retención '%(tax)s' no tiene código SRI y no se puede "
            "deducir de su porcentaje (%(rate)s%%).\n\n"
            "Asígnelo en Contabilidad > Configuración > Impuestos, campo "
            "'Código de Retención SRI'. Los códigos de retención de renta salen del "
            "Catálogo del ATS (303 honorarios, 312 bienes, 320 arriendos…); los de "
            "IVA, de la tabla 20 de la Ficha Técnica.\n\n"
            "Si el porcentaje es 0,00 %% hay que elegir a mano entre los dos "
            "códigos que comparten esa tarifa y no se pueden distinguir por ella: "
            "7 (retención en cero, Disp. Transitoria Única de la Res. "
            "NAC-DGERCGC15-00000284) y 8 (no procede retención).",
            tax=self.display_name,
            rate=("%.2f" % rate).rstrip("0").rstrip("."),
        ))


class AccountTaxGroup(models.Model):
    """Acceso tolerante a la clasificación SRI del grupo de impuestos."""

    _inherit = "account.tax.group"

    def _l10n_ec_group_type(self):
        """`l10n_ec_type` del addon oficial, o False si no está instalado."""
        self.ensure_one()
        if "l10n_ec_type" in self._fields:
            return self.l10n_ec_type or False
        return False
