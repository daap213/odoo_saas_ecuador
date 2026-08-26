# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
"""Smoke test de emisión: un comprobante de cada tipo, su XML y su firma.

Complementa a la suite de tests. Aquí se ve el XML que sale de verdad —sus etiquetas,
su versión, su clave de acceso— en vez de un aserto, que es lo que hace falta para
revisar a ojo lo que se va a transmitir antes de una certificación.

NO transmite nada al SRI. Firma con un certificado autofirmado, que el SRI no acepta:
lo que comprueba es que el XML se construye conforme a la Ficha Técnica 2.34 y que el
camino criptográfico funciona. La transacción se revierte al final, así que la base
queda como estaba.

    ./devops/lab.sh up
    ./devops/lab.sh install l10n_ec_full
    cd ../odoo_template && docker compose exec -T odoo \
        odoo shell -d lab --no-http --workers=0 --max-cron-threads=0 \
        < ../odoo_saas_ecuador/devops/smoke_emision.py
"""
from lxml import etree

company = env.company
company.partner_id.write({"vat": "1791251237001", "country_id": env.ref("base.ec").id})
company.write({"street": "Av. Republica E7-197", "l10n_ec_sri_environment": "test",
               "l10n_ec_forced_accounting": True})
if not env["account.account"].search([("company_ids", "in", company.id)], limit=1):
    env["account.chart.template"].try_loading("ec", company, install_demo=False)

sale = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
sale.write({"l10n_ec_entity": "002", "l10n_ec_emission": "003"})
purchase = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1)
purchase.write({"l10n_ec_entity": "002", "l10n_ec_emission": "005",
                "l10n_ec_allow_purchase_liquidation": True})

tax15 = env["account.tax"].search(
    [("type_tax_use", "=", "sale"), ("amount", "=", 15.0),
     ("company_id", "=", company.id)], limit=1)
cliente = env["res.partner"].create({
    "name": "CLIENTE DE PRUEBA S.A.", "vat": "1791251237001",
    "l10n_ec_identifier_type": "ruc", "country_id": env.ref("base.ec").id,
    "street": "Av. Amazonas N35-123"})
proveedor = env["res.partner"].create({
    "name": "Proveedor sin RUC", "vat": "1710034065",
    "l10n_ec_identifier_type": "cedula", "country_id": env.ref("base.ec").id,
    "street": "Barrio La Loma"})
producto = env["product.product"].create({
    "name": "Servicio de prueba", "default_code": "SRV-01", "type": "service"})

SRI = env["l10n_ec.sri.xml"]


def emitir(move):
    move.action_post()
    move.l10n_ec_sri_access_key = SRI.generate_access_key(move)
    return SRI.render_xml(move)


def revisar(nombre, xml, esperado_tag, esperado_ver, esperado_cod, clave):
    root = etree.fromstring(xml.encode("utf-8"))
    def t(tag):
        return root.findtext(".//%s" % tag)
    coherente = (t("estab") == clave[24:27] and t("ptoEmi") == clave[27:30]
                 and t("secuencial") == clave[30:39] and t("codDoc") == clave[8:10])
    ok = (root.tag == esperado_tag and root.get("version") == esperado_ver
          and t("codDoc") == esperado_cod and root.get("id") == "comprobante"
          and coherente and len(clave) == 49 and clave.isdigit())
    print("  %-22s %-18s v%-6s codDoc=%s  clave-coherente=%s  %s"
          % (nombre, root.tag, root.get("version"), t("codDoc"), coherente,
             "OK" if ok else "*** FALLO ***"))
    return xml


print("=== Emision de un comprobante de cada tipo ===")

factura = env["account.move"].create({
    "move_type": "out_invoice", "partner_id": cliente.id, "journal_id": sale.id,
    "invoice_date": "2026-08-25",
    "invoice_line_ids": [(0, 0, {"product_id": producto.id, "quantity": 2,
                                 "price_unit": 100.0,
                                 "tax_ids": [(6, 0, tax15.ids)]})]})
xml_fact = revisar("Factura", emitir(factura), "factura", "1.1.0", "01",
                   factura.l10n_ec_sri_access_key)

nc = factura._reverse_moves([{"invoice_date": factura.invoice_date,
                              "journal_id": sale.id,
                              "l10n_latam_document_type_id": env.ref("l10n_ec.ec_dt_04").id}])
