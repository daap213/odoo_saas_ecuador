# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models, _


class L10nEcBusinessTemplate(models.Model):
    """
    Business templates for quick company setup.
    Each template contains products, suppliers, categories, and configuration
    specific to a type of business (Tienda, Panadería, Ferretería, etc.)
    """

    _name = "l10n_ec.business.template"
    _description = "Plantilla de Negocio Ecuador"
    _order = "sequence, name"

    # Basic Info
    name = fields.Char(
        string="Nombre",
        required=True,
        translate=True,
        help="Nombre del tipo de negocio (ej: Tienda de Barrio)",
    )
    code = fields.Char(
        string="Código",
        required=True,
        help="Código interno (ej: tienda_barrio)",
    )
    icon = fields.Char(
        string="Icono",
        default="🏪",
        help="Emoji para mostrar en el selector",
    )
    description = fields.Text(
        string="Descripción",
        translate=True,
        help="Descripción del tipo de negocio",
    )
    sequence = fields.Integer(
        string="Secuencia",
        default=10,
    )
    active = fields.Boolean(
        string="Activo",
        default=True,
    )

    # Template Category
    category = fields.Selection(
        [
            ("retail", "Comercio/Retail"),
            ("food", "Alimentos/Restaurantes"),
            ("services", "Servicios"),
            ("professional", "Profesionales"),
            ("manufacturing", "Manufactura"),
        ],
        string="Categoría",
        required=True,
        default="retail",
    )

    # Size Compatibility
    available_for_simple = fields.Boolean(
        string="Disponible para Simple",
        default=True,
        help="Este template está disponible para negocios pequeños",
    )
    available_for_medium = fields.Boolean(
        string="Disponible para Mediano",
        default=True,
    )
    available_for_enterprise = fields.Boolean(
        string="Disponible para Grande",
        default=True,
    )

    # Template Content Counts
    product_count = fields.Integer(
        string="Productos",
        compute="_compute_counts",
    )
    supplier_count = fields.Integer(
        string="Proveedores",
        compute="_compute_counts",
    )
    category_count = fields.Integer(
        string="Categorías",
        compute="_compute_counts",
    )
    bom_count = fields.Integer(
        string="Recetas/BOM",
        compute="_compute_counts",
    )

    # Related Data
    product_template_ids = fields.One2many(
        "l10n_ec.business.template.product",
        "template_id",
        string="Productos Template",
    )
    supplier_ids = fields.One2many(
        "l10n_ec.business.template.supplier",
        "template_id",
        string="Proveedores Template",
    )
    category_ids = fields.One2many(
        "l10n_ec.business.template.category",
        "template_id",
        string="Categorías Template",
    )

    # Configuration
    enable_pos = fields.Boolean(
        string="Habilitar POS",
        default=True,
    )
    enable_inventory = fields.Boolean(
        string="Habilitar Inventario",
        default=False,
    )
    enable_mrp = fields.Boolean(
        string="Habilitar Producción",
        default=False,
    )

    @api.depends("product_template_ids", "supplier_ids", "category_ids")
    def _compute_counts(self):
        for record in self:
            record.product_count = len(record.product_template_ids)
            record.supplier_count = len(record.supplier_ids)
            record.category_count = len(record.category_ids)
            record.bom_count = len(
                record.product_template_ids.filtered(lambda p: p.has_bom)
            )

    def action_load_template(self, company, size="simple"):
        """
        Load this template into the given company.
        Creates products, suppliers, categories based on size.
        """
        self.ensure_one()

        results = {
            "products_created": 0,
            "suppliers_created": 0,
            "categories_created": 0,
        }

        # Create categories first
        category_map = {}
        for cat in self.category_ids:
            new_cat = self.env["product.category"].create({
                "name": cat.name,
                "parent_id": cat.parent_ref.id if cat.parent_ref else False,
            })
            category_map[cat.code] = new_cat.id
            results["categories_created"] += 1

        # Create suppliers
        for supplier in self.supplier_ids:
            if size == "simple" and not supplier.for_simple:
                continue
            if size == "medium" and not supplier.for_medium:
                continue

            self.env["res.partner"].create({
                "name": supplier.name,
                "vat": supplier.ruc,
                "supplier_rank": 1,
                "company_type": "company",
                "l10n_ec_taxpayer_type": supplier.taxpayer_type,
                "street": supplier.address,
                "phone": supplier.phone,
                "email": supplier.email,
            })
            results["suppliers_created"] += 1

        # Create products
        for product in self.product_template_ids:
            if size == "simple" and not product.for_simple:
                continue
            if size == "medium" and not product.for_medium:
                continue

            # Odoo 19: product.template.type solo admite consu / service / combo.
            # El valor 'product' (almacenable) desapareció; ahora "almacenable" es
            # type='consu' + is_storable=True, que aporta el módulo stock.
            vals = {
                "name": product.name,
                "type": "service" if product.product_type == "service" else "consu",
                "list_price": product.list_price,
                "standard_price": product.cost,
                "categ_id": category_map.get(
                    product.category_code,
                    self.env.ref("product.product_category_all").id
                ),
                "available_in_pos": self.enable_pos,
                "barcode": product.barcode or False,
            }
            if product.product_type == "product":
                # 'is_storable' lo añade el módulo stock, del que depende l10n_ec.
                vals["is_storable"] = True

            # Add taxes
            if product.tax_type == "iva_15":
                # Find or create IVA 15% tax
                tax = self.env["account.tax"].search([
                    ("amount", "=", 15),
                    ("type_tax_use", "=", "sale"),
                    ("company_id", "=", company.id),
                ], limit=1)
                if tax:
                    vals["taxes_id"] = [(6, 0, [tax.id])]

            self.env["product.template"].create(vals)
            results["products_created"] += 1

        return results


