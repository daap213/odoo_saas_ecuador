# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
#
# Copyright 2026 Somatech.dev
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).

import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Configura automáticamente Odoo para Ecuador al instalar la localización
    y abre el asistente de configuración de empresa.
    """
    _logger.info("🇪🇨 Iniciando configuración automática de localización Ecuador...")

    # =========================================================================
    # 1. INSTALAR IDIOMA ESPAÑOL ECUADOR
    # =========================================================================
    try:
        lang = env["res.lang"]._activate_lang("es_EC")
        if not lang:
            lang = env["res.lang"]._activate_lang("es_ES")
        _logger.info("✅ Idioma Español activado")
    except Exception as e:
        _logger.warning(f"⚠️ No se pudo activar idioma español: {e}")

    # =========================================================================
    # 2. CONFIGURAR COMPAÑÍA PRINCIPAL (PAÍS Y MONEDA)
    # =========================================================================
    try:
        company = env.company
        ecuador = env.ref("base.ec", raise_if_not_found=False)
        usd = env.ref("base.USD", raise_if_not_found=False)

        company_vals = {}
        if ecuador:
            company_vals["country_id"] = ecuador.id
        if usd:
            company_vals["currency_id"] = usd.id

        if company_vals:
            company.write(company_vals)
            _logger.info("✅ Compañía configurada para Ecuador")
    except Exception as e:
        _logger.warning(f"⚠️ Error configurando compañía: {e}")

    # =========================================================================
    # 3. CONFIGURAR USUARIO ADMIN
    # =========================================================================
    try:
        admin_user = env.ref("base.user_admin", raise_if_not_found=False)
        if admin_user:
            user_vals = {"tz": "America/Guayaquil"}
            if env["res.lang"].search([("code", "=", "es_EC")]):
                user_vals["lang"] = "es_EC"
            elif env["res.lang"].search([("code", "=", "es_ES")]):
                user_vals["lang"] = "es_ES"
            admin_user.write(user_vals)
            _logger.info("✅ Usuario admin configurado")
    except Exception as e:
        _logger.warning(f"⚠️ Error configurando usuario: {e}")

    # =========================================================================
    # 4. ENSURE CRITICAL PARAMETERS EXIST (from XML data - no hardcoding)
    # XML data files (l10n_ec_sri_config.xml, l10n_ec_payroll_data.xml) are authoritative.
    # This only logs what was loaded, does NOT override.
    # =========================================================================
    try:
        IrConfigParam = env["ir.config_parameter"].sudo()
        # Log the loaded values from XML files (for verification only)
        sbu = IrConfigParam.get_param("l10n_ec.sbu", False)
        iva = IrConfigParam.get_param("l10n_ec.iva_rate", False)
        iess_p = IrConfigParam.get_param("l10n_ec.iess_aporte_personal", False)
        iess_e = IrConfigParam.get_param("l10n_ec.iess_aporte_patronal", False)
        _logger.info(
            f"✅ Parámetros cargados desde XML: SBU={sbu}, IVA={iva}%, IESS Personal={iess_p}%, IESS Patronal={iess_e}%"
        )
    except Exception as e:
        _logger.warning(f"⚠️ Error verificando parámetros: {e}")

    # =========================================================================
    # 5. ACTIVAR MONEDA USD
    # =========================================================================
    try:
        usd_currency = env.ref("base.USD", raise_if_not_found=False)
        if usd_currency and not usd_currency.active:
            usd_currency.active = True
            _logger.info("✅ Moneda USD activada")
    except Exception as e:
        _logger.warning(f"⚠️ Error activando USD: {e}")

    _logger.info(
        "🇪🇨 ¡Localización Ecuador configurada! Abriendo asistente de empresa..."
    )

    # =========================================================================
    # 6. ABRIR WIZARD DE CONFIGURACIÓN DE EMPRESA
    # =========================================================================
    # Note: We can't directly open a wizard from post_init_hook because
    # the request context isn't available. Instead, we create a todo item
    # that will prompt the user to configure the company.
    try:
        # Create a to-do action for the user
        env["ir.actions.todo"].create(
            {
                "action_id": env.ref("l10n_ec_full.action_l10n_ec_company_setup_wizard").id,
                "state": "open",
                "name": "Configurar Empresa Ecuador",
            }
        )
        _logger.info("✅ Tarea de configuración creada")
    except Exception as e:
        _logger.warning(f"⚠️ No se pudo crear tarea de configuración: {e}")


def uninstall_hook(env):
    """Limpia parámetros al desinstalar."""
    _logger.info("Desinstalando localización Ecuador...")
    try:
        IrConfigParam = env["ir.config_parameter"].sudo()
        params = [
            "l10n_ec.sbu",
            "l10n_ec.sbu_year",
            "l10n_ec.iess_personal",
            "l10n_ec.iess_patronal",
            "l10n_ec.iva_rate",
            "l10n_ec.consumidor_final_limit",
            "l10n_ec.sri_environment",
            "l10n_ec.obligado_contabilidad",
            "l10n_ec.contribuyente_especial",
            "l10n_ec.agente_retencion",
        ]
        for param in params:
            IrConfigParam.set_param(param, False)
    except Exception as e:
        _logger.warning(f"Error en desinstalación: {e}")
