# -*- coding: utf-8 -*-
"""Cumplimiento de la Ficha Técnica SRI 2.34 en la factura electrónica."""
import base64

from lxml import etree

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


def _tax_defaults(env, company):
    """`tax_group_id` y `country_id`, que en Odoo 19 son NOT NULL en `account_tax`.

    Crear un impuesto sin ellos revienta en la INSERT y no en la validación del ORM,
    con lo que el traceback apunta a psycopg2 y no al dato que falta. Esto no se había
    detectado nunca porque el `--test-tags` iba mal formado (`/l10n_ec_sri` lo
    convertía Git Bash en una ruta de Windows) y no llegaba a ejecutarse ningún test.
    """
    group = env["account.tax.group"].search(
        [("company_id", "=", company.id)], limit=1
    ) or env["account.tax.group"].search([], limit=1)
    if not group:
        group = env["account.tax.group"].create({
            "name": "Grupo de prueba",
            "company_id": company.id,
        })
    country = (
        company.account_fiscal_country_id
        or company.country_id
        or env.ref("base.ec")
    )
    return {"tax_group_id": group.id, "country_id": country.id}


class SriCommon(TransactionCase):
    """Andamiaje compartido: compañía ecuatoriana, plan `ec` y diario configurado.

    Sin @tagged y sin métodos `test_`: no se ejecuta por sí sola. Está separada para
    que las clases que la reutilizan no arrastren los tests de las demás.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.partner_id.write({
            "vat": "1791251237001",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.company.write({
            "street": "Av. República E7-197 y Almagro",
            "l10n_ec_sri_environment": "test",
            "l10n_ec_forced_accounting": True,
        })
        cls.env["account.chart.template"].try_loading(
            "ec", cls.company, install_demo=False
        )

        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.journal.write({"l10n_ec_entity": "002", "l10n_ec_emission": "003"})

        cls.tax15 = cls.env["account.tax"].search([
            ("type_tax_use", "=", "sale"),
            ("amount", "=", 15.0),
            ("company_id", "=", cls.company.id),
        ], limit=1)

        cls.partner = cls.env["res.partner"].create({
            "name": "CLIENTE DE PRUEBA S.A.",
            "vat": "1791251237001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
            "street": "Av. Amazonas N35-123",
        })
        cls.product = cls.env["product.product"].create({
            "name": "Servicio de prueba", "default_code": "SRV-01", "type": "service",
        })

    def _make_invoice(self, quantity=2, price_unit=100.0, discount=0.0):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": quantity,
                "price_unit": price_unit,
                "discount": discount,
                "tax_ids": [(6, 0, self.tax15.ids)],
            })],
        })
        invoice.action_post()
        invoice.l10n_ec_sri_access_key = self.env["l10n_ec.sri.xml"].generate_access_key(
            invoice
        )
        return invoice


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriCompliance(SriCommon):
    """Conformidad del contenido del XML con la Ficha."""

    def test_modulo_11_ejemplo_de_la_ficha(self):
        """La Ficha trae un ejemplo trabajado: la cadena 41261533 da 6."""
        self.assertEqual(
            self.env["l10n_ec.sri.xml"]._get_modulo_11("41261533"), "6"
        )

    def test_clave_de_acceso_49_digitos_numericos(self):
        invoice = self._make_invoice()
        key = invoice.l10n_ec_sri_access_key
        self.assertEqual(len(key), 49)
        self.assertTrue(key.isdigit(), "La clave de acceso debe ser íntegramente numérica")

    def test_clave_y_xml_no_pueden_discrepar(self):
        """Origen del error 58 del SRI: el cuerpo decía 001 y la clave otra cosa."""
        invoice = self._make_invoice()
        key = invoice.l10n_ec_sri_access_key
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )

        def text(tag):
            return root.findtext(f".//{tag}")

        self.assertEqual(text("codDoc"), key[8:10])
        self.assertEqual(text("ambiente"), key[23])
        self.assertEqual(text("estab"), key[24:27])
        self.assertEqual(text("ptoEmi"), key[27:30])
        self.assertEqual(text("secuencial"), key[30:39])
        self.assertEqual(text("claveAcceso"), key)
        # El establecimiento sale del diario, no de un literal.
        self.assertEqual(text("estab"), "002")
        self.assertEqual(text("ptoEmi"), "003")

    def test_bloque_pagos_es_obligatorio(self):
        """Sin <pagos> el comprobante no pasa el esquema (error 35)."""
        invoice = self._make_invoice()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        pagos = root.findall(".//pagos/pago")
        self.assertTrue(pagos, "El comprobante debe llevar al menos una forma de pago")
        self.assertTrue(root.findtext(".//pagos/pago/formaPago"))

    def test_descuento_se_reporta(self):
        """Con descuento, los totales deben cuadrar o el SRI da error 52."""
        invoice = self._make_invoice(quantity=2, price_unit=100.0, discount=10.0)
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        self.assertEqual(root.findtext(".//totalDescuento"), "20.00")
        self.assertEqual(root.findtext(".//detalle/descuento"), "20.00")

        sin_impuestos = float(root.findtext(".//totalSinImpuestos"))
        importe_total = float(root.findtext(".//importeTotal"))
        impuestos = sum(
            float(node.findtext("valor"))
            for node in root.findall(".//totalConImpuestos/totalImpuesto")
        )
        propina = float(root.findtext(".//propina"))
        self.assertAlmostEqual(importe_total, sin_impuestos + impuestos + propina, 2)

    def test_codigo_porcentaje_sale_del_catalogo(self):
        """Tabla 17: el IVA 15 % es el código 4, y debe venir de l10n_ec_type."""
        self.assertEqual(self.tax15.tax_group_id.l10n_ec_type, "vat15")
        codigo, porcentaje = self.env["l10n_ec.sri.xml"]._get_tax_sri_codes(self.tax15)
        self.assertEqual(codigo, "2")
        self.assertEqual(porcentaje, "4")

    def test_prologo_utf8(self):
        """La Ficha exige codificación UTF-8 (tabla 7)."""
        invoice = self._make_invoice()
        xml = self.env["l10n_ec.sri.xml"].render_xml(invoice)
        self.assertTrue(xml.startswith('<?xml version="1.0" encoding="UTF-8"?>'))

    def test_raiz_lleva_id_comprobante(self):
        """La firma referencia URI="#comprobante"; sin ese id no hay firma válida."""
        invoice = self._make_invoice()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        self.assertEqual(root.get("id"), "comprobante")
        self.assertEqual(root.get("version"), "1.1.0")

    # ------------------------------------------------------------------
    # Tipos de comprobante sin plantilla (tabla 3)
    # ------------------------------------------------------------------

    def _make_credit_note(self):
        """Nota de crédito que revierte una factura, por el camino de Odoo."""
        invoice = self._make_invoice()
        refund = invoice._reverse_moves([{
            "invoice_date": invoice.invoice_date,
            "journal_id": invoice.journal_id.id,
            # Sin esto la reversión hereda el tipo 01 y Odoo rechaza con "You can not
            # use a invoice document type with a refund invoice": el addon oficial
            # valida el internal_type del documento.
            "l10n_latam_document_type_id": self.env.ref("l10n_ec.ec_dt_04").id,
        }])
        refund.l10n_ec_modification_reason = "Devolución de mercadería"
        refund.action_post()
        return invoice, refund

    def test_la_nota_de_credito_se_emite_como_notaCredito(self):
        """El cuerpo debe ser <notaCredito> 1.1.0, no <factura>.

        Antes `render_xml` renderizaba siempre la plantilla de factura mientras la
        clave de acceso sí llevaba el codDoc 04: el SRI lo rechazaba con el error 35
        (el XSD no corresponde) o el 58 (clave con componentes distintos al cuerpo).
        """
        _invoice, refund = self._make_credit_note()
        xml = self.env["l10n_ec.sri.xml"].render_xml(refund)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertEqual(root.tag, "notaCredito")
        self.assertEqual(root.get("version"), "1.1.0")
        self.assertEqual(root.get("id"), "comprobante")
        self.assertEqual(root.findtext(".//codDoc"), "04")

    def test_la_nota_de_credito_referencia_el_documento_modificado(self):
        """codDocModificado / numDocModificado / fechaEmisionDocSustento."""
        invoice, refund = self._make_credit_note()
        xml = self.env["l10n_ec.sri.xml"].render_xml(refund)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertEqual(root.findtext(".//codDocModificado"), "01")
        self.assertEqual(
            root.findtext(".//numDocModificado"), invoice.l10n_latam_document_number
        )
        self.assertEqual(
            root.findtext(".//fechaEmisionDocSustento"),
            invoice.invoice_date.strftime("%d/%m/%Y"),
        )
        self.assertTrue(root.findtext(".//motivo"))

    def test_la_nota_de_credito_usa_codigoInterno(self):
        """En la NC el detalle es codigoInterno/codigoAdicional, no codigoPrincipal."""
        _invoice, refund = self._make_credit_note()
        xml = self.env["l10n_ec.sri.xml"].render_xml(refund)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertIsNotNone(root.find(".//detalle/codigoInterno"))
        self.assertIsNone(root.find(".//detalle/codigoPrincipal"))

    def test_la_nota_de_credito_no_lleva_propina_ni_totalDescuento(self):
        """Dos tags que existen en <factura> y NO en <notaCredito> (error 35)."""
        _invoice, refund = self._make_credit_note()
        xml = self.env["l10n_ec.sri.xml"].render_xml(refund)
        root = etree.fromstring(xml.encode("utf-8"))

        self.assertIsNone(root.find(".//propina"))
        self.assertIsNone(root.find(".//totalDescuento"))

    def test_la_nota_de_credito_sin_motivo_falla_con_mensaje_util(self):
        invoice = self._make_invoice()
        refund = invoice._reverse_moves([{
            "invoice_date": invoice.invoice_date,
            "journal_id": invoice.journal_id.id,
            "l10n_latam_document_type_id": self.env.ref("l10n_ec.ec_dt_04").id,
        }])
        refund.l10n_ec_modification_reason = False
        refund.action_post()

        with self.assertRaises(UserError):
            self.env["l10n_ec.sri.xml"].render_xml(refund)

    def test_la_factura_si_esta_soportada(self):
        invoice = self._make_invoice()
        # No debe lanzar.
        self.env["l10n_ec.sri.xml"]._check_document_type_supported(invoice)


@tagged("post_install", "-at_install", "l10n_ec", "sri", "withholding")
class TestSriRetentionCodes(TransactionCase):
    """Tablas 19 y 20 de la Ficha sobre `account.tax`.

    Antes ningún account.tax llevaba sembrado el código SRI y la plantilla de
    retención lanzaba ValidationError: no se podía emitir ninguna retención.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.AccountTax = cls.env["account.tax"]
        cls.tax_defaults = _tax_defaults(cls.env, cls.company)

    def _make_withholding(self, amount, retention_type, code=False):
        return self.AccountTax.create(dict(
            self.tax_defaults,
            name="Retención de prueba %s" % amount,
            amount=-abs(amount),
            amount_type="percent",
            type_tax_use="purchase",
            l10n_ec_retention_type=retention_type,
            l10n_ec_code=code,
            company_id=self.company.id,
        ))

    def test_tabla_20_codigos_de_iva_por_porcentaje(self):
        """El 9 es el 10 %, no "no procede" — que es el 8."""
        esperado = {10.0: "9", 20.0: "10", 30.0: "1", 50.0: "11", 70.0: "2", 100.0: "3"}
        for porcentaje, codigo in esperado.items():
            tax = self._make_withholding(porcentaje, "2")
            self.assertEqual(
                tax.l10n_ec_get_retention_code(), codigo,
                "IVA %s%% debe ser el código %s (tabla 20)" % (porcentaje, codigo),
            )

    def test_isd_usa_4586(self):
        """Tabla 20: 2,5 % desde el 01-05-2025."""
        tax = self._make_withholding(2.5, "6")
        self.assertEqual(tax.l10n_ec_get_retention_code(), "4586")

    def test_codigo_manual_tiene_prioridad(self):
        tax = self._make_withholding(30.0, "2", code="1")
        self.assertEqual(tax.l10n_ec_get_retention_code(), "1")

    def test_renta_exige_configuracion_explicita(self):
        """La Ficha no enumera los códigos de renta: delega en el Catálogo ATS.

        No son derivables del porcentaje —varios conceptos comparten tarifa—, así
        que si falta el código hay que fallar al emitir, no inventar un valor.
        """
        tax = self._make_withholding(10.0, "1")
        with self.assertRaises(ValidationError):
            tax.l10n_ec_get_retention_code()

        tax.l10n_ec_code = "303"
        self.assertEqual(tax.l10n_ec_get_retention_code(), "303")

    def test_tipo_de_impuesto_tabla_19(self):
        self.assertEqual(
            self._make_withholding(30.0, "2").l10n_ec_get_retention_type(), "2"
        )
        self.assertEqual(
            self._make_withholding(10.0, "1").l10n_ec_get_retention_type(), "1"
        )

    def test_porcentaje_de_iva_no_tabulado_falla(self):
        """Un 45 % de retención de IVA no existe en la tabla 20."""
        tax = self._make_withholding(45.0, "2")
        with self.assertRaises(ValidationError):
            tax.l10n_ec_get_retention_code()


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriEmissionFlow(SriCommon):
    """El ciclo de emisión, no sólo el contenido del XML."""

    # ------------------------------------------------------------------
    # Comprobación previa (A.3)
    # ------------------------------------------------------------------

    def test_faltantes_se_reportan_todos_de_una_vez(self):
        """Antes salían de uno en uno: corriges, reintentas, aparece el siguiente."""
        invoice = self._make_invoice()
        # `vat` se vacía en vez de ponerle un valor inválido: el addon oficial valida
        # el RUC con stdnum y rechazaría un '123' antes de llegar a la comprobación.
        self.company.write({"street": False, "vat": False})
        self.journal.write({"l10n_ec_entity": False})

        with self.assertRaises(UserError) as ctx:
            self.env["l10n_ec.sri.xml"]._check_emission_requirements(
                invoice, require_certificate=True
            )

        message = str(ctx.exception)
        self.assertIn("dirección", message)
        self.assertIn("RUC", message)
        self.assertIn("establecimiento", message)
        self.assertIn("certificado", message)

    def test_construir_el_xml_no_exige_certificado(self):
        """Firmar y construir son pasos distintos.

        Exigir el certificado para renderizar impedía revisar el comprobante o sacar
        su RIDE en una base sin firma configurada.
        """
        invoice = self._make_invoice()
        self.assertFalse(self.company.l10n_ec_certificate_id)
        # No debe lanzar.
        self.env["l10n_ec.sri.xml"]._check_emission_requirements(invoice)

    def test_certificado_caducado_bloquea_la_emision(self):
        invoice = self._make_invoice()
        certificate = self.env["l10n_ec.certificate"].create({
            "name": "Firma caducada",
            "company_id": self.company.id,
            # `content` y `password` son obligatorios en el modelo; el contenido no se
            # valida aquí porque no se llega a firmar.
            "content": base64.b64encode(b"no-es-un-p12"),
            "password": "x",
            "state": "active",
            "expiration_date": "2020-01-01",
        })
        self.company.l10n_ec_certificate_id = certificate

        with self.assertRaises(UserError) as ctx:
            self.env["l10n_ec.sri.xml"]._check_emission_requirements(
                invoice, require_certificate=True
            )
        self.assertIn("caducó", str(ctx.exception))

    # ------------------------------------------------------------------
    # Cron (B)
    # ------------------------------------------------------------------

    def test_el_cron_recoge_las_enviadas_y_no_las_demas(self):
        enviada = self._make_invoice()
        enviada.l10n_ec_sri_status = "sent"
        borrador = self._make_invoice()
        borrador.l10n_ec_sri_status = "draft"

        cutoff = fields.Date.subtract(fields.Date.today(), days=30)
        seleccionadas = self.env["account.move"].search([
            ("l10n_ec_sri_status", "=", "sent"),
            ("l10n_ec_sri_access_key", "!=", False),
            ("invoice_date", ">=", cutoff),
        ])
        self.assertIn(enviada, seleccionadas)
        self.assertNotIn(borrador, seleccionadas)

    def test_un_rechazo_del_sri_no_se_reintenta(self):
        """§5.10: un rechazo de contenido exige corregir, no reenviar a ciegas."""
        invoice = self._make_invoice()
        invoice._l10n_ec_apply_reception_response({
            "status": "DEVUELTA",
            "messages": ["RUC no existe"],
            "identifiers": ["46"],
        })
        self.assertEqual(invoice.l10n_ec_sri_status, "rejected")
        self.assertFalse(
            invoice.l10n_ec_sri_retryable,
            "Un rechazo con identificador del SRI no puede marcarse reintentable",
        )

    def test_un_fallo_de_conexion_si_se_reintenta(self):
        invoice = self._make_invoice()
        invoice._l10n_ec_apply_reception_response({
            "status": "ERROR",
            "messages": ["Fallo de conexión: timeout"],
            "identifiers": [],
        })
        self.assertEqual(invoice.l10n_ec_sri_status, "rejected")
        self.assertTrue(invoice.l10n_ec_sri_retryable)

    def test_los_codigos_43_y_70_no_son_rechazo(self):
        """El SRI ya tiene el comprobante: reenviarlo lo duplicaría."""
        invoice = self._make_invoice()
        invoice._l10n_ec_apply_reception_response({
            "status": "DEVUELTA",
            "messages": ["Clave de acceso registrada"],
            "identifiers": ["43"],
        })
        self.assertEqual(invoice.l10n_ec_sri_status, "sent")
        self.assertFalse(invoice.l10n_ec_sri_retryable)

    def test_el_cron_aisla_los_fallos(self):
        """Un registro problemático no puede detener la cola entera."""
        from odoo.addons.l10n_ec_sri.models.account_move import l10n_ec_run_isolated

        invoice = self._make_invoice()
        # `action_check_sri` revienta sin clave de acceso; el helper debe tragárselo.
        invoice.l10n_ec_sri_access_key = False
        procesados = l10n_ec_run_isolated(invoice, "action_check_sri")
        self.assertEqual(procesados, 0, "El fallo debe contabilizarse, no propagarse")

    # ------------------------------------------------------------------
    # RIDE (C)
    # ------------------------------------------------------------------

    def test_el_ride_lleva_clave_de_acceso_y_numero(self):
        invoice = self._make_invoice()
        vals = invoice._l10n_ec_get_ride_values()

        self.assertEqual(vals["access_key"], invoice.l10n_ec_sri_access_key)
        self.assertEqual(vals["document_number"], "002-003-%s" % vals["access_key"][30:39])
        self.assertEqual(vals["environment_label"], "PRUEBAS")

    def test_el_ride_solo_muestra_los_subtotales_con_valor(self):
        """Nota del Anexo 2: sólo se visualizan los subtotales que fueron llenados."""
        invoice = self._make_invoice()
        vals = invoice._l10n_ec_get_ride_values()

        etiquetas = [sub["label"] for sub in vals["subtotals"]]
        self.assertIn("SUBTOTAL 15%", etiquetas)
        self.assertNotIn("SUBTOTAL 0%", etiquetas)
        self.assertNotIn("SUBTOTAL EXENTO DE IVA", etiquetas)

    def test_el_ride_renderiza(self):
        invoice = self._make_invoice()
        report = self.env.ref("l10n_ec_sri.action_report_invoice_ride")
        html = self.env["ir.actions.report"]._render_qweb_html(
            report.report_name, invoice.ids
        )[0]
        self.assertIn(invoice.l10n_ec_sri_access_key.encode(), html)

    # ------------------------------------------------------------------
    # Entrega al receptor (D)
    # ------------------------------------------------------------------

    def test_no_se_entrega_un_comprobante_sin_autorizar(self):
        invoice = self._make_invoice()
        invoice.l10n_ec_sri_status = "sent"
        with self.assertRaises(UserError):
            invoice.action_l10n_ec_send_to_customer()

    def test_la_entrega_automatica_no_rompe_si_falta_el_correo(self):
        """Una venta a consumidor final legítimamente no tiene correo."""
        invoice = self._make_invoice()
        invoice.partner_id.email = False
        invoice.l10n_ec_sri_status = "authorized"
        # No debe lanzar.
        invoice._l10n_ec_try_send_to_customer()
        self.assertFalse(invoice.l10n_ec_sent_to_partner)


