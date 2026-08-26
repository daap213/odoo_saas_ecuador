# Comprueba que los seis RIDE se imprimen y llevan su propio titulo.
import re

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
    "name": "CLIENTE RIDE S.A.", "vat": "1791251237001",
    "l10n_ec_identifier_type": "ruc", "country_id": env.ref("base.ec").id,
    "street": "Av. Amazonas N35-123"})
proveedor = env["res.partner"].create({
    "name": "Proveedor sin RUC", "vat": "1710034065",
    "l10n_ec_identifier_type": "cedula", "country_id": env.ref("base.ec").id,
    "street": "Barrio La Loma"})
producto = env["product.product"].create({
    "name": "Servicio de prueba", "default_code": "SRV-01", "type": "service"})

SRI = env["l10n_ec.sri.xml"]
REPORT = env["ir.actions.report"]


def emitir(move):
    move.action_post()
    move.l10n_ec_sri_access_key = SRI.generate_access_key(move)
    return move


def imprimir(nombre, record, accion, titulo_esperado):
    html, _kind = REPORT._render_qweb_html(accion, record.ids)
    text = html.decode("utf-8") if isinstance(html, bytes) else html
    titulo = re.search(r"<h5[^>]*>([^<]+)</h5>", text)
    encontrado = (titulo.group(1).strip() if titulo else "(sin titulo)")
    ok = titulo_esperado in encontrado
    print("  %-22s %-34s %s" % (nombre, encontrado, "OK" if ok else "*** FALLO ***"))


print("=== RIDE por tipo de comprobante ===")

factura = emitir(env["account.move"].create({
    "move_type": "out_invoice", "partner_id": cliente.id, "journal_id": sale.id,
    "invoice_date": "2026-08-25",
    "invoice_line_ids": [(0, 0, {"product_id": producto.id, "quantity": 2,
                                 "price_unit": 100.0,
                                 "tax_ids": [(6, 0, tax15.ids)]})]}))
imprimir("Factura", factura, "l10n_ec_sri.action_report_invoice_ride", "FACTURA")

nc = factura._reverse_moves([{"invoice_date": factura.invoice_date,
                              "journal_id": sale.id,
                              "l10n_latam_document_type_id": env.ref("l10n_ec.ec_dt_04").id}])
nc.l10n_ec_modification_reason = "Devolucion de mercaderia"
emitir(nc)
imprimir("Nota de credito", nc, "l10n_ec_sri.action_report_invoice_ride", "NOTA DE CR")

wiz = env["account.debit.note"].with_context(
    active_model="account.move", active_ids=factura.ids).create(
    {"reason": "Intereses por mora", "copy_lines": True})
wiz.create_debit()
nd = factura.debit_note_ids
nd.l10n_latam_document_type_id = env.ref("l10n_ec.ec_dt_05")
emitir(nd)
imprimir("Nota de debito", nd, "l10n_ec_sri.action_report_invoice_ride", "NOTA DE D")

liq = env["account.move"].create({
    "move_type": "in_invoice", "partner_id": proveedor.id,
    "journal_id": purchase.id, "invoice_date": "2026-08-25",
    "l10n_latam_document_type_id": env.ref("l10n_ec.ec_dt_03").id,
    "invoice_line_ids": [(0, 0, {"product_id": producto.id, "quantity": 1,
                                 "price_unit": 50.0})]})
liq.journal_id = purchase
liq.l10n_latam_document_type_id = env.ref("l10n_ec.ec_dt_03")
emitir(liq)
imprimir("Liquidacion compra", liq, "l10n_ec_sri.action_report_invoice_ride",
         "LIQUIDACI")

# --- Retencion ---------------------------------------------------------------
retencion = env["l10n_ec.retention"].create({
    "invoice_id": liq.id,
    "partner_id": proveedor.id,
    "company_id": company.id,
    "date_issue": "2026-08-25",
    "journal_id": purchase.id,
})
ret_tax = env["account.tax"].search([
    ("company_id", "=", company.id), ("l10n_ec_code", "!=", False),
    ("type_tax_use", "=", "purchase")], limit=1)
if not ret_tax:
    group = env["account.tax.group"].search([("company_id", "=", company.id)], limit=1)
    ret_tax = env["account.tax"].create({
        "name": "Retencion renta 2.75%", "amount": -2.75, "amount_type": "percent",
        "type_tax_use": "purchase", "l10n_ec_code": "312",
        "l10n_ec_retention_type": "1",
        "tax_group_id": group.id, "country_id": env.ref("base.ec").id})
env["l10n_ec.retention.line"].create({
    "retention_id": retencion.id, "tax_id": ret_tax.id,
    "base_amount": 50.0, "amount": -1.375})
retencion.action_post()
imprimir("Retencion", retencion, "l10n_ec_sri.action_report_retention_ride",
         "RETENCI")

# --- Guia de remision --------------------------------------------------------
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
imprimir("Guia de remision", guia, "l10n_ec_guia_remision.action_report_guia_ride",
         "GU")

env.cr.rollback()
print()
print("=== Transaccion revertida ===")