nc.l10n_ec_modification_reason = "Devolucion de mercaderia"
revisar("Nota de credito", emitir(nc), "notaCredito", "1.1.0", "04",
        nc.l10n_ec_sri_access_key)

wiz = env["account.debit.note"].with_context(
    active_model="account.move", active_ids=factura.ids).create(
    {"reason": "Intereses por mora", "copy_lines": True})
wiz.create_debit()
nd = factura.debit_note_ids
nd.l10n_latam_document_type_id = env.ref("l10n_ec.ec_dt_05")
revisar("Nota de debito", emitir(nd), "notaDebito", "1.0.0", "05",
        nd.l10n_ec_sri_access_key)

liq = env["account.move"].create({
    "move_type": "in_invoice", "partner_id": proveedor.id,
    "journal_id": purchase.id, "invoice_date": "2026-08-25",
    "l10n_latam_document_type_id": env.ref("l10n_ec.ec_dt_03").id,
    "invoice_line_ids": [(0, 0, {"product_id": producto.id, "quantity": 1,
                                 "price_unit": 50.0})]})
liq.journal_id = purchase
liq.l10n_latam_document_type_id = env.ref("l10n_ec.ec_dt_03")
revisar("Liquidacion compra", emitir(liq), "liquidacionCompra", "1.1.0", "03",
        liq.l10n_ec_sri_access_key)

pt = env["stock.picking.type"].search(
    [("code", "=", "outgoing"), ("company_id", "=", company.id)], limit=1)
company.l10n_ec_guia_journal_id = sale
cond = env["l10n_ec.driver"].create({
    "name": "Juan Perez", "identification_type": "cedula",
    "identification_number": "1710034065", "license_number": "LIC-1"})
veh = env["l10n_ec.vehicle"].create({"name": "Camion 01", "license_plate": "PCM4567"})
guia = env["stock.picking"].create({
    "partner_id": cliente.id, "picking_type_id": pt.id,
    "location_id": pt.default_location_src_id.id,
    "location_dest_id": pt.default_location_dest_id.id,
    "l10n_ec_driver_id": cond.id, "l10n_ec_vehicle_id": veh.id,
    "l10n_ec_route": "Quito - Ambato",
    "move_ids": [(0, 0, {"product_id": producto.id, "product_uom_qty": 3.0,
                         "location_id": pt.default_location_src_id.id,
                         "location_dest_id": pt.default_location_dest_id.id})]})
guia._generate_access_key()
revisar("Guia de remision", SRI.render_xml(guia), "guiaRemision", "1.1.0", "06",
        guia.l10n_ec_sri_access_key)

print()
print("=== Anexo 26: RUC del proveedor en TODOS los comprobantes ===")
env["ir.config_parameter"].sudo().set_param("l10n_ec.software_provider_ruc",
                                            "1791251237001")
for nombre, rec in (("Factura", factura), ("Nota de credito", nc),
                    ("Nota de debito", nd), ("Liquidacion", liq), ("Guia", guia)):
    root = etree.fromstring(SRI.render_xml(rec).encode("utf-8"))
    campos = {c.get("nombre"): c.text
              for c in root.findall(".//infoAdicional/campoAdicional")}
    print("  %-18s RUC Proveedor = %s" % (nombre, campos.get("RUC Proveedor")))

print()
print("=== Firma XAdES-BES (certificado autofirmado, NO valido ante el SRI) ===")
from odoo.addons.l10n_ec_sri.tests.certificate_fixture import (
    build_test_p12, TEST_P12_PASSWORD)
import base64 as _b64
firmado = env["l10n_ec.sri.signer"].sign_xml(
    xml_fact.encode("utf-8"), _b64.b64encode(build_test_p12()), TEST_P12_PASSWORD)
raiz = etree.fromstring(firmado)
ns = {"ds": "http://www.w3.org/2000/09/xmldsig#"}
sig = raiz.find(".//ds:Signature", ns)
refs = [r.get("URI") for r in raiz.findall(".//ds:Reference", ns)]
print("  firma insertada dentro de <factura>:", sig is not None)
print("  Id de la firma                     :", sig.get("Id"))
print("  referencias firmadas               :", refs)
print("  algoritmo                          :",
      raiz.find(".//ds:SignatureMethod", ns).get("Algorithm").rsplit("#", 1)[-1])

env.cr.rollback()
print()
print("=== Transaccion revertida: la base queda como estaba ===")
