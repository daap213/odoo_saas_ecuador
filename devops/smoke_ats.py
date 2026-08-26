# Genera el ATS de un periodo con una compra, una venta y una retencion.
# No lo presenta a nadie: comprueba que el XML sale y que sus casillas cuadran.
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
purchase.write({"l10n_ec_entity": "002", "l10n_ec_emission": "005"})

tax15 = env["account.tax"].search(
    [("type_tax_use", "=", "sale"), ("amount", "=", 15.0),
     ("company_id", "=", company.id)], limit=1)
tax15_buy = env["account.tax"].search(
    [("type_tax_use", "=", "purchase"), ("amount", "=", 15.0),
     ("company_id", "=", company.id)], limit=1)

cliente = env["res.partner"].create({
    "name": "CLIENTE ATS S.A.", "vat": "1791251237001",
    "l10n_ec_identifier_type": "ruc", "country_id": env.ref("base.ec").id})
proveedor = env["res.partner"].create({
    "name": "PROVEEDOR ATS S.A.", "vat": "1710034065001",
    "l10n_ec_identifier_type": "ruc", "country_id": env.ref("base.ec").id})
producto = env["product.product"].create({
    "name": "Servicio ATS", "default_code": "ATS-01", "type": "service"})

PERIODO = ("08", "2026")
FECHA = "2026-08-10"


def factura(move_type, partner, journal, doc_xmlid, taxes, numero):
    move = env["account.move"].create({
        "move_type": move_type, "partner_id": partner.id, "journal_id": journal.id,
        "invoice_date": FECHA,
        "l10n_latam_document_type_id": env.ref(doc_xmlid).id,
        "invoice_line_ids": [(0, 0, {
            "product_id": producto.id, "quantity": 1, "price_unit": 100.0,
            "tax_ids": [(6, 0, taxes.ids)]})]})
    move.l10n_latam_document_type_id = env.ref(doc_xmlid)
    # En compras el numero lo pone el proveedor y hay que darlo ANTES de publicar;
    # en ventas lo genera Odoo con la secuencia del diario.
    if move_type.startswith("in_"):
        move.l10n_latam_document_number = numero
    move.action_post()
    move.l10n_ec_sri_access_key = env["l10n_ec.sri.xml"].generate_access_key(move)
    return move


print("=== Datos del periodo ===")
compra = factura("in_invoice", proveedor, purchase, "l10n_ec.ec_dt_01",
                 tax15_buy, "002-005-000000001")
compra.l10n_ec_sustento_code = "01"
venta = factura("out_invoice", cliente, sale, "l10n_ec.ec_dt_01",
                tax15, "002-003-000000001")
print("  compra %s  venta %s" % (compra.l10n_latam_document_number,
                                 venta.l10n_latam_document_number))

group = env["account.tax.group"].search([("company_id", "=", company.id)], limit=1)
ret_tax = env["account.tax"].create({
    "name": "Retencion renta 2.75% (ATS)", "amount": -2.75, "amount_type": "percent",
    "type_tax_use": "purchase", "l10n_ec_code": "312", "l10n_ec_retention_type": "1",
    "tax_group_id": group.id, "country_id": env.ref("base.ec").id})
retencion = env["l10n_ec.retention"].create({
    "invoice_id": compra.id, "journal_id": purchase.id, "company_id": company.id,
    "date_issue": FECHA,
    "tax_ids": [(0, 0, {"tax_id": ret_tax.id, "base_amount": 100.0, "amount": -2.75})]})
retencion.action_post()
retencion.l10n_ec_sri_access_key = env[
    "l10n_ec.sri.retention.xml"]._generate_retention_access_key(retencion)
retencion.l10n_ec_sri_status = "authorized"
print("  retencion %s" % retencion.name)

print()
print("=== Generacion del ATS ===")
wizard = env["l10n_ec.ats.wizard"].create({
    "date_month": PERIODO[0], "date_year": PERIODO[1], "company_id": company.id})
xml = wizard.generate_xml()
root = etree.fromstring(xml)


def t(path):
    node = root.find(path)
    return node.text if node is not None else "(ausente)"


print("  raiz                       :", root.tag)
print("  informante                 :", t("IdInformante"))
print("  periodo                    : %s/%s" % (t("Mes"), t("Anio")))
print("  numEstabRuc                :", t("numEstabRuc"))
print("  compras declaradas         :", len(root.findall(".//detalleCompras")))
print("  ventas declaradas          :", len(root.findall(".//detalleVentas")))
print("  establecimientos           :", len(root.findall(".//ventaEst")))

compra_xml = root.find(".//detalleCompras")
print()
print("  --- primera compra ---")
for tag in ("codSustento", "tpIdProv", "idProv", "tipoComprobante",
            "establecimiento", "puntoEmision", "secuencial", "autorizacion",
            "baseNoGraIva", "baseImponible", "baseImpGrav", "baseImpExe",
            "montoIce", "montoIva", "estabRetencion1", "autRetencion1"):
    node = compra_xml.find(tag)
    print("    %-18s %s" % (tag, node.text if node is not None else "(ausente)"))
air = compra_xml.find(".//detalleAir")
if air is not None:
    print("    AIR codRetAir      %s  base %s  val %s"
          % (air.findtext("codRetAir"), air.findtext("baseImpAir"),
             air.findtext("valRetAir")))

venta_xml = root.find(".//detalleVentas")
print()
print("  --- primera venta ---")
for tag in ("tpIdCliente", "idCliente", "parteRelVentas", "tipoComprobante",
            "numeroComprobantes", "baseImpGrav", "montoIva", "montoIce",
            "valorRetIva"):
    node = venta_xml.find(tag)
    print("    %-18s %s" % (tag, node.text if node is not None else "(ausente)"))

est = root.find(".//ventaEst")
print()
print("  --- establecimiento ---")
print("    codEstab           %s  ventasEstab %s"
      % (est.findtext("codEstab"), est.findtext("ventasEstab")))

print()
inventados = [x for x in ("9999999999", "999999999", "0000000000")
              if x in xml.decode("utf-8")]
print("=== Valores inventados en el XML:", inventados or "ninguno", "===")

env.cr.rollback()
print("=== Transaccion revertida ===")
