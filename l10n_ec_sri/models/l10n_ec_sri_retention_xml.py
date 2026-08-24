# -*- coding: utf-8 -*-
"""Comprobante de retención (codDoc 07) — Ficha Técnica SRI 2.34."""
import logging
import re

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_RETENTION_NUMBER_RE = re.compile(r"^(\d{3})-(\d{3})-(\d{9})$")


class L10nEcSriRetentionXml(models.AbstractModel):
    _name = "l10n_ec.sri.retention.xml"
    _description = "SRI Retention XML Generator"

    def render_xml(self, retention):
        """XML del comprobante de retención, con prólogo UTF-8.

        La clave de acceso se genera UNA vez y se conserva. Antes se regeneraba en
        cada llamada a render_xml —y encima con un código numérico aleatorio—, así
        que dos renders del mismo comprobante producían dos claves distintas.
        """
        if not retention.l10n_ec_sri_access_key:
            retention.l10n_ec_sri_access_key = self._generate_retention_access_key(
                retention
            )

        establishment, emission_point, sequential = self._split_number(retention)
        values = {
            "record": retention,
            "access_key": retention.l10n_ec_sri_access_key,
            "company": retention.company_id,
            "partner": retention.partner_id,
            "establishment": establishment,
            "emission_point": emission_point,
            "sequential": sequential,
            "environment": self._get_environment(retention.company_id),
            "formatted_date": retention.date_issue.strftime("%d/%m/%Y"),
            "periodo_fiscal": retention.date_issue.strftime("%m/%Y"),
        }
        body = self.env["ir.qweb"]._render("l10n_ec_sri.xml_retention", values)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + str(body)

    def _get_environment(self, company):
        """Tabla 4: 1 = Pruebas, 2 = Producción.

        Aquí estaba uno de los fallos más graves del módulo: se metía en la clave de
        acceso el valor CRUDO del campo de selección, es decir la cadena literal
        'test' o 'production'. La clave dejaba de ser numérica y el módulo 11
        reventaba: la retención electrónica no podía emitirse nunca.
        """
        return "2" if company.l10n_ec_sri_environment == "production" else "1"

    def _split_number(self, record):
        """(estab, ptoEmi, secuencial) a partir del número del comprobante."""
        number = (record.name or "").strip()
        match = _RETENTION_NUMBER_RE.match(number)
        if match:
            return match.groups()

        journal_defaults = ("001", "001")
        digits = re.sub(r"\D", "", number)
        if not digits:
            raise UserError(_(
                "No se puede derivar el secuencial de la retención '%s'.", number
            ))
        return journal_defaults[0], journal_defaults[1], digits[-9:].zfill(9)

    def _generate_retention_access_key(self, record):
        """Clave de acceso de 49 dígitos para el comprobante de retención."""
        company = record.company_id
        ruc = (company.vat or "").strip()
        if not ruc.isdigit() or len(ruc) != 13:
            raise UserError(_(
                "El RUC de la compañía debe tener 13 dígitos numéricos (actual: '%s').",
                ruc or "",
            ))

        establishment, emission_point, sequential = self._split_number(record)

        base_key = "{date}{doc}{ruc}{env}{estab}{pto}{seq}{numeric}{emission}".format(
            date=record.date_issue.strftime("%d%m%Y"),
            doc="07",
            ruc=ruc,
            env=self._get_environment(company),
            estab=establishment,
            pto=emission_point,
            seq=sequential,
            # Determinista, igual que en la factura: un reenvío debe reutilizar la
            # misma clave (Ficha §5.10), no generar una nueva.
            numeric=sequential[-8:].zfill(8),
            emission="1",
        )
        return base_key + self.env["l10n_ec.sri.xml"]._get_modulo_11(base_key)
