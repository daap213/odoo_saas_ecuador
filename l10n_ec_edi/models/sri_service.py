# -*- coding: utf-8 -*-
"""Cliente de los web services del SRI (esquema offline, Ficha Técnica 2.34).

Dos correcciones de fondo respecto a la versión anterior:

1. El endpoint se resuelve **por ambiente y por compañía**. Antes se leía siempre
   `self.env.company.l10n_ec_sri_reception_url`, cuyo valor por defecto apunta a
   `celcer` (pruebas) — de modo que pasar la compañía a producción no cambiaba nada
   y en multiempresa se podía enviar al ambiente de otra compañía.

2. Se devuelven los **identificadores** de los mensajes. Sin ellos era imposible
   distinguir un rechazo real de los códigos 43 ("clave de acceso registrada") y 70
   ("clave de acceso en procesamiento"), que significan que el comprobante YA está
   en el SRI y que la Ficha prohíbe reenviar.
"""
import logging

from odoo import _, models
from odoo.exceptions import UserError

try:
    from zeep import Client, Settings
    from zeep.transports import Transport
    from zeep.exceptions import Fault
except ImportError:
    logging.getLogger(__name__).warning("Zeep library not installed")

_logger = logging.getLogger(__name__)

# Ficha Técnica 2.34, §7.2. Estas son las URL oficiales; los parámetros del sistema
# permiten sobreescribirlas sin tocar código.
DEFAULT_URLS = {
    ("reception", "test"): "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    ("reception", "production"): "https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl",
    ("authorization", "test"): "https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
    ("authorization", "production"): "https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl",
}

# §11 nota 2: ante estos códigos NO se debe reenviar ni regenerar la clave.
ALREADY_RECEIVED_CODES = {"43", "70"}

# La Ficha fija 1 MB para el envio individual y advierte que el limite practico
# del servicio de recepcion es menor. Se comprueba antes de transmitir porque el
# SRI responde a un comprobante demasiado grande con un rechazo generico que no
# menciona el tamano, y la causa real se vuelve muy dificil de localizar.
MAX_DOCUMENT_BYTES = 320 * 1024


