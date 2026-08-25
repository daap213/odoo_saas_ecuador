# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class L10nEcCompanySetupWizard(models.TransientModel):
    """
    Wizard para configurar la empresa ecuatoriana después de instalar la localización.
    Auto-carga datos del SRI cuando se ingresa el RUC.
    """

    _name = "l10n_ec.company.setup.wizard"
    _description = "Asistente de Configuración de Empresa Ecuador"

    # Search Options
    search_type = fields.Selection(
        [
            ("ruc", "Buscar por RUC"),
            ("name", "Buscar por Nombre"),
        ],
        string="Tipo de Búsqueda",
        default="ruc",
    )

    search_name = fields.Char(
        string="Buscar por Nombre",
        help="Ingrese el nombre de la empresa para buscar en el SRI",
    )

    # Company Info (auto-loaded from SRI)
    company_ruc = fields.Char(
        string="RUC",
        size=13,
        help="Ingrese el RUC y los datos se cargarán automáticamente del SRI",
    )
    company_name = fields.Char(
        string="Razón Social", help="Se carga automáticamente del SRI"
    )
    commercial_name = fields.Char(
        string="Nombre Comercial", help="Se carga automáticamente del SRI"
    )

    # Status from SRI
    sri_estado = fields.Char(string="Estado SRI", readonly=True)
    sri_tipo_contribuyente = fields.Char(string="Tipo Contribuyente", readonly=True)
    sri_clase_contribuyente = fields.Char(string="Clase Contribuyente", readonly=True)
    sri_actividad = fields.Char(string="Actividad Económica", readonly=True)

    # Address (auto-loaded)
    street = fields.Char(string="Dirección")
    city = fields.Char(string="Ciudad")
    province = fields.Char(string="Provincia")
    phone = fields.Char(string="Teléfono")
    email = fields.Char(string="Correo Electrónico")
    website = fields.Char(string="Sitio Web")

    # SRI Settings
    sri_environment = fields.Selection(
        [
            ("test", "Pruebas (Desarrollo)"),
            ("production", "Producción (Real)"),
        ],
        string="Ambiente SRI",
        default="test",
        required=True,
    )

    obligado_contabilidad = fields.Boolean(
        string="Obligado a Llevar Contabilidad", help="Se carga automáticamente del SRI"
    )

    contribuyente_especial = fields.Char(
        string="Nº Contribuyente Especial", help="Se carga automáticamente del SRI"
    )

    agente_retencion = fields.Char(
        string="Nº Agente de Retención", help="Se carga automáticamente del SRI"
    )

    regimen_rimpe = fields.Char(string="Régimen RIMPE", readonly=True)

    # =========================================================================
    # MULTI-STEP WIZARD CONTROL
    # =========================================================================
    current_step = fields.Integer(
        string="Paso Actual",
        default=1,
        help="Control de navegación del wizard: 1=Negocio, 2=Tamaño, 3=Empresa, "
             "4=Datos, 5=Confirmar",
    )

    # =========================================================================
    # PASO 1: TIPO DE NEGOCIO (Business Template)
    # =========================================================================
    business_template_id = fields.Many2one(
        "l10n_ec.business.template",
        string="Tipo de Negocio",
        help="Seleccione el tipo de negocio para cargar productos y proveedores",
    )

    # =========================================================================
    # PASO 2: TAMAÑO DEL NEGOCIO
    # =========================================================================
    business_size = fields.Selection(
        [
            ("simple", "Pequeño (1-3 empleados, solo vender)"),
            ("medium", "Mediano (4-15 empleados, con inventario)"),
            ("enterprise", "Grande (16+ empleados, ERP completo)"),
        ],
        string="Tamaño del Negocio",
        default="simple",
        help="Define qué módulos y funcionalidades se activarán",
    )
    employee_count = fields.Selection(
        [
            ("1-3", "1-3 empleados"),
            ("4-10", "4-10 empleados"),
            ("11-15", "11-15 empleados"),
            ("16+", "Más de 15 empleados"),
        ],
        string="Número de Empleados",
    )
    location_count = fields.Selection(
        [
            ("1", "1 local"),
            ("2-3", "2-3 locales"),
            ("4+", "Más de 3 locales"),
        ],
        string="Número de Locales",
        default="1",
    )
    needs_inventory = fields.Boolean(
        string="Necesito Control de Inventario",
        default=False,
    )
    needs_purchases = fields.Boolean(
        string="Compro a Proveedores con Factura",
        default=False,
    )

    # =========================================================================
    # PASO 2: PLAN DE CUENTAS
    # =========================================================================
    chart_template = fields.Selection(
        [
            ("ecuador_niif", "Plan Ecuador NIIF PYMES (Recomendado)"),
            ("ecuador_nif", "Plan Ecuador NIF"),
        ],
        string="Plan de Cuentas",
        default="ecuador_niif",
        help="Seleccione el plan de cuentas a instalar",
    )

    # =========================================================================
    # PASO 3: FACTURACIÓN ELECTRÓNICA
    # =========================================================================
    certificate_file = fields.Binary(
        string="Certificado Digital (.p12)",
        help="Archivo .p12 del certificado de firma electrónica (BCE, Security Data, etc.)",
    )
    certificate_filename = fields.Char(string="Nombre Certificado")
    certificate_password = fields.Char(
        string="Contraseña Certificado",
        help="Contraseña del certificado .p12",
    )
    certificate_valid = fields.Boolean(
        string="Certificado Válido",
        readonly=True,
        help="Se valida automáticamente al subir el archivo",
    )
    certificate_owner = fields.Char(
        string="Titular Certificado",
        readonly=True,
        help="Nombre del titular detectado del certificado",
    )
    certificate_expiry = fields.Date(
        string="Vencimiento Certificado",
        readonly=True,
    )

    # Punto de emisión
    establecimiento = fields.Char(
        string="Establecimiento",
        default="001",
        size=3,
        help="Código de establecimiento SRI (3 dígitos)",
    )
    punto_emision = fields.Char(
        string="Punto de Emisión",
        default="001",
        size=3,
        help="Código de punto de emisión SRI (3 dígitos)",
    )
    secuencia_inicio = fields.Integer(
        string="Secuencia Inicial",
        default=1,
        help="Número inicial para la secuencia de documentos",
    )

    # =========================================================================
    # PASO 4: NÓMINA / IESS
    # =========================================================================
    payroll_region = fields.Selection(
        [
            ("sierra", "Sierra / Oriente"),
            ("costa", "Costa / Galápagos"),
        ],
        string="Región Laboral",
        default="sierra",
        help="Define la fecha del Décimo Cuarto: Sierra=Agosto, Costa=Marzo",
    )
    payroll_period = fields.Selection(
        [
            ("monthly", "Mensual"),
            ("biweekly", "Quincenal"),
        ],
        string="Período de Pago",
        default="monthly",
    )
    fondos_reserva_mode = fields.Selection(
        [
            ("monthly", "Pago Mensual (vía IESS)"),
            ("accumulated", "Acumulado (pago directo)"),
        ],
        string="Fondos de Reserva",
        default="monthly",
        help="Forma de pago de fondos de reserva después del primer año",
    )

    # Demo Data Options - User controlled
    install_demo_data = fields.Boolean(
        string="Instalar Datos de Demostración",
        default=False,
        help="Habilita la instalación de datos de prueba",
    )
    demo_customers = fields.Boolean(
        string="Clientes Demo",
        default=True,
        help="Clientes de prueba: Natural, Sociedad, RIMPE, Especial, Exportador",
    )
    demo_suppliers = fields.Boolean(
        string="Proveedores Demo",
        default=True,
        help="Proveedores para probar retenciones: Profesional, Comercial, Inmuebles",
    )
    demo_employees = fields.Boolean(
        string="Empleados Demo",
        default=True,
        help="Empleados para nómina: Sierra, Costa, Galápagos",
    )
    demo_foreign = fields.Boolean(
        string="Partners Extranjeros Demo",
        default=True,
        help="Partners del exterior para probar ISD y exportaciones",
    )

    # Status
    sri_loaded = fields.Boolean(string="Datos Cargados del SRI", default=False)
    sri_message = fields.Char(string="Mensaje SRI", readonly=True)

    @api.onchange("company_ruc")
    def _onchange_company_ruc(self):
        """Auto-cargar datos del SRI cuando se ingresa un RUC válido."""
        if not self.company_ruc:
            return

        ruc = self.company_ruc.strip()

        # Solo consultar si tiene 13 dígitos
        if len(ruc) != 13 or not ruc.isdigit():
            self.sri_message = "Ingrese un RUC válido de 13 dígitos"
            self.sri_loaded = False
            return

        # Consultar SRI
        try:
            service = self.env["l10n_ec.sri.ruc.service"]
            result = service.consultar_ruc(ruc)

            if result["success"]:
                data = result["data"]

                # Auto-completar campos
                self.company_name = data.get("razon_social", "")
                self.commercial_name = data.get("nombre_comercial", "")
                self.street = data.get("direccion", "")
                self.city = data.get("canton", "")
                self.province = data.get("provincia", "")
                self.phone = data.get("telefono", "")
                self.email = data.get("email", "")

                # Datos del SRI
                self.sri_estado = data.get("estado", "")
                self.sri_tipo_contribuyente = data.get("tipo_contribuyente", "")
                self.sri_clase_contribuyente = data.get("clase_contribuyente", "")
                self.sri_actividad = data.get("actividad_economica", "")
                self.obligado_contabilidad = data.get("obligado_contabilidad", False)
                self.contribuyente_especial = data.get("contribuyente_especial", "")
                self.agente_retencion = data.get("agente_retencion", "")
                self.regimen_rimpe = data.get("regimen_rimpe", "")

                self.sri_loaded = True
                self.sri_message = (
                    f"✅ Datos cargados del SRI - Estado: {data.get('estado', 'N/A')}"
                )

                # Advertir si no está ACTIVO
                if data.get("estado", "").upper() != "ACTIVO":
                    return {
                        "warning": {
                            "title": "Contribuyente No Activo",
                            "message": f"El contribuyente tiene estado: {data.get('estado')}. Verifique en el SRI.",
                        }
                    }
            else:
                self.sri_loaded = False
                self.sri_message = f"❌ {result.get('error', 'Error desconocido')}"

        except Exception as e:
            self.sri_loaded = False
            self.sri_message = f"❌ Error al consultar SRI: {str(e)}"

    def action_search_by_name(self):
        """Buscar contribuyentes por nombre en el SRI."""
        self.ensure_one()

        if not self.search_name or len(self.search_name) < 3:
            raise ValidationError(_("Ingrese al menos 3 caracteres para buscar"))

        service = self.env["l10n_ec.sri.ruc.service"]
        result = service.consultar_por_nombre(self.search_name)

        if not result["success"]:
            raise ValidationError(_(result.get("error", "Error en búsqueda")))

        # Crear registros temporales para selección
        resultados = result["data"]

        if len(resultados) == 1:
            # Si solo hay uno, cargar directamente
            self.company_ruc = resultados[0].get("ruc")
            return

        # Si hay múltiples, mostrar lista para seleccionar
        return {
            "type": "ir.actions.act_window",
            "name": f"Resultados: {self.search_name}",
            "res_model": "l10n_ec.ruc.search.result",
            "view_mode": "tree",
            "target": "new",
            "context": {
                "search_results": resultados,
                "wizard_id": self.id,
            },
        }

    def action_configure_company(self):
        """Aplica la configuración a la empresa."""
        self.ensure_one()

        if not self.company_ruc or not self.company_name:
            raise ValidationError(_("Debe ingresar el RUC y la Razón Social"))

        company = self.env.company
        ecuador = self.env.ref("base.ec")

        # Buscar o crear provincia
        province_id = False
        if self.province:
            province = self.env["res.country.state"].search(
                [("name", "ilike", self.province), ("country_id.code", "=", "EC")],
                limit=1,
            )
            province_id = province.id if province else False

        # Update company
        company.write(
            {
                "name": self.company_name,
                "vat": self.company_ruc,
                "company_registry": self.commercial_name or self.company_name,
                "street": self.street,
                "city": self.city,
                "state_id": province_id,
                "country_id": ecuador.id,
                "phone": self.phone,
                "email": self.email,
                "website": self.website,
            }
        )

        # Set SRI parameters
        IrConfigParam = self.env["ir.config_parameter"].sudo()
        IrConfigParam.set_param("l10n_ec.sri_environment", self.sri_environment)
        IrConfigParam.set_param(
            "l10n_ec.obligado_contabilidad", str(self.obligado_contabilidad)
        )

        if self.contribuyente_especial:
            IrConfigParam.set_param(
                "l10n_ec.contribuyente_especial", self.contribuyente_especial
            )

        if self.agente_retencion:
            IrConfigParam.set_param("l10n_ec.agente_retencion", self.agente_retencion)

        # Install demo data if selected
        demo_message = ""
        if self.install_demo_data:
            demo_count = self._install_demo_data(company)
            demo_message = f" Se instalaron {demo_count} partners de demostración."

        # Success notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("✅ Empresa Configurada"),
                "message": _(
                    "La empresa %s ha sido configurada correctamente para Ecuador.%s"
                )
                % (self.company_name, demo_message),
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.act_window",
                    "res_model": "res.config.settings",
                    "view_mode": "form",
                    "target": "current",
                },
            },
        }

    def _install_demo_data(self, company):
        """
        Instala datos de demostración controlados por el usuario.
        Carga partners de prueba según categorías seleccionadas.
        """
        import os
        from lxml import etree

        # Path to demo data file
        demo_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'l10n_ec_base', 'demo', 'l10n_ec_demo_partners.xml'
        )

        if not os.path.exists(demo_file):
            return 0

        # Define which xml_ids belong to each category
        customer_ids = [
            # Personas Naturales
            'demo_customer_natural', 'demo_customer_tercera_edad',
            'demo_customer_discapacidad', 'demo_customer_natural_obligado',
            'demo_customer_artesano',
            # Personas Jurídicas
            'demo_customer_sociedad', 'demo_customer_especial',
            'demo_customer_rimpe_e', 'demo_customer_rimpe_p',
            'demo_customer_final', 'demo_customer_exporter',
            # Sector Público
            'demo_customer_gobierno', 'demo_customer_empresa_publica',
            # Entidades Especiales
            'demo_customer_fundacion', 'demo_customer_ong',
            'demo_customer_cooperativa', 'demo_customer_zede',
            'demo_customer_nueva_empresa',
        ]
        supplier_ids = [
            'demo_supplier_profesional', 'demo_supplier_comercial',
            'demo_supplier_especial', 'demo_supplier_informal',
            'demo_supplier_arrendador', 'demo_supplier_transporte',
            'demo_supplier_gobierno', 'demo_supplier_seguros',
            'demo_supplier_banco', 'demo_supplier_publicidad',
            'demo_supplier_notario',
        ]
        employee_ids = [
            'demo_employee_sierra', 'demo_employee_costa',
            'demo_employee_galapagos',
        ]
        foreign_ids = [
            'demo_supplier_usa', 'demo_customer_colombia',
        ]

        # Build list of allowed xml_ids based on user selection
        allowed_ids = []
        if self.demo_customers:
            allowed_ids.extend(customer_ids)
        if self.demo_suppliers:
            allowed_ids.extend(supplier_ids)
        if self.demo_employees:
            allowed_ids.extend(employee_ids)
        if self.demo_foreign:
            allowed_ids.extend(foreign_ids)

        if not allowed_ids:
            return 0

        # Load via ir.model.data
        count = 0
        Partner = self.env['res.partner'].with_company(company)

        # Parse XML and create records
        tree = etree.parse(demo_file)
        root = tree.getroot()

        for record in root.findall(".//record[@model='res.partner']"):
            xml_id = record.get('id')

            # Skip if not in allowed categories
            if xml_id not in allowed_ids:
                continue

            full_xml_id = f"l10n_ec_base.{xml_id}"

            # Check if already exists
            existing = self.env.ref(full_xml_id, raise_if_not_found=False)
            if existing:
                continue

            # Build values from XML
            vals = {'company_id': company.id}
            for field in record.findall('field'):
                fname = field.get('name')
                fref = field.get('ref')
                feval = field.get('eval')

                if fref:
                    ref_record = self.env.ref(fref, raise_if_not_found=False)
                    vals[fname] = ref_record.id if ref_record else False
                elif feval:
                    vals[fname] = eval(feval)
                else:
                    vals[fname] = field.text

            try:
                partner = Partner.create(vals)
                # Register xml_id
                self.env['ir.model.data'].create({
                    'name': xml_id,
                    'module': 'l10n_ec_base',
                    'model': 'res.partner',
                    'res_id': partner.id,
                    'noupdate': True,
                })
                count += 1
            except Exception:
                pass  # Skip if error

        return count

    # =========================================================================
    # MULTI-STEP NAVIGATION
    # =========================================================================
    def action_next_step(self):
        """Avanza al siguiente paso del wizard."""
        self.ensure_one()

        # Validar paso actual antes de avanzar
        if self.current_step == 1:
            if not self.company_ruc or not self.company_name:
                raise ValidationError(_("Complete los datos de la empresa antes de continuar"))

        elif self.current_step == 3:
            # Validar certificado si fue subido
            if self.certificate_file and not self.certificate_valid:
                raise ValidationError(_("El certificado no es válido"))

        if self.current_step < 6:
            self.current_step += 1

        return self._get_wizard_action()

    def action_previous_step(self):
        """Retrocede al paso anterior del wizard."""
        self.ensure_one()
        if self.current_step > 1:
            self.current_step -= 1
        return self._get_wizard_action()

    def action_go_to_step(self, step):
        """Ir a un paso específico."""
        self.ensure_one()
        if 1 <= step <= 6:
            self.current_step = step
        return self._get_wizard_action()

    def _get_wizard_action(self):
        """Devuelve la acción del wizard para recargar la vista."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    @api.onchange("certificate_file", "certificate_password")
    def _onchange_certificate(self):
        """Valida el certificado cuando se sube o cambia la contraseña."""
        if not self.certificate_file or not self.certificate_password:
            self.certificate_valid = False
            self.certificate_owner = ""
            self.certificate_expiry = False
            return

        # Validate certificate using cryptography library
        import base64
        try:
            from cryptography.hazmat.primitives.serialization import pkcs12
            from cryptography import x509

            cert_data = base64.b64decode(self.certificate_file)
            private_key, certificate, additional = pkcs12.load_key_and_certificates(
                cert_data, self.certificate_password.encode()
            )

            if certificate:
                # Extract owner name
                subject = certificate.subject
                for attr in subject:
                    if attr.oid == x509.oid.NameOID.COMMON_NAME:
                        self.certificate_owner = attr.value
                        break

                # Extract expiry date
                self.certificate_expiry = certificate.not_valid_after_utc.date()
                self.certificate_valid = True
            else:
                self.certificate_valid = False
                self.sri_message = "Certificado no contiene información válida"

        except Exception as e:
            self.certificate_valid = False
            self.certificate_owner = ""
            self.certificate_expiry = False
            self.sri_message = f"Error al validar certificado: {str(e)}"

    def action_skip_wizard(self):
        """Permite saltar el wizard y configurar después."""
        return {"type": "ir.actions.act_window_close"}
