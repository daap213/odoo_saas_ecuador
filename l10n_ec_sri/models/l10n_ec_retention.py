# -*- coding: utf-8 -*-
import base64

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from .account_move import l10n_ec_run_isolated


class L10nEcRetention(models.Model):
    _name = "l10n_ec.retention"
    _description = "Ecuadorian Withholding (Retención)"
    _inherit = ["portal.mixin", "mail.thread", "mail.activity.mixin"]

    name = fields.Char(
        string="Number",
        required=True,
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _("New"),
    )
    invoice_id = fields.Many2one(
        "account.move",
        string="Invoice",
        domain="[('move_type', '=', 'in_invoice')]",
        required=True,
    )
    partner_id = fields.Many2one(
        "res.partner", related="invoice_id.partner_id", string="Supplier", store=True
    )
    date_issue = fields.Date(
        string="Date Issue", default=fields.Date.context_today, required=True
    )

    # De aquí salen el establecimiento y el punto de emisión del comprobante.
    #
    # Sin este campo, `_split_number` no encontraba de dónde sacarlos y caía a un
    # `001-001` fijo: cualquier emisor cuyo punto de emisión fuera otro recibía
    # rechazo del SRI, que valida estab/ptoEmi contra los establecimientos
    # registrados en el RUC. Los dos campos los aporta el `l10n_ec` oficial.
    # El dominio filtra por tener los códigos SRI, no por `type`: lo que hace válido
    # a un diario aquí es que aporte establecimiento y punto de emisión, y el
    # `l10n_ec` oficial los deja disponibles en diarios de cualquier tipo.
    journal_id = fields.Many2one(
        "account.journal",
        string="Diario de emisión",
        check_company=True,
        default=lambda self: self._default_journal_id(),
        domain="[('l10n_ec_entity', '!=', False), ('l10n_ec_emission', '!=', False)]",
        help="Diario del que se toman el establecimiento y el punto de emisión "
             "(001-001-...) que van en la clave de acceso y en el comprobante.",
    )

    # Tax Lines
    tax_ids = fields.One2many(
        "l10n_ec.retention.line", "retention_id", string="Withholding Lines"
    )

    # Ciclo de vida del documento, separado del estado ante el SRI.
    #
    # Antes no existía: `action_post` reescribía `l10n_ec_sri_status` a 'draft', y el
    # botón "Send to SRI" estaba oculto precisamente en 'draft'. Sólo aparecía tras un
    # rechazo, así que una retención recién creada NO SE PODÍA ENVIAR desde la interfaz.
    state = fields.Selection(
        [("draft", "Borrador"), ("posted", "Confirmada"), ("cancel", "Anulada")],
        string="Estado",
        default="draft",
        required=True,
        copy=False,
        tracking=True,
    )

    # SRI Fields
    l10n_ec_sri_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent to SRI"),
            ("authorized", "Authorized"),
            ("rejected", "Rejected"),
        ],
        string="SRI Status",
        default="draft",
        copy=False,
    )
    l10n_ec_sri_access_key = fields.Char(string="Access Key", size=49, copy=False)
    l10n_ec_authorization_date = fields.Datetime(
        string="Authorization Date", copy=False
    )
    l10n_ec_sri_response = fields.Text(string="SRI Response", copy=False)
    l10n_ec_xml_data = fields.Binary(
        string="XML File", attachment=True, copy=False,
        help="Comprobante firmado tal como se transmitió al SRI.",
    )
    # Igual que en la factura: sólo se reintenta lo que falló por transporte. Un
    # rechazo de contenido exige corregir y reenviar con la misma clave (§5.10).
    l10n_ec_sri_retryable = fields.Boolean(string="Reintentable", copy=False)
    l10n_ec_sri_retry_count = fields.Integer(string="Reintentos", default=0, copy=False)

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    @api.constrains("date_issue", "invoice_id")
    def _check_retention_date(self):
        """La retención no puede ser anterior a la factura que la sustenta.

        Portado desde el modelo `account.retention` que este sustituye. La regla de
        los 5 días hábiles ya no aplica desde 2026; sólo queda la coherencia de
        fechas, que el SRI valida contra <fechaEmisionDocSustento>.
        """
        for record in self:
            if record.invoice_id and record.date_issue:
                invoice_date = record.invoice_id.invoice_date
                if invoice_date and record.date_issue < invoice_date:
                    raise ValidationError(_(
                        "La fecha de la retención (%(retention)s) no puede ser "
                        "anterior a la de la factura (%(invoice)s).",
                        retention=record.date_issue,
                        invoice=invoice_date,
                    ))

    @api.model
    def _default_journal_id(self):
        """Primer diario de la compañía que tenga establecimiento y punto de emisión."""
        return self.env["account.journal"].search([
            ("company_id", "in", self.env.companies.ids),
            ("l10n_ec_entity", "!=", False),
            ("l10n_ec_emission", "!=", False),
        ], limit=1)

    @api.model
    def _l10n_ec_format_number(self, journal, sequential):
        """`001-001-000000001` a partir del diario y el secuencial.

        El formato no es cosmético: el SRI lo exige en el RIDE y sus tres partes son
        las mismas que viajan en la clave de acceso, así que tienen que salir de una
        sola fuente. Falla explícitamente en vez de inventar un `001` por defecto,
        que es lo que hacía que se emitieran comprobantes con un punto de emisión
        que no existe en el RUC del emisor.
        """
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
        return "{}-{}-{}".format(
            establishment.zfill(3), emission_point.zfill(3), str(sequential).zfill(9)
        )

    def _l10n_ec_assign_number(self):
        """Asigna `001-001-000000001` al confirmar, no al crear.

        Antes se numeraba en `create()`. Tres razones para moverlo aquí:

        * un borrador que se borra quemaba un secuencial de la serie del SRI;
        * `journal_id` es editable en borrador, así que el número quedaba obsoleto
          en cuanto el usuario cambiaba de diario;
        * al crear todavía puede no haber diario elegido.

        El secuencial es por diario: dos puntos de emisión no pueden compartir
        contador, porque el SRI numera por (establecimiento, punto de emisión, tipo
        de comprobante).
        """
        self.ensure_one()
        if self.name and self.name != _("New"):
            return
        if not self.journal_id:
            raise UserError(_(
                "La retención no tiene diario de emisión. Elija uno con "
                "establecimiento y punto de emisión SRI configurados."
            ))
        sequential = self.journal_id._l10n_ec_next_retention_sequential()
        self.name = self._l10n_ec_format_number(self.journal_id, sequential)

    @api.constrains("journal_id", "state")
    def _check_journal_locked_after_emission(self):
        """El diario no se toca una vez que hay clave de acceso.

        La clave lleva dentro el establecimiento y el punto de emisión: cambiarlos
        después dejaría el cuerpo del comprobante y su clave describiendo dos
        emisores distintos, que es el error 58 del SRI.
        """
        for record in self:
            if record.l10n_ec_sri_access_key and not record.journal_id:
                raise ValidationError(_(
                    "La retención %s ya tiene clave de acceso: no puede quedarse sin "
                    "diario de emisión.", record.display_name,
                ))

    def action_post(self):
        """Confirma la retención y la deja lista para transmitir."""
        for retention in self:
            if not retention.tax_ids:
                raise UserError(_(
                    "La retención %s no tiene líneas: no hay nada que declarar al SRI.",
                    retention.display_name,
                ))
            retention._l10n_ec_assign_number()
            retention.state = "posted"

    def action_draft(self):
        """Devuelve a borrador una retención que el SRI rechazó.

        No se permite sobre una ya autorizada: §5.10 obliga a corregir y reenviar con
        la MISMA clave y secuencial, no a rehacer el documento.
        """
        for retention in self:
            if retention.l10n_ec_sri_status == "authorized":
                raise UserError(_(
                    "La retención %s ya está autorizada por el SRI y no puede volver "
                    "a borrador.", retention.display_name,
                ))
            retention.state = "draft"

    def action_send_sri(self):
        """
        Orchestrator for Retention: XML Gen -> Sign -> Send
        """
        for ret in self:
            if ret.l10n_ec_sri_status in ["authorized", "sent"]:
                continue
            if ret.state != "posted":
                raise UserError(_(
                    "La retención %s debe confirmarse antes de enviarla al SRI.",
                    ret.display_name,
                ))

            # 1. Generate Access Key & XML
            # render_xml returns bytes
            xml_content = self.env["l10n_ec.sri.retention.xml"].render_xml(ret)
            if not isinstance(xml_content, bytes):
                xml_content = xml_content.encode("utf-8")

            # 2. Sign XML (Reuse Signer)
            certificate = ret.company_id.l10n_ec_certificate_id
            if not certificate:
                raise UserError(_("No active Electronic Signature found."))

            signed_xml = certificate.sign_xml(xml_content)
            ret.l10n_ec_xml_data = base64.b64encode(signed_xml)

            # 3. Send to SRI
            response = self.env["l10n_ec.sri.service"].send_document(
                ret.company_id, signed_xml
            )
            messages = response.get("messages", [])

            if response.get("status") == "RECIBIDA":
                ret.l10n_ec_sri_status = "sent"
                ret.l10n_ec_sri_response = False
                ret.l10n_ec_sri_retryable = False
                continue

            # Igual que en la factura: los identificadores 43 ("clave de acceso
            # registrada") y 70 ("en procesamiento") NO son rechazos — el SRI ya
            # tiene el comprobante y la Ficha (§11) prohíbe reenviarlo.
            already_at_sri = {"43", "70"} & set(response.get("identifiers", []))
            if already_at_sri:
                ret.l10n_ec_sri_status = "sent"
                ret.l10n_ec_sri_retryable = False
                ret.l10n_ec_sri_response = _(
                    "El SRI ya tiene este comprobante (código %s). No se reenvía: se "
                    "consultará su autorización.", ", ".join(sorted(already_at_sri))
                )
                continue

            ret.l10n_ec_sri_status = "rejected"
            ret.l10n_ec_sri_response = "\n".join(messages) or response.get("status")
            ret.l10n_ec_sri_retryable = (
                response.get("status") == "ERROR" and not response.get("identifiers")
            )

    def action_check_sri(self):
        """
        Check Status for Retention
        """
        for ret in self:
            if not ret.l10n_ec_sri_access_key:
                raise UserError(_("No Access Key."))

            response = self.env["l10n_ec.sri.service"].check_authorization(
                ret.company_id, ret.l10n_ec_sri_access_key
            )

            if response.get("status") == "AUTORIZADO":
                ret.l10n_ec_sri_status = "authorized"
                ret.l10n_ec_sri_response = False
                if response.get("date"):
                    from datetime import timezone as _tz
                    d = response["date"]
                    if hasattr(d, 'tzinfo') and d.tzinfo is not None:
                        d = d.astimezone(_tz.utc).replace(tzinfo=None)
                    ret.l10n_ec_authorization_date = d
                # El comprobante autorizado que devuelve el SRI es el que hay que
                # conservar; sustituye al firmado que se guardó al transmitir.
                if response.get("xml"):
                    ret.l10n_ec_xml_data = base64.b64encode(
                        response["xml"].encode("utf-8")
                    )
            elif response.get("status") in ("NO AUTORIZADO", "RECHAZADO"):
                ret.l10n_ec_sri_status = "rejected"
                ret.l10n_ec_sri_response = "\n".join(response.get("messages", []))
            else:
                # EN PROCESO / PPR / PENDING: el SRI puede tardar hasta 24 h (§7.5).
                ret.l10n_ec_sri_response = _(
                    "Estado en el SRI: %s. %s",
                    response.get("status") or _("sin respuesta"),
                    " ".join(response.get("messages", [])),
                )

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------

    @api.model
    def _l10n_ec_cron_process_pending(self, limit=200, max_age_days=30, max_retries=5):
        """Mismo ciclo asíncrono que la factura, para las retenciones.

        Ver `account.move._l10n_ec_cron_process_pending`: consulta las enviadas y
        reintenta sólo las que fallaron por transporte.
        """
        cutoff = fields.Date.subtract(fields.Date.today(), days=max_age_days)

        pending = self.search([
            ("l10n_ec_sri_status", "=", "sent"),
            ("l10n_ec_sri_access_key", "!=", False),
            ("date_issue", ">=", cutoff),
        ], limit=limit)
        l10n_ec_run_isolated(pending, "action_check_sri")

        retryable = self.search([
            ("l10n_ec_sri_status", "=", "rejected"),
            ("l10n_ec_sri_retryable", "=", True),
            ("l10n_ec_sri_retry_count", "<", max_retries),
            ("state", "=", "posted"),
            ("date_issue", ">=", cutoff),
        ], limit=limit)
        for retention in retryable:
            retention.l10n_ec_sri_retry_count += 1
        l10n_ec_run_isolated(retryable, "action_send_sri")

        return len(pending) + len(retryable)


