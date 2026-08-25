# -*- coding: utf-8 -*-
"""Asigna diario a las retenciones existentes y renumera las que aún no se emitieron.

`l10n_ec.retention` no tenía `journal_id`, así que el generador del XML no encontraba
de dónde sacar el establecimiento y el punto de emisión y caía a un `001-001` fijo.
Ahora salen del diario, que es lo que el SRI valida contra los establecimientos
registrados en el RUC.

Dos cosas aquí:

1. Rellenar `journal_id` en todo registro existente. El campo NO se declara
   `required=True` en esta versión a propósito: si una compañía no tiene ningún diario
   con los dos códigos SRI, es mejor dejar el campo vacío —y que el usuario elija— que
   asignarle un diario cuyo punto de emisión no exista en su RUC, que es exactamente el
   fallo que se está corrigiendo.
2. Renumerar `name` al formato `001-001-000000001` **sólo** en las retenciones que
   todavía no se han enviado. Una retención ya transmitida conserva su número: el que
   viaja en su clave de acceso y el que el SRI tiene registrado. Cambiarlo produciría
   un comprobante que no cuadra con lo autorizado.
"""
import logging
import re

_logger = logging.getLogger(__name__)

_NUMBER_RE = re.compile(r"^(\d{3})-(\d{3})-(\d{9})$")


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        [table, column],
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return
    if not _column_exists(cr, "l10n_ec_retention", "journal_id"):
        _logger.warning("l10n_ec_sri: no existe l10n_ec_retention.journal_id; se omite.")
        return

    # Un diario por compañía: el primero de venta/misceláneo que tenga los dos
    # códigos SRI. Si una compañía no tiene ninguno, sus retenciones se quedan sin
    # diario y el usuario tendrá que elegirlo a mano — mejor eso que asignar uno
    # cuyo punto de emisión no exista en el RUC.
    cr.execute(
        """
        SELECT DISTINCT ON (company_id) company_id, id
        FROM account_journal
        WHERE type IN ('sale', 'general')
          AND l10n_ec_entity IS NOT NULL AND l10n_ec_entity <> ''
          AND l10n_ec_emission IS NOT NULL AND l10n_ec_emission <> ''
        ORDER BY company_id, id
        """
    )
    journal_by_company = dict(cr.fetchall())
    if not journal_by_company:
        _logger.warning(
            "l10n_ec_sri: ninguna compañía tiene un diario con establecimiento y "
            "punto de emisión SRI. Las retenciones existentes quedan sin diario."
        )
        return

    for company_id, journal_id in journal_by_company.items():
        cr.execute(
            "UPDATE l10n_ec_retention SET journal_id = %s "
            "WHERE company_id = %s AND journal_id IS NULL",
            [journal_id, company_id],
        )
        if cr.rowcount:
            _logger.info(
                "l10n_ec_sri: %s retenciones de la compañía %s apuntan al diario %s.",
                cr.rowcount, company_id, journal_id,
            )

    # Renumerar sólo lo que nunca salió hacia el SRI.
    cr.execute(
        """
        SELECT r.id, r.name, j.l10n_ec_entity, j.l10n_ec_emission
        FROM l10n_ec_retention r
        JOIN account_journal j ON j.id = r.journal_id
        WHERE COALESCE(r.l10n_ec_sri_status, 'draft') IN ('draft', 'rejected')
          AND r.l10n_ec_sri_access_key IS NULL
        """
    )
    renamed = 0
    for retention_id, name, entity, emission in cr.fetchall():
        if _NUMBER_RE.match((name or "").strip()):
            continue
        digits = re.sub(r"\D", "", name or "")
        if not digits:
            continue
        new_name = "{}-{}-{}".format(
            (entity or "").strip().zfill(3),
            (emission or "").strip().zfill(3),
            digits[-9:].zfill(9),
        )
        cr.execute(
            "UPDATE l10n_ec_retention SET name = %s WHERE id = %s",
            [new_name, retention_id],
        )
        renamed += 1

    if renamed:
        _logger.info("l10n_ec_sri: %s retenciones renumeradas a estab-ptoEmi-seq.", renamed)