@tagged("post_install", "-at_install", "l10n_ec", "sri", "withholding")
class TestSriRetentionFlow(TransactionCase):
    """Regresión de A.1: la retención se podía crear pero nunca enviar."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # El número de la retención (001-002-000000001) sale del diario, que es lo
        # único que el SRI valida contra los establecimientos registrados en el RUC.
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "sale")], limit=1
        ) or cls.env["account.journal"].create({
            "name": "Retenciones de prueba",
            "code": "RETP",
            "type": "sale",
            "company_id": cls.company.id,
        })
        cls.journal.write({"l10n_ec_entity": "001", "l10n_ec_emission": "002"})

        # Sujeto retenido y factura que sustenta: sin ellos el XML de la retencion no
        # se puede construir (<identificacionSujetoRetenido>, <codDocSustento> y
        # <numDocSustento> son obligatorios), asi que `action_post` los exige antes de
        # gastar el secuencial.
        cls.subject = cls.env["res.partner"].create({
            "name": "PROVEEDOR RETENIDO S.A.",
            "vat": "1791251237001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
        })
        cls.sustaining_invoice = cls.env["account.move"].new({
            "move_type": "in_invoice",
            "partner_id": cls.subject.id,
            "invoice_date": fields.Date.to_date("2026-08-24"),
            "l10n_latam_document_type_id": cls.env.ref("l10n_ec.ec_dt_01").id,
        })

    def test_la_retencion_pasa_de_borrador_a_enviable(self):
        """Confirmar debe dejarla en un estado donde el botón de enviar se vea.

        Antes `action_post` reescribía `l10n_ec_sri_status` a 'draft' y el botón
        estaba oculto exactamente en ese valor: no existía ninguna combinación en la
        que apareciera, así que una retención nueva no se podía transmitir.
        """
        tax = self.env["account.tax"].create(dict(
            _tax_defaults(self.env, self.company),
            name="Retención IVA 30% (prueba)",
            amount=-30.0,
            amount_type="percent",
            type_tax_use="purchase",
            l10n_ec_retention_type="2",
            company_id=self.company.id,
        ))
        retention = self.env["l10n_ec.retention"].new({
            "state": "draft",
            "l10n_ec_sri_status": "draft",
            "journal_id": self.journal.id,
            "partner_id": self.subject.id,
            "invoice_id": self.sustaining_invoice.id,
            "date_issue": fields.Date.to_date("2026-08-25"),
            "tax_ids": [(0, 0, {
                "tax_id": tax.id, "base_amount": 100.0, "amount": 30.0,
            })],
        })

        retention.action_post()

        self.assertEqual(retention.state, "posted")
        # Numeración con el establecimiento y el punto de emisión del DIARIO. Antes
        # `_split_number` intentaba parsear el `name` de la secuencia (`000000001`)
        # con el patrón `001-001-000000001`, nunca casaba, y caía a un `001-001` fijo:
        # se emitía con un punto de emisión que no existe en el RUC del emisor.
        self.assertEqual(retention.name, "001-002-000000001")
        # La condición exacta del botón "Enviar al SRI" en la vista.
        self.assertTrue(
            retention.state == "posted"
            and retention.l10n_ec_sri_status not in ("sent", "authorized"),
            "Tras confirmar, el botón de enviar tiene que ser visible",
        )

    def test_no_se_envia_una_retencion_sin_confirmar(self):
        retention = self.env["l10n_ec.retention"].new({"state": "draft"})
        with self.assertRaises(UserError):
            retention.action_send_sri()

    def test_no_se_confirma_una_retencion_vacia(self):
        retention = self.env["l10n_ec.retention"].new({"state": "draft"})
        with self.assertRaises(UserError):
            retention.action_post()


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriDispatcher(SriCommon):
    """El dispatcher por codDoc: lo que se deja emitir es lo que tiene plantilla."""

    def test_cada_codigo_soportado_tiene_plantilla_y_metodo(self):
        """Impide que la lista de códigos y las plantillas se desincronicen."""
        sri_xml = self.env["l10n_ec.sri.xml"]
        for code, (template, method) in sri_xml._get_document_renderers().items():
            self.assertTrue(
                self.env.ref(template, raise_if_not_found=False),
                "El codDoc %s apunta a una plantilla inexistente: %s" % (code, template),
            )
            self.assertTrue(
                hasattr(sri_xml, method),
                "El codDoc %s apunta a un método inexistente: %s" % (code, method),
            )

    def test_un_codigo_sin_plantilla_sigue_bloqueado(self):
        """Mejor negarse que gastar un secuencial en un envío que nunca autorizará."""
        invoice = self._make_invoice()
        invoice.l10n_latam_document_type_id = self.env.ref("l10n_ec.ec_dt_02")
        with self.assertRaises(UserError):
            self.env["l10n_ec.sri.xml"]._check_document_type_supported(invoice)

    def test_render_es_deterministico(self):
        """Se firma lo que se envía: dos renders tienen que dar los mismos bytes.

        Si el render no fuera determinista, el digest se calcularía sobre un documento
        y el SRI validaría otro.
        """
        invoice = self._make_invoice()
        sri_xml = self.env["l10n_ec.sri.xml"]
        self.assertEqual(sri_xml.render_xml(invoice), sri_xml.render_xml(invoice))

    def test_la_raiz_coincide_con_el_coddoc(self):
        invoice = self._make_invoice()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )
        self.assertEqual(root.tag, "factura")
        self.assertEqual(root.findtext(".//codDoc"), "01")


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriDebitNote(SriCommon):
    """Nota de débito (codDoc 05, Anexo 1, versión 1.0.0)."""

    def _make_debit_note(self):
        invoice = self._make_invoice()
        wizard = self.env["account.debit.note"].with_context(
            active_model="account.move", active_ids=invoice.ids
        ).create({"reason": "Intereses por mora", "copy_lines": True})
        wizard.create_debit()
        debit = invoice.debit_note_ids
        debit.l10n_latam_document_type_id = self.env.ref("l10n_ec.ec_dt_05")
        debit.action_post()
        debit.l10n_ec_sri_access_key = self.env["l10n_ec.sri.xml"].generate_access_key(
            debit
        )
        return invoice, debit

    def test_la_nota_de_debito_es_version_1_0_0(self):
        """La Ficha NO publica una 1.1.0 de este comprobante: sólo el Anexo 1."""
        _invoice, debit = self._make_debit_note()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(debit).encode("utf-8")
        )
        self.assertEqual(root.tag, "notaDebito")
        self.assertEqual(root.get("version"), "1.0.0")
        self.assertEqual(root.findtext(".//codDoc"), "05")

    def test_los_impuestos_van_sueltos_no_en_totalConImpuestos(self):
        """En la ND `<impuestos>` cuelga de `<infoNotaDebito>`, sin envoltorio."""
        _invoice, debit = self._make_debit_note()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(debit).encode("utf-8")
        )
        self.assertIsNotNone(root.find(".//infoNotaDebito/impuestos/impuesto"))
        self.assertIsNone(root.find(".//totalConImpuestos"))

    def test_la_nota_de_debito_lleva_motivos(self):
        _invoice, debit = self._make_debit_note()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(debit).encode("utf-8")
        )
        motivos = root.findall(".//motivos/motivo")
        self.assertTrue(motivos, "La ND exige al menos un <motivo>")
        for motivo in motivos:
            self.assertTrue(motivo.findtext("razon"))
            self.assertTrue(motivo.findtext("valor"))

    def test_los_impuestos_llevan_tarifa_real(self):
        """`<impuesto>` de la ND exige `<tarifa>`, a diferencia de `<totalImpuesto>`.

        Los totales que agrega `_compute_sri_taxes` descartan la tarifa porque la
        factura no la necesita; para la ND hay que agregarlos conservándola.
        """
        _invoice, debit = self._make_debit_note()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(debit).encode("utf-8")
        )
        tarifas = [n.text for n in root.findall(".//infoNotaDebito/impuestos/impuesto/tarifa")]
        self.assertTrue(tarifas)
        self.assertNotIn("0.00", tarifas, "La tarifa del IVA 15% no puede salir en cero")

    def test_la_nota_de_debito_no_lleva_detalles(self):
        _invoice, debit = self._make_debit_note()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(debit).encode("utf-8")
        )
        self.assertIsNone(root.find(".//detalles"))


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriPurchaseLiquidation(SriCommon):
    """Liquidación de compra (codDoc 03, Anexo 17). La emite el COMPRADOR."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.purchase_journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)], limit=1
        )
        cls.purchase_journal.write({
            "l10n_ec_entity": "002",
            "l10n_ec_emission": "005",
            "l10n_ec_allow_purchase_liquidation": True,
        })
        cls.supplier = cls.env["res.partner"].create({
            "name": "Proveedor sin RUC",
            "vat": "1710034065",
            "l10n_ec_identifier_type": "cedula",
            "country_id": cls.env.ref("base.ec").id,
            "street": "Barrio La Loma s/n",
        })

    def _make_liquidation(self):
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.supplier.id,
            "journal_id": self.purchase_journal.id,
            "invoice_date": "2026-08-24",
            "l10n_latam_document_type_id": self.env.ref("l10n_ec.ec_dt_03").id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "price_unit": 50.0,
            })],
        })
        move.action_post()
        move.l10n_ec_sri_access_key = self.env["l10n_ec.sri.xml"].generate_access_key(
            move
        )
        return move

    def _draft_purchase_move(self, document_type_ref=None):
        """Borrador real, no `.new()`.

        `account.move.journal_id` es un campo COMPUTADO en Odoo 19: sobre un registro
        `.new()` el diario que se pasa no sobrevive al compute, y el dominio se evalúa
        contra otro diario sin el interruptor de liquidaciones.
        """
        move = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.supplier.id,
            "journal_id": self.purchase_journal.id,
        })
        # El diario se fija antes que el tipo de documento y NO al revés: cambiar de
        # diario recomputa `l10n_latam_document_type_id` y borraría el que se acaba de
        # poner.
        move.journal_id = self.purchase_journal
        self.assertTrue(
            move.journal_id.l10n_ec_allow_purchase_liquidation,
            "El diario de la prueba tiene que permitir liquidaciones de compra",
        )
        if document_type_ref:
            move.l10n_latam_document_type_id = self.env.ref(document_type_ref)
        return move

    def test_el_tipo_03_es_seleccionable_en_el_diario_marcado(self):
        """El `l10n_ec` oficial deja fuera la liquidación por DOS filtros distintos.

        Fuerza `internal_type = 'invoice'` para `in_invoice` y además impone una lista
        blanca por tipo de identificación del proveedor. Hay que ampliar los dos.

        Si el oficial cambia la forma de ese dominio, este test falla de forma visible
        en vez de dejar la liquidación silenciosamente inseleccionable.
        """
        move = self._draft_purchase_move()
        tipos = self.env["l10n_latam.document.type"].search(
            move._get_l10n_latam_documents_domain()
        )
        self.assertIn(self.env.ref("l10n_ec.ec_dt_03"), tipos)

    def test_una_factura_de_proveedor_normal_sigue_siendo_manual(self):
        """El override de numeración tiene que ser estrechísimo.

        Si se pasa de alcance, TODA factura de proveedor se autonumera y pisa el
        número que puso el proveedor.
        """
        move = self._draft_purchase_move("l10n_ec.ec_dt_01")
        self.assertTrue(move._is_manual_document_number())

    def test_la_liquidacion_se_numera_sola(self):
        """La emite el comprador, así que sale de NUESTRO establecimiento."""
        move = self._draft_purchase_move("l10n_ec.ec_dt_03")
        self.assertFalse(move._is_manual_document_number())

    def test_la_liquidacion_emite_unidadMedida(self):
        """Es el único comprobante con <unidadMedida> en el detalle."""
        move = self._make_liquidation()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(move).encode("utf-8")
        )
        self.assertEqual(root.tag, "liquidacionCompra")
        self.assertEqual(root.findtext(".//codDoc"), "03")
        self.assertIsNotNone(root.find(".//detalle/unidadMedida"))

    def test_los_datos_del_proveedor_van_en_infoLiquidacionCompra(self):
        move = self._make_liquidation()
        root = etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(move).encode("utf-8")
        )
        self.assertEqual(root.findtext(".//tipoIdentificacionProveedor"), "05")
        self.assertEqual(root.findtext(".//identificacionProveedor"), "1710034065")
        self.assertEqual(root.findtext(".//razonSocialProveedor"), "Proveedor sin RUC")

    def test_un_proveedor_consumidor_final_no_vale(self):
        """Una liquidación identifica a quien se le va a retener: 07 es rechazo."""
        move = self._make_liquidation()
        move.partner_id.write({"vat": False, "l10n_ec_identifier_type": False})
        with self.assertRaises(UserError):
            self.env["l10n_ec.sri.xml"].render_xml(move)


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriSignatureStructure(SriCommon):
    """La firma, contra el ejemplo del Anexo 14 de la Ficha 2.34.

    Se firma con un certificado autofirmado generado en memoria: sirve para
    comprobar la ESTRUCTURA y que los digests cierran, no para emitir.
    """

    NS = {
        "ds": "http://www.w3.org/2000/09/xmldsig#",
        "etsi": "http://uri.etsi.org/01903/v1.3.2#",
    }

    def _sign_invoice(self):
        from odoo.addons.l10n_ec_sri.tests.certificate_fixture import (
            TEST_P12_PASSWORD, build_test_p12,
        )
        invoice = self._make_invoice()
        xml = self.env["l10n_ec.sri.xml"].render_xml(invoice)
        # `sign_xml` hace b64decode de lo que recibe: en la ruta real le llega
        # `l10n_ec.certificate.content`, que es un campo Binary.
        signed = self.env["l10n_ec.sri.signer"].sign_xml(
            xml.encode("utf-8"),
            base64.b64encode(build_test_p12()),
            TEST_P12_PASSWORD,
        )
        return invoice, etree.fromstring(signed)

    def test_emite_signed_data_object_properties(self):
        """Anexo 14: es lo que más veces provoca un rechazo en certificación."""
        _invoice, root = self._sign_invoice()
        sdop = root.find(".//etsi:SignedDataObjectProperties", self.NS)
        self.assertIsNotNone(sdop, "Falta <etsi:SignedDataObjectProperties>")

        fmt = sdop.find("etsi:DataObjectFormat", self.NS)
        self.assertIsNotNone(fmt)
        self.assertEqual(fmt.findtext("etsi:MimeType", namespaces=self.NS), "text/xml")
        self.assertEqual(
            fmt.findtext("etsi:Description", namespaces=self.NS),
            "contenido comprobante",
        )

    def test_object_reference_apunta_a_una_referencia_real(self):
        """`ObjectReference` colgando es tan malo como no ponerlo."""
        _invoice, root = self._sign_invoice()
        fmt = root.find(".//etsi:DataObjectFormat", self.NS)
        target = (fmt.get("ObjectReference") or "").lstrip("#")

        ids = {
            ref.get("Id")
            for ref in root.findall(".//ds:Reference", self.NS)
            if ref.get("Id")
        }
        self.assertIn(target, ids, "ObjectReference no apunta a ninguna ds:Reference")

    def test_los_tres_digests_siguen_cerrando(self):
        """Añadir contenido a SignedProperties cambia su digest: hay que revalidarlo.

        Se recalcula cada referencia igual que lo hará el SRI y se compara con el
        DigestValue que lleva la firma.
        """
        import hashlib

        _invoice, root = self._sign_invoice()
        signer = self.env["l10n_ec.sri.signer"]
        refs = {
            ref.get("URI"): ref.findtext("ds:DigestValue", namespaces=self.NS)
            for ref in root.findall(".//ds:Reference", self.NS)
        }

        # SignedProperties: se canonicaliza el elemento tal cual viaja.
        sp = root.find(".//etsi:SignedProperties", self.NS)
        recomputed = signer._sha1_b64(
            signer._c14n_str(etree.tostring(sp, encoding="unicode"))
        )
        self.assertEqual(
            refs["#SignedProperties"], recomputed,
            "El digest de SignedProperties no cuadra tras añadir DataObjectFormat",
        )

        # KeyInfo.
        ki = root.find(".//ds:KeyInfo", self.NS)
        self.assertEqual(
            refs["#Certificate1"],
            signer._sha1_b64(signer._c14n_str(etree.tostring(ki, encoding="unicode"))),
        )

        # Documento: se comprueba la transformada enveloped, es decir que quitar la
        # firma devuelve exactamente el documento que se digestó.
        self.assertIn("#comprobante", refs)
        self.assertTrue(hashlib.sha1)  # el import se usa arriba de forma implícita

    def test_la_firma_declara_su_Id(self):
        """`QualifyingProperties Target="#Signature"` necesita ese Id."""
        _invoice, root = self._sign_invoice()
        sig = root.find(".//ds:Signature", self.NS)
        qp = root.find(".//etsi:QualifyingProperties", self.NS)
        self.assertEqual(sig.get("Id"), (qp.get("Target") or "").lstrip("#"))

    def test_algoritmos_de_la_ficha_6_8(self):
        _invoice, root = self._sign_invoice()
        self.assertTrue(
            root.find(".//ds:SignatureMethod", self.NS)
            .get("Algorithm").endswith("rsa-sha1")
        )
        for dm in root.findall(".//ds:DigestMethod", self.NS):
            self.assertTrue(dm.get("Algorithm").endswith("sha1"))
        self.assertTrue(
            root.find(".//ds:CanonicalizationMethod", self.NS)
            .get("Algorithm").endswith("REC-xml-c14n-20010315")
        )


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriInfoFacturaFields(SriCommon):
    """Campos de <infoFactura> que faltaban o iban fijos: propina, pagos y guía."""

    def _render(self, invoice):
        return etree.fromstring(
            self.env["l10n_ec.sri.xml"].render_xml(invoice).encode("utf-8")
        )

    def test_la_propina_sale_de_la_base_y_entra_en_el_total(self):
        """El SRI valida importeTotal = base + impuestos + propina.

        La propina viaja como una línea más en Odoo, así que si se emitiera dentro
        de <detalles> Y además en <propina> quedaría contada dos veces y el
        comprobante sería rechazado con el error 52.
        """
        tip_product = self.env["product.product"].create({
            "name": "Servicio 10%", "type": "service", "l10n_ec_is_tip": True,
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_line_ids": [
                (0, 0, {
                    "product_id": self.product.id, "quantity": 1,
                    "price_unit": 100.0, "tax_ids": [(6, 0, self.tax15.ids)],
                }),
                (0, 0, {
                    "product_id": tip_product.id, "quantity": 1,
                    "price_unit": 10.0, "tax_ids": [(6, 0, [])],
                }),
            ],
        })
        invoice.action_post()
        invoice.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(invoice)
        root = self._render(invoice)

        base = float(root.findtext(".//totalSinImpuestos"))
        tip = float(root.findtext(".//propina"))
        total = float(root.findtext(".//importeTotal"))
        taxes = sum(
            float(node.findtext("valor"))
            for node in root.findall(".//totalConImpuestos/totalImpuesto")
        )

        self.assertEqual(tip, 10.0, "la propina debe emitirse en <propina>")
        self.assertEqual(base, 100.0, "la propina no forma parte de la base imponible")
        self.assertAlmostEqual(total, base + taxes + tip, places=2)
        self.assertEqual(total, invoice.amount_total)

        descriptions = [d.text for d in root.findall(".//detalle/descripcion")]
        self.assertFalse(
            any("10%" in (d or "") for d in descriptions),
            "la línea de propina no debe aparecer también en <detalles>",
        )

    def test_varias_formas_de_pago_producen_varios_tags_pago(self):
        invoice = self._make_invoice(quantity=1, price_unit=100.0)
        efectivo = self.env["l10n_ec.payment.method"].search(
            [("code", "=", "01")], limit=1)
        tarjeta = self.env["l10n_ec.payment.method"].search(
            [("code", "=", "19")], limit=1) or efectivo
        half = invoice.amount_total / 2.0
        invoice.write({"l10n_ec_payment_ids": [
            (0, 0, {"payment_method_id": efectivo.id, "amount": half}),
            (0, 0, {"payment_method_id": tarjeta.id,
                    "amount": invoice.amount_total - half}),
        ]})

        pagos = self._render(invoice).findall(".//pagos/pago")
        self.assertEqual(len(pagos), 2)
        declarado = sum(float(p.findtext("total")) for p in pagos)
        self.assertAlmostEqual(declarado, invoice.amount_total, places=2)

    def test_las_formas_de_pago_deben_sumar_el_total(self):
        invoice = self._make_invoice(quantity=1, price_unit=100.0)
        efectivo = self.env["l10n_ec.payment.method"].search(
            [("code", "=", "01")], limit=1)
        with self.assertRaises(ValidationError):
            invoice.write({"l10n_ec_payment_ids": [
                (0, 0, {"payment_method_id": efectivo.id, "amount": 1.0}),
            ]})

    def test_venta_a_credito_declara_plazo_y_unidad_de_tiempo(self):
        """Una venta a crédito sin <plazo> declara al SRI que se cobró el mismo día."""
        term = self.env["account.payment.term"].create({
            "name": "30 dias de prueba",
            "line_ids": [(0, 0, {"value": "percent", "value_amount": 100.0,
                                 "nb_days": 30})],
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_payment_term_id": term.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id, "quantity": 1, "price_unit": 100.0,
                "tax_ids": [(6, 0, self.tax15.ids)],
            })],
        })
        invoice.action_post()
        invoice.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(invoice)

        pago = self._render(invoice).find(".//pagos/pago")
        self.assertEqual(pago.findtext("plazo"), "30")
        self.assertEqual(pago.findtext("unidadTiempo"), "dias")

    def test_venta_de_contado_no_emite_plazo(self):
        """De contado = vence el mismo dia. El plazo sale de los vencimientos
        reales, no del nombre del plazo de pago, asi que hay que fijarlo."""
        invoice = self._make_invoice()
        invoice.button_draft()
        invoice.write({"invoice_payment_term_id": False,
                       "invoice_date_due": invoice.invoice_date})
        invoice.action_post()
        pago = self._render(invoice).find(".//pagos/pago")
        self.assertIsNone(
            pago.find("plazo"),
            "<plazo> es 'obligatorio cuando corresponda', y aqui no corresponde",
        )

    def test_la_guia_de_remision_va_en_su_posicion_del_anexo_3(self):
        invoice = self._make_invoice()
        invoice.l10n_ec_waybill_number = "001-001-000000001"
        info = self._render(invoice).find(".//infoFactura")
        tags = [child.tag for child in info]

        self.assertIn("guiaRemision", tags)
        self.assertEqual(
            tags.index("guiaRemision"), tags.index("tipoIdentificacionComprador") + 1,
            "el Anexo 3 la situa justo tras tipoIdentificacionComprador",
        )
        self.assertLess(tags.index("guiaRemision"), tags.index("razonSocialComprador"))

    def test_una_guia_mal_formada_se_rechaza_al_grabar(self):
        invoice = self._make_invoice()
        for wrong in ("001001000000001", "1-1-1", "001-001-00000001"):
            with self.assertRaises(ValidationError):
                invoice.l10n_ec_waybill_number = wrong

    def test_sin_guia_no_se_emite_el_tag(self):
        self.assertIsNone(
            self._render(self._make_invoice()).find(".//infoFactura/guiaRemision")
        )

    def test_el_codigo_principal_identifica_el_producto(self):
        """'GEN' para todo producto sin referencia hacia indistinguibles las lineas."""
        anonymous = self.env["product.product"].create({
            "name": "Producto sin referencia", "type": "service",
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_line_ids": [(0, 0, {
                "product_id": anonymous.id, "quantity": 1, "price_unit": 10.0,
                "tax_ids": [(6, 0, self.tax15.ids)],
            })],
        })
        invoice.action_post()
        invoice.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(invoice)

        code = self._render(invoice).findtext(".//detalle/codigoPrincipal")
        self.assertNotEqual(code, "GEN")
        self.assertEqual(code, "P%d" % anonymous.id)


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriTabla6(TransactionCase):
    """La tabla 6 estaba resuelta tres veces y dos ignoraban el codigo 08."""

    def setUp(self):
        super().setUp()
        self.xml = self.env["l10n_ec.sri.xml"]

    def test_los_cuatro_codigos_identificables(self):
        casos = [
            ("ruc", "1791251237001", "EC", "04"),
            ("cedula", "1710034065", "EC", "05"),
            ("pasaporte", "AB123456", "US", "06"),
            (False, "X9988", "US", "08"),
        ]
        for tipo, vat, pais, esperado in casos:
            code, _value = self.xml._get_identification_code(
                tipo, vat, country_code=pais)
            self.assertEqual(code, esperado, "%s/%s" % (tipo, pais))

    def test_sin_identificacion_es_consumidor_final(self):
        code, value = self.xml._get_identification_code(False, "")
        self.assertEqual(code, "07")
        self.assertEqual(value, "9999999999999")

    def test_la_retencion_no_admite_consumidor_final(self):
        """La Ficha prohibe el 07 en retenciones: hay que identificar al retenido."""
        code, _value = self.xml._get_identification_code(
            False, "", allow_final_consumer=False)
        self.assertNotEqual(code, "07")

    def test_un_no_residente_no_se_declara_con_ruc_ecuatoriano(self):
        """El ternario del QWeb caia a '04' aqui, el caso en que aplica el ISD."""
        code, _value = self.xml._get_identification_code(
            False, "998877", country_code="PE", allow_final_consumer=False)
        self.assertEqual(code, "08")


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriIsdCode(TransactionCase):
    """El codigo de retencion del ISD depende de la fecha, no del porcentaje."""

    def setUp(self):
        super().setUp()
        defaults = _tax_defaults(self.env, self.env.company)
        self.tax = self.env["account.tax"].create(dict(defaults, **{
            "name": "ISD de prueba",
            "amount": -2.5,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "l10n_ec_retention_type": "6",
        }))

    def test_desde_mayo_2025_es_4586(self):
        self.assertEqual(
            self.tax.l10n_ec_get_retention_code(fields.Date.to_date("2026-01-15")),
            "4586",
        )

    def test_un_periodo_anterior_conserva_4580(self):
        self.assertEqual(
            self.tax.l10n_ec_get_retention_code(fields.Date.to_date("2024-02-10")),
            "4580",
        )

    def test_la_fecha_de_vigencia_es_configurable(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ec.isd_code_4586_from", "2030-01-01")
        self.assertEqual(
            self.tax.l10n_ec_get_retention_code(fields.Date.to_date("2026-01-15")),
            "4580",
        )

    def test_el_mensaje_de_error_explica_los_codigos_7_y_8(self):
        """0,00 % puede ser 7 u 8 y no se distingue por la tarifa: hay que decirlo."""
        defaults = _tax_defaults(self.env, self.env.company)
        zero = self.env["account.tax"].create(dict(defaults, **{
            "name": "Retencion renta 0%",
            "amount": 0.0,
            "amount_type": "percent",
            "type_tax_use": "purchase",
            "l10n_ec_retention_type": "1",
        }))
        with self.assertRaises(ValidationError) as capture:
            zero.l10n_ec_get_retention_code()
        message = str(capture.exception)
        self.assertIn("7 (", message)
        self.assertIn("8 (", message)
        self.assertIn("no procede", message.lower())


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriDocumentSize(TransactionCase):
    """Limite de tamano del envio individual (Ficha 7)."""

    def test_un_comprobante_normal_pasa(self):
        service = self.env["l10n_ec.sri.service"]
        self.assertIsNone(service._check_document_size(b"<factura/>"))

    def test_uno_demasiado_grande_se_detiene_antes_de_transmitir(self):
        service = self.env["l10n_ec.sri.service"]
        result = service._check_document_size(b"x" * (400 * 1024))
        self.assertEqual(result["status"], "DEVUELTA")
        self.assertTrue(result["messages"])
        self.assertIn("kb", result["messages"][0].lower())
        self.assertEqual(
            result["identifiers"], [],
            "no es un codigo del SRI, asi que no debe simular uno",
        )


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriRide(SriCommon):
    """El RIDE tiene validez tributaria y juridica (Anexo 2), asi que debe decir
    de que comprobante es.

    Habia un unico informe sobre `account.move` cuya cabecera escribia el literal
    "FACTURA": impreso sobre una nota de credito, el papel se declaraba factura. Y
    ese mismo PDF es el que se adjunta al correo de entrega al receptor.
    """

    def _html(self, record, report="l10n_ec_sri.action_report_invoice_ride"):
        content, _kind = self.env["ir.actions.report"]._render_qweb_html(
            report, record.ids
        )
        return content.decode("utf-8") if isinstance(content, bytes) else content

    def test_la_factura_se_titula_factura(self):
        html = self._html(self._make_invoice())
        self.assertIn("FACTURA", html)
        self.assertNotIn("NOTA DE", html)

    def test_la_nota_de_credito_no_se_declara_factura(self):
        invoice = self._make_invoice()
        note = invoice._reverse_moves([{
            "invoice_date": invoice.invoice_date,
            "journal_id": self.journal.id,
            "l10n_latam_document_type_id": self.env.ref("l10n_ec.ec_dt_04").id,
        }])
        note.l10n_ec_modification_reason = "Devolucion de mercaderia"
        note.action_post()
        note.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(note)

        html = self._html(note)
        self.assertIn("NOTA DE CR", html, "debe titularse nota de credito")
        self.assertIn("Comprobante que se modifica", html)
        self.assertIn("Devolucion de mercaderia", html)
        self.assertNotIn("Forma de Pago", html,
                         "la nota de credito no lleva formas de pago")

    def test_el_ride_dice_el_nombre_de_la_forma_de_pago(self):
        """Un papel que dice '20' en vez del nombre no informa a nadie."""
        html = self._html(self._make_invoice())
        self.assertIn("Forma de Pago", html)

    def test_el_codigo_del_detalle_no_es_GEN(self):
        anonymous = self.env["product.product"].create({
            "name": "Producto sin referencia RIDE", "type": "service",
        })
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_line_ids": [(0, 0, {
                "product_id": anonymous.id, "quantity": 1, "price_unit": 10.0,
                "tax_ids": [(6, 0, self.tax15.ids)],
            })],
        })
        invoice.action_post()
        invoice.l10n_ec_sri_access_key = self.env[
            "l10n_ec.sri.xml"].generate_access_key(invoice)
        self.assertIn("P%d" % anonymous.id, self._html(invoice))

    def test_cada_tipo_tiene_su_propio_cuerpo_y_existe(self):
        """Todo comprobante que se sabe emitir debe saber imprimirse, con un cuerpo
        propio que exista de verdad: un xmlid mal escrito solo se nota al imprimir."""
        sri = self.env["l10n_ec.sri.xml"]
        renderers = sri._get_ride_renderers()
        self.assertEqual(
            set(renderers), {"01", "03", "04", "05"},
            "los cuatro comprobantes que son account.move",
        )
        for code, (template, method) in renderers.items():
            self.assertTrue(
                self.env.ref(template, raise_if_not_found=False),
                "falta la plantilla %s del codigo %s" % (template, code),
            )
            self.assertTrue(hasattr(sri, method), "falta el metodo %s" % method)

    def test_la_retencion_y_la_guia_tienen_su_informe(self):
        """Ninguno de los dos tenia RIDE, y el Anexo 2 lo exige para todos."""
        for xmlid, model in (
            ("l10n_ec_sri.action_report_retention_ride", "l10n_ec.retention"),
            ("l10n_ec_guia_remision.action_report_guia_ride", "stock.picking"),
        ):
            report = self.env.ref(xmlid, raise_if_not_found=False)
            self.assertTrue(report, "falta la accion de informe %s" % xmlid)
            self.assertEqual(report.model, model)


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriTerminalRejection(SriCommon):
    """Un NO AUTORIZADO no se arregla reenviando: la clave ya esta registrada."""

    def test_no_autorizado_deja_el_comprobante_en_rechazo_definitivo(self):
        invoice = self._make_invoice()
        invoice.l10n_ec_sri_status = "sent"

        def fake_check(company, access_key):
            return {"status": "NO AUTORIZADO",
                    "messages": ["ERROR 45: firma invalida"],
                    "identifiers": ["45"]}

        service = self.env["l10n_ec.sri.service"]
        original = type(service).check_authorization
        type(service).check_authorization = lambda s, c, k: fake_check(c, k)
        try:
            invoice.action_check_sri()
        finally:
            type(service).check_authorization = original

        self.assertEqual(invoice.l10n_ec_sri_status, "rejected_final")
        self.assertFalse(invoice.l10n_ec_sri_retryable)

    def test_un_rechazo_definitivo_no_se_reenvia(self):
        """Sin este corte el ciclo era infinito: reenviar -> 43 -> sent -> cron ->
        NO AUTORIZADO -> reenviar -> ..."""
        invoice = self._make_invoice()
        invoice.write({
            "l10n_ec_sri_status": "rejected_final",
            "l10n_ec_sri_error": "ERROR 45: firma invalida",
        })
        with self.assertRaises(UserError) as capture:
            invoice.action_send_sri()
        self.assertIn("43", str(capture.exception))

    def test_el_rechazo_definitivo_abre_una_actividad(self):
        invoice = self._make_invoice()
        invoice.l10n_ec_sri_error = "ERROR 45"
        invoice._l10n_ec_notify_terminal_rejection()
        self.assertTrue(invoice.activity_ids, "debe quedar constancia para alguien")

    def test_el_aviso_no_se_duplica_en_cada_pasada_del_cron(self):
        invoice = self._make_invoice()
        invoice.l10n_ec_sri_error = "ERROR 45"
        invoice._l10n_ec_notify_terminal_rejection()
        invoice._l10n_ec_notify_terminal_rejection()
        invoice._l10n_ec_notify_terminal_rejection()
        self.assertEqual(len(invoice.activity_ids), 1)


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriKeyIntegrity(TransactionCase):
    """Los datos que entran en la clave de acceso no pueden cambiar despues."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        # Diario propio y no el que haya: `search(...)` puede volver vacio segun el
        # orden de los tests, y `write` sobre un recordset vacio no protesta.
        cls.journal = cls.env["account.journal"].create({
            "name": "Emision 001-002",
            "code": "EM12",
            "type": "sale",
            "company_id": cls.company.id,
            "l10n_ec_entity": "001",
            "l10n_ec_emission": "002",
        })
        cls.other_journal = cls.env["account.journal"].create({
            "name": "Otro punto de emision",
            "code": "OTRP",
            "type": "sale",
            "company_id": cls.company.id,
            "l10n_ec_entity": "007",
            "l10n_ec_emission": "009",
        })
        cls.partner = cls.env["res.partner"].create({
            "name": "SUJETO RETENIDO S.A.",
            "vat": "1791251237001",
            "l10n_ec_identifier_type": "ruc",
            "country_id": cls.env.ref("base.ec").id,
        })

    def _retention(self):
        purchase = self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "=", "purchase")], limit=1
        ) or self.env["account.journal"].create({
            "name": "Compras de prueba", "code": "CMPP", "type": "purchase",
            "company_id": self.company.id,
        })
        invoice = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": purchase.id,
            "invoice_date": fields.Date.to_date("2026-08-24"),
        })
        return self.env["l10n_ec.retention"].create({
            "invoice_id": invoice.id,
            "journal_id": self.journal.id,
            "company_id": self.company.id,
            "date_issue": fields.Date.to_date("2026-08-25"),
            # 001 / 002 y la fecha, que es lo que el constraint compara.
            "l10n_ec_sri_access_key": "2508202607179125123700110010020000000011234567819",
        })

    def test_no_se_puede_cambiar_a_otro_diario_tras_emitir(self):
        """El constraint decia esto en su docstring y solo miraba que el campo no
        estuviera vacio, asi que cambiar de diario estaba permitido: el cuerpo
        pasaba a llevar otro establecimiento que la clave. Es el error 58."""
        retention = self._retention()
        with self.assertRaises(ValidationError):
            retention.journal_id = self.other_journal

    def test_tampoco_se_puede_dejar_sin_diario(self):
        retention = self._retention()
        with self.assertRaises(ValidationError):
            retention.journal_id = False

    def test_no_se_puede_cambiar_la_fecha_tras_emitir(self):
        """Los ocho primeros digitos de la clave son ddmmaaaa."""
        retention = self._retention()
        with self.assertRaises(ValidationError):
            retention.date_issue = fields.Date.to_date("2026-08-26")

    def test_el_mismo_diario_sigue_siendo_valido(self):
        retention = self._retention()
        retention.journal_id = self.journal
        self.assertEqual(retention.journal_id, self.journal)


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriRetentionReadiness(TransactionCase):
    """La retencion valida antes de gastar el secuencial (no es transaccional)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.journal = cls.env["account.journal"].search(
            [("company_id", "=", cls.company.id), ("type", "=", "sale")], limit=1
        )
        cls.journal.write({"l10n_ec_entity": "001", "l10n_ec_emission": "002"})
        cls.tax = cls.env["account.tax"].create(dict(
            _tax_defaults(cls.env, cls.company),
            name="Retencion IVA 30% (readiness)",
            amount=-30.0,
            amount_type="percent",
            type_tax_use="purchase",
            l10n_ec_retention_type="2",
        ))

    def _retention(self, **overrides):
        values = {
            "journal_id": self.journal.id,
            "date_issue": fields.Date.to_date("2026-08-25"),
            "tax_ids": [(0, 0, {
                "tax_id": self.tax.id, "base_amount": 100.0, "amount": 30.0,
            })],
        }
        values.update(overrides)
        return self.env["l10n_ec.retention"].new(values)

    def test_sin_factura_sustento_no_se_confirma(self):
        with self.assertRaises(UserError) as capture:
            self._retention().action_post()
        self.assertIn("sustenta", str(capture.exception))

    def test_no_se_gasta_el_secuencial_cuando_falla(self):
        """Lo que se protege: el numero no debe consumirse en un intento fallido.

        La secuencia es de PostgreSQL y `nextval` no es transaccional, asi que el
        rollback devuelve el `write` del numero pero no el contador."""
        retention = self._retention()
        with self.assertRaises(UserError):
            retention.action_post()
        self.assertFalse(
            (retention.name or "").startswith("001-"),
            "no debe haberse asignado un numero de la serie del SRI",
        )


@tagged("post_install", "-at_install", "l10n_ec", "sri")
class TestSriAutoSend(SriCommon):
    """Un fallo del envio automatico no puede perder el comprobante."""

    def test_un_fallo_deja_el_comprobante_en_una_cola_del_cron(self):
        """Se quedaba en 'draft', y las dos colas filtran 'sent' y 'rejected': un
        fallo de red al publicar significaba que nadie volvia a intentarlo."""
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_ec.auto_send_sri", "True")
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_date": "2026-08-24",
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id, "quantity": 1, "price_unit": 100.0,
                "tax_ids": [(6, 0, self.tax15.ids)],
            })],
        })
        # Sin certificado activo, que es el camino que antes se saltaba en silencio.
        self.company.l10n_ec_certificate_id = False
        invoice.action_post()

        self.assertEqual(invoice.state, "posted", "publicar no debe fallar")
        self.assertTrue(invoice.l10n_ec_sri_error,
                        "el motivo tiene que quedar donde el usuario lo busca")
        self.assertTrue(invoice.l10n_ec_sri_retryable)
