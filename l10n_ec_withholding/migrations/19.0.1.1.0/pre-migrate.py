# -*- coding: utf-8 -*-
"""Traslada las retenciones de `account.retention` a `l10n_ec.retention`.

Los modelos `account.retention` / `account.retention.line` y el catálogo
`l10n_ec.withholding.tax` desaparecen en esta versión: eran una segunda
implementación del comprobante de retención que la emisión electrónica no usaba.
La ruta viva es `l10n_ec.retention` (módulo l10n_ec_sri), que sí genera clave de
acceso y XML.

Se ejecuta en `pre` porque las tablas viejas tienen que existir todavía para poder
leerlas; Odoo elimina los modelos huérfanos después, al cargar el módulo.

Es idempotente y tolera una base sin datos: si las tablas no existen (instalación
nueva) no hace nada.
"""
import logging

_logger = logging.getLogger(__name__)


def _table_exists(cr, table):
    cr.execute("SELECT to_regclass(%s)", [f"public.{table}"])
    return cr.fetchone()[0] is not None


def _column_exists(cr, table, column):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
        """,
        [table, column],
    )
    return cr.fetchone() is not None


def migrate(cr, version):
    if not version:
        return
    if not _table_exists(cr, "account_retention"):
        _logger.info("l10n_ec_withholding: no hay account_retention, nada que migrar.")
        return
    if not _table_exists(cr, "l10n_ec_retention"):
        # l10n_ec_sri es ahora una dependencia, así que su tabla debería existir.
        # Si no está, abortar es más seguro que perder los datos en silencio.
        _logger.error(
            "l10n_ec_withholding: falta la tabla l10n_ec_retention. Instale o "
            "actualice l10n_ec_sri antes de migrar; las retenciones NO se han "
            "trasladado y account_retention se conserva intacta."
        )
        return

    # 1. Cabeceras. `l10n_ec.retention.invoice_id` es obligatorio, así que las
    #    retenciones huérfanas (sin factura) no se pueden trasladar; se cuentan y
    #    se dejan atrás en vez de inventarles una factura.
    #
    #    `state` (ciclo de vida del documento) sólo existe si l10n_ec_sri ya
    #    incorpora ese campo. Se detecta en vez de asumirlo, para que la migración
    #    funcione con cualquiera de las dos versiones del modelo destino: si la
    #    columna no está, se omite y PostgreSQL aplica su valor por defecto.
    #    Los valores coinciden en origen y destino (draft/posted/cancel).
    has_state = _column_exists(cr, "l10n_ec_retention", "state")
    state_column = "state," if has_state else ""
    state_value = "COALESCE(old.state, 'draft')," if has_state else ""

    cr.execute(f"""
        INSERT INTO l10n_ec_retention (
            name, invoice_id, partner_id, date_issue, company_id, {state_column}
            l10n_ec_sri_status, l10n_ec_sri_access_key, l10n_ec_sri_response,
            create_uid, create_date, write_uid, write_date
        )
        SELECT
            old.name, old.invoice_id, old.partner_id, old.date, old.company_id,
            {state_value}
            COALESCE(old.l10n_ec_sri_status, 'draft'),
            old.l10n_ec_sri_access_key, old.l10n_ec_sri_response,
            old.create_uid, old.create_date, old.write_uid, old.write_date
        FROM account_retention old
        WHERE old.invoice_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM l10n_ec_retention new WHERE new.name = old.name
          )
    """)
    migrated = cr.rowcount

    # 2. Líneas. `l10n_ec.retention.line.tax_id` es obligatorio: sólo se trasladan
    #    las que ya apuntaban a un account.tax. Las que sólo tenían el código en
    #    texto (`tax_code`) no se pueden reconstruir de forma fiable, porque ese
    #    campo no estaba validado contra ningún catálogo.
    cr.execute("""
        INSERT INTO l10n_ec_retention_line (
            retention_id, tax_id, base_amount, amount
        )
        SELECT new.id, old_line.tax_id, old_line.base, old_line.amount
        FROM account_retention_line old_line
        JOIN account_retention old ON old.id = old_line.retention_id
        JOIN l10n_ec_retention new ON new.name = old.name
        WHERE old_line.tax_id IS NOT NULL
    """)
    lines_migrated = cr.rowcount

    cr.execute("SELECT count(*) FROM account_retention")
    total = cr.fetchone()[0]
    cr.execute("SELECT count(*) FROM account_retention_line WHERE tax_id IS NULL")
    orphan_lines = cr.fetchone()[0]

    _logger.info(
        "l10n_ec_withholding: %s/%s retenciones y %s líneas trasladadas a "
        "l10n_ec.retention.", migrated, total, lines_migrated,
    )
    if migrated < total:
        _logger.warning(
            "l10n_ec_withholding: %s retenciones sin factura asociada NO se han "
            "trasladado. La tabla account_retention se conserva para que puedan "
            "revisarse a mano.", total - migrated,
        )
    if orphan_lines:
        _logger.warning(
            "l10n_ec_withholding: %s líneas sin impuesto (sólo tenían tax_code en "
            "texto) NO se han trasladado; revísense en account_retention_line.",
            orphan_lines,
        )

    # NO se tocan ir_model_data ni las tablas viejas:
    #
    # - Los registros de datos (vistas, secuencia, códigos de retención) los limpia
    #   el propio Odoo al actualizar: lo que está en ir_model_data del módulo pero
    #   ya no aparece en su XML se elimina solo. Borrarlos aquí a mano, filtrando
    #   por modelo, arrastraría también las vistas del asistente, que siguen vivas.
    # - Las tablas `account_retention*` se conservan a propósito: son la única copia
    #   de lo que no se pudo trasladar (retenciones sin factura, líneas sin
    #   impuesto). Odoo las deja huérfanas sin borrarlas, así que quedan
    #   consultables por SQL. Eliminarlas es una decisión manual y posterior.
