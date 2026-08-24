# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import UserError
import base64


class AccountMove(models.Model):
    """
    Extends account.move with SRI integration logic.
    Field definitions inherited from l10n_ec_edi.

    Note: 2026 Consumidor Final validations are handled by l10n_ec_edi module.
    """

    _inherit = "account.move"

    # Additional fields not in l10n_ec_edi
    l10n_ec_authorization_date = fields.Datetime(
        string="Authorization Date", copy=False
    )
    l10n_ec_sri_error = fields.Text(string="SRI Error Message", copy=False)

    def action_send_sri(self):
        """Genera clave, XML, firma y transmite al SRI."""
        for move in self:
            if move.l10n_ec_sri_status in ["authorized", "sent"]:
                continue

            if move.state != "posted":
                raise UserError(_(
                    "El comprobante %s debe estar publicado antes de enviarlo al SRI.",
                    move.display_name,
                ))

            # 1. Clave de acceso. Se genera UNA sola vez y se conserva: la Ficha
            #    (§5.10) exige que un reenvío use la misma clave y el mismo
            #    secuencial. Regenerarla duplicaría el comprobante en el SRI.
            if not move.l10n_ec_sri_access_key:
                move.l10n_ec_sri_access_key = self.env[
                    "l10n_ec.sri.xml"
                ].generate_access_key(move)

            # 2. XML (ya incluye el prólogo UTF-8)
            xml_content = self.env["l10n_ec.sri.xml"].render_xml(move)
            if not isinstance(xml_content, bytes):
                xml_content = xml_content.encode("utf-8")

            # 3. Firma
            signed_xml = self._sign_xml(xml_content)
            move.l10n_ec_xml_data = base64.b64encode(signed_xml)

            # 4. Envío, con la compañía del documento (no env.company: en
            #    multiempresa eso podía enviar al ambiente de otra).
            response = self.env["l10n_ec.sri.service"].send_document(
                move.company_id, signed_xml
            )
            move._l10n_ec_apply_reception_response(response)

    def _l10n_ec_apply_reception_response(self, response):
        """Traduce la respuesta de recepción a un estado del comprobante.

        Matiz que antes faltaba y que causaba duplicados: un DEVUELTA con el
        identificador 43 ("clave de acceso registrada") o 70 ("clave de acceso en
        procesamiento") NO es un rechazo — significa que el comprobante YA está en
        el SRI. La Ficha (§11 nota 2) prohíbe expresamente reenviarlo o regenerarlo
        con otra clave hasta tener respuesta, hasta 24 horas.
        """
        self.ensure_one()
        status = response.get("status")
        messages = response.get("messages", [])

        if status == "RECIBIDA":
            self.l10n_ec_sri_status = "sent"
            self.l10n_ec_sri_error = False
            return

        already_at_sri = {"43", "70"} & set(response.get("identifiers", []))
        if already_at_sri:
            self.l10n_ec_sri_status = "sent"
            self.l10n_ec_sri_error = _(
                "El SRI ya tiene este comprobante (código %s). No se reenvía: se "
                "consultará su autorización.", ", ".join(sorted(already_at_sri))
            )
            return

        self.l10n_ec_sri_status = "rejected"
        self.l10n_ec_sri_error = "\n".join(messages) or status

    def action_check_sri(self):
        """
        Ping Check Status service (Real Implementation)
        """
        for move in self:
            if not move.l10n_ec_sri_access_key:
                raise UserError(_("No Access Key generated yet."))

            response = self.env["l10n_ec.sri.service"].check_authorization(
                move.company_id, move.l10n_ec_sri_access_key
            )
            status = response.get("status")

            if status == "AUTORIZADO":
                move.l10n_ec_sri_status = "authorized"
                move.l10n_ec_sri_error = False
                if response.get("date"):
                    from datetime import timezone as _tz
                    d = response["date"]
                    if hasattr(d, "tzinfo") and d.tzinfo is not None:
                        d = d.astimezone(_tz.utc).replace(tzinfo=None)
                    move.l10n_ec_authorization_date = d

                # La clave del servicio es "xml"; antes se leía "authorized_xml", que
                # no existe, así que el comprobante autorizado no se guardaba nunca.
                if response.get("xml"):
                    move.l10n_ec_xml_data = base64.b64encode(
                        response["xml"].encode("utf-8")
                    )
            elif status in ("NO AUTORIZADO", "RECHAZADO"):
                move.l10n_ec_sri_status = "rejected"
                move.l10n_ec_sri_error = "\n".join(response.get("messages", []))
            else:
                # EN PROCESO / PPR / PENDING / ERROR: el SRI puede tardar hasta 24 h
                # (§7.5). Antes se ignoraban en silencio y el usuario no sabía nada.
                move.l10n_ec_sri_error = _(
                    "Estado en el SRI: %s. %s",
                    status or _("sin respuesta"),
                    " ".join(response.get("messages", [])),
                )

    def _sign_xml(self, xml_content):
        """
        Internal helper to call the signer lib.
        """
        self.ensure_one()
        certificate = self.company_id.l10n_ec_certificate_id
        if not certificate:
            raise UserError(_("No active Electronic Signature found for this company."))

        return certificate.sign_xml(xml_content)
