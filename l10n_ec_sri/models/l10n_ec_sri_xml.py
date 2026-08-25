# -*- coding: utf-8 -*-
"""Generación del XML de factura conforme a la Ficha Técnica SRI 2.34 (julio 2026).

Principio de diseño: la clave de acceso y el cuerpo del XML se construyen a partir
de UNA SOLA fuente de datos (`_get_document_components`). Antes cada uno derivaba
`estab`, `ptoEmi`, `secuencial` y `codDoc` por su cuenta —la plantilla con literales
`001`/`01`, la clave troceando el código del diario— y cuando no coincidían el SRI
rechazaba con el error 58 ("clave de acceso con componentes diferentes a los del
comprobante").
"""
import base64
import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Ficha Técnica 2.34, tabla 16 — códigos de impuesto
L10N_EC_TAX_CODE_VAT = "2"
L10N_EC_TAX_CODE_ICE = "3"
L10N_EC_TAX_CODE_IRBPNR = "5"

# Tabla 17 — codigoPorcentaje del IVA, indexado por account.tax.group.l10n_ec_type
# (clasificación que aporta el módulo oficial l10n_ec). No existen los códigos 1 ni 9.
L10N_EC_VAT_PERCENT_CODE = {
    "zero_vat": "0",
    "vat12": "2",
    "vat14": "3",
    "vat15": "4",
    "vat05": "5",
    "not_charged_vat": "6",
    "exempt_vat": "7",
    "vat08": "8",   # IVA diferenciado (decreto sector turístico)
    "vat13": "10",
}

# Respaldo por tarifa cuando el grupo de impuestos no está clasificado.
L10N_EC_VAT_PERCENT_CODE_BY_RATE = {
    0.0: "0", 12.0: "2", 14.0: "3", 15.0: "4", 5.0: "5", 8.0: "8", 13.0: "10",
}

_DOCUMENT_NUMBER_RE = re.compile(r"^(\d{3})-(\d{3})-(\d{9})$")

# Etiqueta de cada subtotal del RIDE, por codigoPorcentaje de la tabla 17.
# El Anexo 2 avisa: "los contribuyentes podrán visualizar SOLO los subtotales que
# fueron llenados", así que la plantilla no imprime los que no aparecen aquí.
L10N_EC_SUBTOTAL_LABELS = {
    "0": "SUBTOTAL 0%",
    "2": "SUBTOTAL 12%",
    "3": "SUBTOTAL 14%",
    "4": "SUBTOTAL 15%",
    "5": "SUBTOTAL 5%",
    "6": "SUBTOTAL NO OBJETO DE IVA",
    "7": "SUBTOTAL EXENTO DE IVA",
    "8": "SUBTOTAL TARIFA ESPECIAL",
    "10": "SUBTOTAL 13%",
}

# Tabla 3 — tipos de comprobante que este módulo sabe construir HOY.
#
# `render_xml` renderiza siempre la plantilla de factura, pero la clave de acceso sí
# lleva el codDoc real del documento. Emitir una nota de crédito por esta ruta producía
# un cuerpo <factura> con codDoc 04: el SRI lo rechaza con el error 35 (el XSD no
# corresponde) o el 58 (clave con componentes distintos a los del comprobante). Mejor
# negarse aquí que gastar un secuencial en un envío que nunca autorizará.
L10N_EC_SUPPORTED_DOCUMENT_CODES = {"01"}

# Sólo para el mensaje de error: nombrar el comprobante que el usuario intentó emitir.
L10N_EC_DOCUMENT_NAMES = {
    "01": "Factura",
    "03": "Liquidación de compra de bienes y prestación de servicios",
    "04": "Nota de crédito",
    "05": "Nota de débito",
    "06": "Guía de remisión",
    "07": "Comprobante de retención",
}


