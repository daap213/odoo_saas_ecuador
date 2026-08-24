# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import ValidationError


class AccountTax(models.Model):
    """Código SRI de retención sobre el impuesto.

    La plantilla del comprobante de retención ya leía `tax_id.l10n_ec_code` para
    emitir <codigoRetencion>, pero el campo no existía en ninguna parte del repo:
    renderizar una retención lanzaba AttributeError.

    Corresponde a los códigos de las tablas 19 (impuesto a retener), 20 (retención
    de IVA e ISD) y a los códigos de retención de renta del Catálogo ATS, que la
    Ficha no enumera y delega en la normativa vigente.
    """

    _inherit = "account.tax"

    l10n_ec_code = fields.Char(
        string="Código de Retención SRI",
        size=10,
        index="btree_not_null",
        help="Código con el que el SRI identifica esta retención: <codigoRetencion> "
             "del comprobante. Ej.: 303 (honorarios), 312 (bienes), 1 (IVA 30%).",
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

    def l10n_ec_get_retention_code(self):
        """Código de retención, exigiendo que esté configurado.

        Antes la plantilla caía a '000' cuando faltaba, lo que produce un comprobante
        que el SRI rechaza sin explicar por qué. Es preferible fallar al emitir.
        """
        self.ensure_one()
        if not self.l10n_ec_code:
            raise ValidationError(_(
                "El impuesto de retención '%s' no tiene código SRI configurado.\n\n"
                "Asígnelo en Contabilidad > Configuración > Impuestos, campo "
                "'Código de Retención SRI'.", self.display_name,
            ))
        return self.l10n_ec_code
