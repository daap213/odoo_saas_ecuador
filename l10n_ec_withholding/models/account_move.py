# -*- coding: utf-8 -*-
from odoo import models

# NOTA: aquí había una redefinición de `l10n_ec_sustento_code` como fields.Char.
# El campo ya lo declara l10n_ec_edi/models/account_move.py como fields.Selection
# con los códigos 01..07 de la tabla del SRI. Como l10n_ec_withholding depende de
# l10n_ec_edi y se carga después, el Char ganaba en silencio y convertía un campo
# de vocabulario controlado en texto libre — con la vista de abajo marcándolo
# `required` en toda factura de proveedor, y el ATS perdiendo la validación.
# El campo se hereda; no hay que redeclararlo.


class AccountMove(models.Model):
    _inherit = "account.move"