class L10nEcSriXml(models.AbstractModel):
    _name = "l10n_ec.sri.xml"
    _description = "SRI XML Generator"

    # ------------------------------------------------------------------
    # Componentes compartidos por la clave de acceso y por el XML
    # ------------------------------------------------------------------

    @api.model
    def _get_document_components(self, record):
        """Devuelve los componentes que clave y XML DEBEN compartir.

        Falla de forma explícita en vez de caer a `001`: un establecimiento por
        defecto silencioso es justamente lo que producía claves incoherentes.
        """
        journal = record.journal_id
        establishment = (journal.l10n_ec_entity or "").strip()
        emission_point = (journal.l10n_ec_emission or "").strip()
        if not establishment or not emission_point:
            raise UserError(_(
                "El diario '%s' no tiene establecimiento y punto de emisión SRI.\n\n"
                "Configúrelos en Contabilidad > Configuración > Diarios; son los "
                "códigos de 3 dígitos que asigna el SRI y forman parte tanto de la "
                "clave de acceso como del cuerpo del comprobante.",
                journal.display_name,
            ))

        document_type = record.l10n_latam_document_type_id
        if not document_type.code:
            raise UserError(_(
                "El comprobante %s no tiene tipo de documento SRI asignado.",
                record.display_name,
            ))

        return {
            "establishment": establishment.zfill(3),
            "emission_point": emission_point.zfill(3),
            "sequential": self._get_sequential(record),
            "document_code": document_type.code.zfill(2),
            # Tabla 4: 1 = Pruebas, 2 = Producción
            "environment": (
                "2" if record.company_id.l10n_ec_sri_environment == "production" else "1"
            ),
        }

    @api.model
    def _get_sequential(self, record):
        """Los 9 dígitos del secuencial.

        La Ficha es explícita: "si en el número secuencial no completa los 9 dígitos,
        la clave de acceso estará mal conformada y será motivo de rechazo".
        """
        number = record.l10n_latam_document_number or record.name or ""
        match = _DOCUMENT_NUMBER_RE.match(number.strip())
        if match:
            return match.group(3)
        digits = re.sub(r"\D", "", number)
        if not digits:
            raise UserError(_(
                "No se puede extraer el secuencial del comprobante '%s'.", number
            ))
        return digits[-9:].zfill(9)

    # ------------------------------------------------------------------
    # Clave de acceso
    # ------------------------------------------------------------------

    @api.model
    def generate_access_key(self, record):
        """Clave de acceso de 49 dígitos (Ficha 2.34, tabla 1)."""
        if not record.invoice_date:
            raise UserError(_("El comprobante necesita fecha de emisión."))

        components = self._get_document_components(record)
        ruc = (record.company_id.vat or "").strip()
        if not ruc.isdigit() or len(ruc) != 13:
            raise UserError(_(
                "El RUC de la compañía debe tener 13 dígitos numéricos (actual: '%s').",
                ruc or "",
            ))

        base_key = "{date}{doc}{ruc}{env}{estab}{pto}{seq}{numeric}{emission}".format(
            date=record.invoice_date.strftime("%d%m%Y"),
            doc=components["document_code"],
            ruc=ruc,
            env=components["environment"],
            estab=components["establishment"],
            pto=components["emission_point"],
            seq=components["sequential"],
            # Código numérico DETERMINISTA. La Ficha lo deja a "potestad absoluta del
            # contribuyente emisor", y hacerlo derivado del secuencial vuelve el
            # reenvío idempotente: antes se generaba con random en cada llamada, así
            # que cada reintento producía otra clave y duplicaba el comprobante en el
            # SRI (§5.10 exige reenviar con la MISMA clave y secuencial).
            numeric=components["sequential"][-8:].zfill(8),
            emission="1",  # Tabla 2: para el esquema offline solo existe emisión normal
        )

        access_key = base_key + self._get_modulo_11(base_key)
        if len(access_key) != 49 or not access_key.isdigit():
            raise ValidationError(_(
                "Clave de acceso mal conformada: %s caracteres, numérica=%s",
                len(access_key), access_key.isdigit(),
            ))
        return access_key

    @api.model
    def _get_modulo_11(self, key):
        """Dígito verificador, módulo 11 con factor ponderado 2..7 (Ficha, tabla 1).

        Comprobado con el ejemplo de la propia Ficha: 41261533 -> 6.
        """
        if not key.isdigit():
            raise ValidationError(_(
                "La clave de acceso contiene caracteres no numéricos: %s", key
            ))
        total = 0
        factor = 2
        for char in reversed(key):
            total += int(char) * factor
            factor = 2 if factor == 7 else factor + 1
        check = 11 - (total % 11)
        if check == 11:
            return "0"
        if check == 10:
            return "1"
        return str(check)

    # ------------------------------------------------------------------
    # Impuestos
    # ------------------------------------------------------------------

    @api.model
    def _get_product_lines(self, record):
        """Solo las líneas de producto.

        OJO: en Odoo 19 `display_type` vale 'product' en una línea normal, así que
        `not line.display_type` filtraría TODAS las líneas y el comprobante saldría
        sin detalles ni impuestos. Hay que comparar con 'product' explícitamente.
        """
        return record.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
        )

    @api.model
    def _get_tax_sri_codes(self, tax):
        """(codigo, codigoPorcentaje) de un impuesto, según tablas 16/17/18.

        Prioriza `account.tax.group.l10n_ec_type` —la clasificación oficial— sobre
        cualquier heurística. Antes esto se deducía del importe del impuesto y de
        subcadenas de su nombre, así que renombrar un impuesto rompía el mapeo en
        silencio y faltaban el 13 % y el IVA diferenciado.
        """
        # Acceso tolerante: si el addon oficial `l10n_ec` no está cargado el campo no
        # existe, y leerlo en crudo lanzaba AttributeError antes de poder caer al
        # respaldo por tarifa que hay más abajo.
        ec_type = tax.tax_group_id._l10n_ec_group_type()

        if ec_type in L10N_EC_VAT_PERCENT_CODE:
            return L10N_EC_TAX_CODE_VAT, L10N_EC_VAT_PERCENT_CODE[ec_type]
        if ec_type == "ice":
            category = tax.l10n_ec_ice_category_id
            if not category:
                raise UserError(_(
                    "El impuesto ICE '%s' no tiene categoría ICE asignada; sin ella no "
                    "se puede determinar su código de la tabla 18.", tax.display_name,
                ))
            return L10N_EC_TAX_CODE_ICE, category.code
        if ec_type == "irbpnr":
            return L10N_EC_TAX_CODE_IRBPNR, "5001"

        # Respaldo: el grupo no está clasificado (impuesto creado a mano).
        percent_code = L10N_EC_VAT_PERCENT_CODE_BY_RATE.get(round(tax.amount, 2))
        if percent_code:
            return L10N_EC_TAX_CODE_VAT, percent_code

        raise UserError(_(
            "No se puede determinar el código SRI del impuesto '%s'. Clasifique su "
            "grupo de impuestos (campo 'Tipo EC') o use una tarifa de IVA vigente.",
            tax.display_name,
        ))

    @api.model
    def _compute_sri_taxes(self, record):
        """Totales e impuestos por línea.

        Regla de la Ficha (num. 9.16, tabla 21) que antes no se aplicaba: **el ICE
        forma parte de la base imponible del IVA**. Se calcula primero el ICE de la
        línea y su importe se suma a la base sobre la que se aplica el IVA.
        """
        totals = {}
        line_taxes = {}

        for line in self._get_product_lines(record):
            base = abs(line.price_subtotal)
            entries = []

            ice_taxes = line.tax_ids.filtered(
                lambda t: t.tax_group_id.l10n_ec_type == "ice"
            )
            other_taxes = line.tax_ids - ice_taxes

            ice_amount = 0.0
            for tax in ice_taxes:
                codigo, cod_pct = self._get_tax_sri_codes(tax)
                value = self._compute_tax_amount(tax, line, base)
                ice_amount += value
                entries.append({
                    "codigo": codigo,
                    "codigoPorcentaje": cod_pct,
                    "tarifa": "%.2f" % tax.amount,
                    "baseImponible": "%.2f" % base,
                    "valor": "%.2f" % value,
                })
                self._accumulate(totals, codigo, cod_pct, base, value)

            # El IVA se aplica sobre la base + el ICE de la misma línea.
            vat_base = base + ice_amount
            for tax in other_taxes:
                codigo, cod_pct = self._get_tax_sri_codes(tax)
                value = vat_base * (tax.amount / 100.0)
                entries.append({
                    "codigo": codigo,
                    "codigoPorcentaje": cod_pct,
                    "tarifa": "%.2f" % tax.amount,
                    "baseImponible": "%.2f" % vat_base,
                    "valor": "%.2f" % value,
                })
                self._accumulate(totals, codigo, cod_pct, vat_base, value)

            line_taxes[line.id] = entries

        sri_totals = [
            {
                "codigo": vals["codigo"],
                "codigoPorcentaje": vals["codigoPorcentaje"],
                "baseImponible": "%.2f" % vals["baseImponible"],
                "valor": "%.2f" % vals["valor"],
            }
            for vals in totals.values()
        ]
        return sri_totals, line_taxes

    @api.model
    def _compute_tax_amount(self, tax, line, base):
        """Importe de un impuesto sobre una línea, respetando ICE fijo vs porcentual."""
        if tax.amount_type == "fixed":
            category = tax.l10n_ec_ice_category_id
            if category and category.type == "specific_content":
                content = line.product_id.l10n_ec_ice_unit_content or 1.0
                return abs(line.quantity) * content * category.specific_rate
            if category:
                return abs(line.quantity) * category.specific_rate
            return abs(line.quantity) * tax.amount
        if tax.l10n_ec_ice_category_id and tax.l10n_ec_ice_category_id.type == "ad_valorem":
            return base * (tax.l10n_ec_ice_category_id.ad_valorem_rate / 100.0)
        return base * (tax.amount / 100.0)

    @api.model
    def _accumulate(self, totals, codigo, cod_pct, base, value):
        key = (codigo, cod_pct)
        entry = totals.setdefault(key, {
            "codigo": codigo, "codigoPorcentaje": cod_pct,
            "baseImponible": 0.0, "valor": 0.0,
        })
        entry["baseImponible"] += base
        entry["valor"] += value

    # ------------------------------------------------------------------
    # Valores del comprobante
    # ------------------------------------------------------------------

    @api.model
    def _get_buyer_identification(self, record):
        """(tipoIdentificacionComprador, identificacionComprador) — tabla 6.

        04 RUC · 05 Cédula · 06 Pasaporte · 07 Consumidor Final · 08 Exterior.
        Se usa el tipo declarado en el contacto, no la longitud del VAT: antes un
        pasaporte de 13 caracteres se enviaba como RUC.
        """
        partner = record.partner_id
        vat = (partner.vat or "").strip()

        consumidor_final_ruc = self.env["ir.config_parameter"].sudo().get_param(
            "l10n_ec.consumidor_final_ruc", "9999999999999"
        )
        if not vat or vat == consumidor_final_ruc:
            return "07", consumidor_final_ruc

        identifier_type = partner.l10n_ec_identifier_type
        if identifier_type == "ruc":
            return "04", vat
        if identifier_type == "cedula":
            return "05", vat
        if identifier_type == "pasaporte":
            return "06", vat
        if partner.country_id and partner.country_id.code != "EC":
            return "08", vat

        # Sin tipo declarado: se infiere por longitud como último recurso.
        if len(vat) == 13 and vat.isdigit():
            return "04", vat
        if len(vat) == 10 and vat.isdigit():
            return "05", vat
        return "06", vat

    @api.model
    def _get_payment_details(self, record):
        """Bloque <pagos> — obligatorio. formaPago conforme tabla 24."""
        method = record.l10n_ec_payment_method_id
        code = method.code if method else self.env["ir.config_parameter"].sudo().get_param(
            "l10n_ec.default_payment_method_code", "01"
        )
        return [{"formaPago": code, "total": "%.2f" % record.amount_total}]

    @api.model
    def _get_additional_info(self, record):
        """Campos de <infoAdicional> (máximo 15, hasta 300 caracteres cada uno)."""
        fields_list = []
        partner = record.partner_id
        if partner.email:
            fields_list.append(("Email", partner.email[:300]))
        if partner.phone:
            fields_list.append(("Teléfono", partner.phone[:300]))
        if partner.street:
            fields_list.append(("Dirección", partner.street[:300]))

        # Anexo 26 (Res. NAC-DGERCGC26-00000027): quien emita con un facturador de
        # terceros debe declarar el RUC del proveedor del sistema.
        provider_ruc = self.env["ir.config_parameter"].sudo().get_param(
            "l10n_ec.software_provider_ruc"
        )
        if provider_ruc:
            fields_list.append(("RUC Proveedor", provider_ruc[:300]))

        # Anexo 24: grandes contribuyentes.
        if record.company_id.l10n_ec_big_taxpayer_resolution:
            fields_list.append((
                "Gran Contribuyente",
                record.company_id.l10n_ec_big_taxpayer_resolution[:300],
            ))

        if record.narration:
            text = re.sub(r"<[^>]+>", " ", str(record.narration))
            fields_list.append(("Observaciones", " ".join(text.split())[:300]))

        return fields_list[:15]

    @api.model
    def _check_document_type_supported(self, record):
        """Rechaza los comprobantes para los que no hay plantilla XML.

        Se comprueba antes de generar la clave de acceso para no dejar una clave
        persistida en un documento que no se puede emitir.
        """
        raw_code = (record.l10n_latam_document_type_id.code or "").strip()
        code = raw_code.zfill(2) if raw_code else ""
        if code in L10N_EC_SUPPORTED_DOCUMENT_CODES:
            return
        raise UserError(_(
            "Todavía no se puede emitir electrónicamente %(doc)s: es un comprobante "
            "de tipo %(code)s (%(label)s) y este módulo sólo genera el XML de la "
            "factura (01).\n\n"
            "Enviarlo produciría un cuerpo <factura> con codDoc %(code)s, que el SRI "
            "rechaza (errores 35 y 58). Emítalo por fuera del sistema mientras no "
            "exista la plantilla correspondiente.",
            doc=record.display_name,
            code=code or "sin asignar",
            label=L10N_EC_DOCUMENT_NAMES.get(code, _("no soportado")),
        ))

    @api.model
    def _get_signing_problems(self, company):
        """Lo que impide FIRMAR: certificado ausente, inactivo o caducado.

        Separado del resto porque la firma es un paso posterior a construir el XML, y
        mezclarlos hacía imposible renderizar un comprobante (o su RIDE) en una base
        sin certificado configurado.
        """
        certificate = company.l10n_ec_certificate_id
        if not certificate:
            return [_(
                "certificado de firma electrónica asignado a la compañía "
                "(Compañía > Facturación electrónica)"
            )]
        if certificate.state != "active":
            return [_(
                "certificado '%(name)s' en estado activo (actualmente: %(state)s)",
                name=certificate.name, state=certificate.state,
            )]
        if certificate.expiration_date and certificate.expiration_date < fields.Date.today():
            return [_(
                "certificado vigente: '%(name)s' caducó el %(date)s",
                name=certificate.name, date=certificate.expiration_date,
            )]
        return []

    @api.model
    def _check_emission_requirements(self, record, require_certificate=False):
        """Comprueba los obligatorios antes de construir el XML.

        Mejor fallar aquí con un mensaje claro que enviar al SRI un comprobante
        incompleto y recibir un error 35 de esquema sin contexto.

        `require_certificate` lo activa el flujo de envío, que sí va a firmar: así el
        usuario ve de una vez todo lo que le falta, en vez de corregir un dato,
        reintentar y toparse con el siguiente.
        """
        self._check_document_type_supported(record)
        company = record.company_id
        missing = []
        if not company.street:
            missing.append(_("dirección de la matriz (Compañía > Dirección)"))
        if not record.partner_id.name:
            missing.append(_("razón social del comprador"))
        if not record.invoice_date:
            missing.append(_("fecha de emisión"))
        if not self._get_product_lines(record):
            missing.append(_("al menos una línea de producto"))

        # RUC de la compañía. Se comprobaba dentro de generate_access_key, es decir
        # después de haber pasado el resto de validaciones: el usuario corregía un
        # dato, reintentaba, y se encontraba con el siguiente.
        ruc = (company.vat or "").strip()
        if not ruc.isdigit() or len(ruc) != 13:
            missing.append(_(
                "RUC de la compañía con 13 dígitos numéricos (actual: '%s')", ruc or ""
            ))

        # Establecimiento y punto de emisión del diario. Mismo motivo: el mensaje ya
        # existe en _get_document_components, pero llegaba más tarde y por separado.
        journal = record.journal_id
        if not (journal.l10n_ec_entity or "").strip():
            missing.append(_(
                "establecimiento SRI en el diario '%s' (Contabilidad > Configuración "
                "> Diarios)", journal.display_name,
            ))
        if not (journal.l10n_ec_emission or "").strip():
            missing.append(_(
                "punto de emisión SRI en el diario '%s'", journal.display_name
            ))

        # El certificado sólo se exige cuando se va a FIRMAR. Construir el XML no lo
        # necesita, y pedirlo aquí impedía renderizar un comprobante para revisarlo o
        # para el RIDE en una base sin firma configurada.
        if require_certificate:
            missing.extend(self._get_signing_problems(company))

        if missing:
            raise UserError(_(
                "Faltan datos obligatorios para emitir %(doc)s ante el SRI:\n\n- %(list)s",
                doc=record.display_name,
                list="\n- ".join(missing),
            ))

    @api.model
    def _get_invoice_values(self, record):
        self._check_emission_requirements(record)
        components = self._get_document_components(record)
        sri_totals, sri_line_taxes = self._compute_sri_taxes(record)
        id_type, identification = self._get_buyer_identification(record)
        company = record.company_id

        product_lines = self._get_product_lines(record)
        total_discount = sum(
            line.price_unit * line.quantity * (line.discount or 0.0) / 100.0
            for line in product_lines
        )

        return {
            "record": record,
            "company": company,
            "partner": record.partner_id,
            "access_key": record.l10n_ec_sri_access_key,
            "components": components,
            "sri_totals": sri_totals,
            "sri_line_taxes": sri_line_taxes,
            "buyer_id_type": id_type,
            "buyer_identification": identification,
            "payments": self._get_payment_details(record),
            "additional_info": self._get_additional_info(record),
            "total_discount": "%.2f" % total_discount,
            "lines": product_lines,
            "rimpe_legend": company.l10n_ec_rimpe_legend(),
            "money": lambda value: "%.2f" % (value or 0.0),
            "quantity": lambda value: "%.6f" % (value or 0.0),
            "clip": lambda value, size: (value or "")[:size],
        }

    @api.model
    def get_ride_values(self, record):
        """Datos del RIDE (Anexo 2), derivados de la MISMA fuente que el XML.

        El RIDE es la representación impresa del comprobante y tiene validez
        tributaria y jurídica (§9.19). Se construye reutilizando los mismos helpers
        que alimentan el XML: si la impresión y el archivo transmitido discreparan,
        el papel diría una cosa y el SRI tendría otra.

        No exige que el comprobante esté autorizado: el Anexo 2 aclara que la fecha y
        hora de autorización "no es obligatoria registrarla en el RIDE generado por
        los emisores", así que se puede imprimir un borrador.
        """
        components = self._get_document_components(record)
        sri_totals, _line_taxes = self._compute_sri_taxes(record)
        id_type, identification = self._get_buyer_identification(record)
        company = record.company_id

        product_lines = self._get_product_lines(record)
        total_discount = sum(
            line.price_unit * line.quantity * (line.discount or 0.0) / 100.0
            for line in product_lines
        )

        # Sólo los subtotales con contenido, y sólo los de IVA: el ICE y el IRBPNR
        # van en su propia línea de totales, no como subtotal por tarifa.
        subtotals = [
            {
                "label": L10N_EC_SUBTOTAL_LABELS.get(
                    total["codigoPorcentaje"], "SUBTOTAL"
                ),
                "amount": total["baseImponible"],
            }
            for total in sri_totals
            if total["codigo"] == L10N_EC_TAX_CODE_VAT
        ]
        tax_amount = sum(
            float(total["valor"]) for total in sri_totals
            if total["codigo"] == L10N_EC_TAX_CODE_VAT
        )
        ice_amount = sum(
            float(total["valor"]) for total in sri_totals
            if total["codigo"] == L10N_EC_TAX_CODE_ICE
        )

        return {
            "record": record,
            "company": company,
            "partner": record.partner_id,
            "components": components,
            "access_key": record.l10n_ec_sri_access_key or "",
            "document_number": "%s-%s-%s" % (
                components["establishment"],
                components["emission_point"],
                components["sequential"],
            ),
            "environment_label": (
                "PRODUCCIÓN" if components["environment"] == "2" else "PRUEBAS"
            ),
            "buyer_id_type": id_type,
            "buyer_identification": identification,
            "lines": product_lines,
            "subtotals": subtotals,
            "total_discount": "%.2f" % total_discount,
            "tax_amount": "%.2f" % tax_amount,
            "ice_amount": "%.2f" % ice_amount,
            # Precalculado: en QWeb no conviene depender de que `float()` esté en el
            # contexto de evaluación para decidir si se pinta la fila.
            "has_ice": ice_amount > 0,
            "payments": self._get_payment_details(record),
            "additional_info": self._get_additional_info(record),
            "rimpe_legend": company.l10n_ec_rimpe_legend(),
            "barcode": self._get_access_key_barcode(record.l10n_ec_sri_access_key),
            "money": lambda value: "%.2f" % (value or 0.0),
            "quantity": lambda value: "%.6f" % (value or 0.0),
        }

    @api.model
    def _get_access_key_barcode(self, access_key):
        """Código de barras de la clave de acceso, como data: URI.

        Se incrusta en vez de apuntar a `/report/barcode/` porque esa ruta obliga a
        wkhtmltopdf a hacer una petición HTTP de vuelta al propio Odoo mientras
        genera el PDF. Comprobado: si esa petición falla —servidor sin HTTP, red
        restringida, `web.base.url` mal puesta— wkhtmltopdf devuelve
        "Exit with code 1 due to network error: UnknownContentError" y el RIDE sale
        sin el código de barras, en silencio.

        Es opcional según §9.20, así que si la generación falla se devuelve False y
        el RIDE se imprime sin él en vez de no imprimirse.
        """
        if not access_key:
            return False
        try:
            png = self.env["ir.actions.report"].barcode(
                "Code128", access_key, width=600, height=70
            )
        except Exception:  # noqa: BLE001 — el código de barras no es obligatorio
            _logger.warning(
                "No se pudo generar el código de barras de la clave %s", access_key
            )
            return False
        return "data:image/png;base64,%s" % base64.b64encode(png).decode("ascii")

    @api.model
    def render_xml(self, record):
        """XML de la factura, con prólogo UTF-8 (la Ficha exige esa codificación)."""
        values = self._get_invoice_values(record)
        body = self.env["ir.qweb"]._render("l10n_ec_sri.xml_invoice", values)
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + str(body)