class L10nEcRetentionLine(models.Model):
    _name = "l10n_ec.retention.line"
    _description = "Withholding Tax Line"

    retention_id = fields.Many2one(
        "l10n_ec.retention", string="Retention", ondelete="cascade"
    )
    tax_id = fields.Many2one("account.tax", string="Tax", required=True)
    base_amount = fields.Monetary(string="Base Amount", required=True)
    amount = fields.Monetary(string="Withheld Amount", required=True)
    currency_id = fields.Many2one(
        "res.currency", related="retention_id.company_id.currency_id"
    )

    @api.onchange("tax_id", "base_amount")
    def _compute_amount(self):
        for line in self:
            # Odoo 19 eliminó account.tax.compute_all(): esto lanzaba AttributeError
            # y ninguna retención podía calcularse.
            #
            # Una retención ecuatoriana es siempre un porcentaje plano sobre la base
            # (tablas 19 renta / 21 IVA / 23 ISD del SRI), sin impuestos encadenados
            # ni precio incluido, así que la aritmética directa es exacta y evita
            # depender del pipeline nuevo (_prepare_base_line_for_taxes_computation →
            # _add_tax_details_in_base_line) para un caso de un solo impuesto.
            tax = line.tax_id
            if not tax or not line.base_amount:
                line.amount = 0.0
            elif tax.amount_type == "percent":
                line.amount = abs(line.base_amount * tax.amount / 100.0)
            elif tax.amount_type == "fixed":
                line.amount = abs(tax.amount)
            else:
                line.amount = 0.0
