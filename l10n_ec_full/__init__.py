# -*- coding: utf-8 -*-
from . import models
from . import wizard
from . import hooks


def post_init_hook(env):
    """Tras instalar: idioma es_EC, país, moneda y apertura del asistente.

    Todo eso vivía en `hooks.py` y NUNCA se ejecutaba: el manifest declara
    `"post_init_hook": "post_init_hook"`, que Odoo resuelve contra ESTE módulo, y aquí
    sólo se escribía un parámetro. El resultado era que el asistente de configuración
    de empresa no se abría solo y la base quedaba sin idioma ni moneda ecuatorianos.
    """
    env["ir.config_parameter"].sudo().set_param("l10n_ec.installed", "True")
    hooks.post_init_hook(env)


def uninstall_hook(env):
    """Cleanup on uninstall."""
    hooks.uninstall_hook(env)
