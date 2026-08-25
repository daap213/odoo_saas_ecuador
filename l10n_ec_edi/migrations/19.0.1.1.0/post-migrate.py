# -*- coding: utf-8 -*-
"""Vacía las URL de los web services que quedaron clavadas en el ambiente de pruebas.

`res.company.l10n_ec_sri_reception_url` / `..._authorization_url` se declaraban con
`default=` apuntando a `celcer` (pruebas). Odoo escribe el default en TODAS las
compañías al crear el campo, así que el override manual estaba siempre relleno — y
`l10n_ec.sri.service._get_service_url` le da precedencia sobre el selector de
ambiente. Resultado: poner la compañía en producción no cambiaba el endpoint y los
comprobantes seguían yendo a `celcer`.

Los `default=` ya no existen. Aquí se limpia lo que dejaron: si el valor guardado es
exactamente una de las URL oficiales, se vacía para que lo resuelva el ambiente. Un
valor distinto es un override deliberado del cliente y NO se toca.

Se ejecuta en `post` porque necesita la columna ya migrada.
"""
import logging

_logger = logging.getLogger(__name__)

# Las cuatro URL oficiales de la Ficha §7.2. Cualquiera de ellas guardada en el
# campo es un vestigio del default (o una copia literal del mismo endpoint que el
# ambiente ya resuelve): en ambos casos, vaciar es correcto.
_SRI_URLS = (
    "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
)


def migrate(cr, version):
    if not version:
        return

    for column in ("l10n_ec_sri_reception_url", "l10n_ec_sri_authorization_url"):
        cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'res_company' AND column_name = %s
            """,
            [column],
        )
        if not cr.fetchone():
            continue

        cr.execute(
            f"UPDATE res_company SET {column} = NULL WHERE {column} = ANY(%s)",
            [list(_SRI_URLS)],
        )
        if cr.rowcount:
            _logger.info(
                "l10n_ec_edi: %s compañías vuelven a resolver %s por ambiente.",
                cr.rowcount,
                column,
            )