class L10nEcBusinessTemplateProduct(models.Model):
    """Products to be created from a business template."""

    _name = "l10n_ec.business.template.product"
    _description = "Producto de Plantilla"
    _order = "sequence, name"

    template_id = fields.Many2one(
        "l10n_ec.business.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    # Product Data
    name = fields.Char(string="Nombre", required=True)
    code = fields.Char(string="Código")
    barcode = fields.Char(string="Código de Barras")
    category_code = fields.Char(string="Código Categoría")

    product_type = fields.Selection(
        [
            ("consu", "Consumible"),
            ("product", "Almacenable"),
            ("service", "Servicio"),
        ],
        string="Tipo",
        default="product",
    )

    list_price = fields.Float(string="Precio Venta", required=True)
    cost = fields.Float(string="Costo")

    tax_type = fields.Selection(
        [
            ("iva_15", "IVA 15%"),
            ("iva_5", "IVA 5%"),
            ("iva_0", "IVA 0%"),
            ("exento", "Exento"),
        ],
        string="IVA",
        default="iva_15",
    )

    # BOM
    has_bom = fields.Boolean(string="Tiene Receta/BOM")
    bom_data = fields.Text(string="Datos BOM (JSON)")

    # Size availability
    for_simple = fields.Boolean(string="Para Simple", default=True)
    for_medium = fields.Boolean(string="Para Mediano", default=True)
    for_enterprise = fields.Boolean(string="Para Grande", default=True)


class L10nEcBusinessTemplateSupplier(models.Model):
    """Suppliers to be created from a business template."""

    _name = "l10n_ec.business.template.supplier"
    _description = "Proveedor de Plantilla"

    template_id = fields.Many2one(
        "l10n_ec.business.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )

    # Supplier Data (REAL Ecuador suppliers)
    name = fields.Char(string="Razón Social", required=True)
    ruc = fields.Char(string="RUC", size=13)
    taxpayer_type = fields.Selection(
        [
            ("general", "General"),
            ("special", "Contribuyente Especial"),
            ("rimpe_e", "RIMPE Emprendedor"),
        ],
        string="Tipo Contribuyente",
        default="general",
    )
    address = fields.Char(string="Dirección")
    phone = fields.Char(string="Teléfono")
    email = fields.Char(string="Email")

    # What they supply
    supply_category = fields.Char(
        string="Categoría Suministro",
        help="Qué productos suministra (ej: Bebidas, Harinas)",
    )

    # Size availability
    for_simple = fields.Boolean(string="Para Simple", default=False)
    for_medium = fields.Boolean(string="Para Mediano", default=True)
    for_enterprise = fields.Boolean(string="Para Grande", default=True)


class L10nEcBusinessTemplateCategory(models.Model):
    """Product categories for a business template."""

    _name = "l10n_ec.business.template.category"
    _description = "Categoría de Plantilla"
    _order = "sequence"

    template_id = fields.Many2one(
        "l10n_ec.business.template",
        string="Template",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)

    name = fields.Char(string="Nombre Categoría", required=True)
    code = fields.Char(string="Código", required=True)
    parent_ref = fields.Many2one(
        "product.category",
        string="Categoría Padre",
    )
