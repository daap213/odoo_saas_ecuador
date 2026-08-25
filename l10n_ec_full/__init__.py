# -*- coding: utf-8 -*-
from . import models
from . import wizard


def post_init_hook(env):
    """Post installation hook - set default config."""
    env["ir.config_parameter"].sudo().set_param("l10n_ec.installed", "True")


def uninstall_hook(env):
    """Cleanup on uninstall."""
    pass