class SriService(models.AbstractModel):
    _name = "l10n_ec.sri.service"
    _description = "SRI SOAP Web Service Client"

    def _get_service_url(self, company, service):
        """URL del servicio para el ambiente de ESTA compañía.

        Precedencia: campo de la compañía (si el usuario lo fijó) → parámetro del
        sistema por ambiente → constante oficial.
        """
        environment = company.l10n_ec_sri_environment or "test"
        override = company[f"l10n_ec_sri_{service}_url"]
        if override:
            return override

        suffix = "prod" if environment == "production" else "test"
        param = self.env["ir.config_parameter"].sudo().get_param(
            f"l10n_ec.sri_{service}_url_{suffix}"
        )
        return param or DEFAULT_URLS[(service, environment)]

    def _get_client(self, url):
        try:
            settings = Settings(strict=False, xml_huge_tree=True)
            transport = Transport(timeout=30, operation_timeout=30)
            return Client(wsdl=url, settings=settings, transport=transport)
        except Exception as exc:
            raise UserError(
                _("No se pudo conectar con el WSDL del SRI en %s.\n\n%s", url, exc)
            )

    def _parse_messages(self, container):
        """Extrae (textos, identificadores) de un bloque <mensajes>."""
        texts, identifiers = [], []
        for message in getattr(container, "mensaje", []) or []:
            identifier = str(getattr(message, "identificador", "") or "")
            if identifier:
                identifiers.append(identifier)
            texts.append(
                "{ident} {tipo}: {msg} {extra}".format(
                    ident=identifier,
                    tipo=getattr(message, "tipo", "") or "",
                    msg=getattr(message, "mensaje", "") or "",
                    extra=getattr(message, "informacionAdicional", "") or "",
                ).strip()
            )
        return texts, identifiers

    def _check_document_size(self, signed_xml_bytes):
        """Respuesta de rechazo si el comprobante excede el limite, o None.

        Devuelve la misma forma que `send_document` —status, messages,
        identifiers— para que el llamador no tenga que distinguir este caso del
        rechazo del SRI: es un rechazo, sólo que detectado antes de gastar la
        llamada. El identificador queda vacío porque no es un código del SRI.
        """
        size = len(signed_xml_bytes or b"")
        if size <= MAX_DOCUMENT_BYTES:
            return None
        return {
            "status": "DEVUELTA",
            "messages": [_(
                "El comprobante firmado ocupa %(size).0f kb y el envio individual "
                "admite hasta %(limit).0f kb. Divida el documento en varios "
                "comprobantes o reduzca el numero de lineas.",
                size=size / 1024.0, limit=MAX_DOCUMENT_BYTES / 1024.0,
            )],
            "identifiers": [],
        }

    def send_document(self, company, signed_xml_bytes):
        """Envía el comprobante firmado al servicio de recepción.

        Devuelve {status, messages, identifiers}. `status` es RECIBIDA o DEVUELTA
        según la Ficha; los identificadores permiten al llamador reconocer los
        códigos 43 y 70.
        """
        oversize = self._check_document_size(signed_xml_bytes)
        if oversize:
            return oversize

        url = self._get_service_url(company, "reception")
        client = self._get_client(url)

        try:
            response = client.service.validarComprobante(xml=signed_xml_bytes)
            result = {
                "status": getattr(response, "estado", None),
                "messages": [],
                "identifiers": [],
            }

            comprobantes = getattr(response, "comprobantes", None)
            for comprobante in getattr(comprobantes, "comprobante", []) or []:
                texts, identifiers = self._parse_messages(
                    getattr(comprobante, "mensajes", None)
                )
                result["messages"].extend(texts)
                result["identifiers"].extend(identifiers)
            return result

        except Fault as exc:
            return {"status": "ERROR", "messages": [f"SOAP Fault: {exc}"], "identifiers": []}
        except Exception as exc:
            _logger.exception("Error enviando comprobante al SRI (%s)", url)
            return {"status": "ERROR", "messages": [f"Fallo de conexión: {exc}"], "identifiers": []}

    def check_authorization(self, company, access_key):
        """Consulta la autorización por clave de acceso.

        Devuelve {status, date, xml, authorization_number, messages, identifiers}.
        `status` puede ser AUTORIZADO, NO AUTORIZADO, RECHAZADO, EN PROCESO o
        PENDING (esta última cuando el SRI todavía no tiene ninguna autorización).
        """
        url = self._get_service_url(company, "authorization")
        client = self._get_client(url)

        try:
            response = client.service.autorizacionComprobante(
                claveAccesoComprobante=access_key
            )

            autorizaciones = getattr(response, "autorizaciones", None)
            items = getattr(autorizaciones, "autorizacion", None) or []
            if not items:
                return {
                    "status": "PENDING",
                    "messages": [_("El SRI aún no tiene una autorización para esta clave.")],
                    "identifiers": [],
                }

            # §5.11: si fue rechazado varias veces el WS devuelve el último estado.
            auth = items[-1]
            texts, identifiers = self._parse_messages(getattr(auth, "mensajes", None))
            return {
                "status": getattr(auth, "estado", None),
                "date": getattr(auth, "fechaAutorizacion", None),
                "xml": getattr(auth, "comprobante", None),
                "authorization_number": getattr(auth, "numeroAutorizacion", None),
                "messages": texts,
                "identifiers": identifiers,
            }

        except Fault as exc:
            return {"status": "ERROR", "messages": [f"SOAP Fault: {exc}"], "identifiers": []}
        except Exception as exc:
            _logger.exception("Error consultando autorización en el SRI (%s)", url)
            return {"status": "ERROR", "messages": [f"Fallo de conexión: {exc}"], "identifiers": []}
