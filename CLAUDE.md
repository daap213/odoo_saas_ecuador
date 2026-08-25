# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este repositorio

Colección de ~19 addons de Odoo (`l10n_ec*`) que implementan la localización ecuatoriana: facturación electrónica SRI, retenciones, nómina IESS, aduanas y reportes tributarios. **No es un módulo único** — es un repo de addons que se monta completo en el `addons_path`.

Rama de trabajo: `19.0`. Todos los `__manifest__.py` declaran `"version": "19.0.1.0.0"`, pero **el código y la documentación fueron escritos para Odoo 18** (README, `docs/INSTALACION.md` y `DEVELOPER_SETUP_DOCKER.md` siguen diciendo "Odoo 18"). La migración a 19 está incompleta — ver "Deuda técnica conocida".

Idioma: los mensajes al usuario (`UserError`, `ValidationError`, labels) van en **español**; docstrings y comentarios técnicos están mezclados ES/EN. Mantener la convención del archivo que se edita.

## Comandos

### Laboratorio local (la vía rápida)

`devops/lab.sh` levanta Odoo 19 + PostgreSQL sobre `../odoo_template` **montando este
directorio de trabajo** — el checkout real o un worktree —, así que un cambio se ve con
un `update`, sin commitear ni pushear. No modifica ningún fichero del template: el
montaje va en `devops/docker-compose.lab.yaml`, que se añade como tercer fichero de
`COMPOSE_FILE`.

```bash
./devops/lab.sh up                       # primer arranque ~4 min (reinstala apt+pip)
./devops/lab.sh init                     # crea la BD `lab`, deja admin/admin
./devops/lab.sh install                  # l10n_ec_base,l10n_ec_edi,l10n_ec_sri
./devops/lab.sh install l10n_ec_full
./devops/lab.sh update l10n_ec_sri
./devops/lab.sh test l10n_ec_sri         # suite del módulo
./devops/lab.sh shell | logs | ps | down
```

Odoo queda en <http://localhost:18069>. Dos trampas que el script ya resuelve y que
conviene conocer si se invoca Odoo a mano:

* `--test-enable` levanta el servidor HTTP **aunque se pase `--no-http`**, así que
  choca con el Odoo que ya sirve en 8069/8072: hay que darle puertos propios.
* En Git Bash sobre Windows, `--test-tags /l10n_ec_sri` se traduce a
  `C:/Program Files/Git/l10n_ec_sri` antes de llegar a Odoo, que lo rechaza con
  *"Invalid tag"* y ejecuta **0 tests sin fallar** — silencioso y muy fácil de tomar
  por "todo verde". Se evita con `MSYS_NO_PATHCONV=1`.

### Contra una instalación propia

No hay CI, linter ni `pyproject.toml` en el repo.

```bash
# Instalar / actualizar módulos (el orden importa: base → edi → sri → resto)
odoo-bin -c odoo.conf -d <db> -i l10n_ec_base,l10n_ec_edi,l10n_ec_sri --stop-after-init
odoo-bin -c odoo.conf -d <db> -u l10n_ec_sri --stop-after-init

# Smoke test obligatorio antes de commitear: si esto falla, el código está roto
odoo-bin -c odoo.conf -d <db> -i l10n_ec_base,l10n_ec_edi,l10n_ec_withholding --stop-after-init --log-level=warn

# Tests de un módulo
odoo-bin -c odoo.conf -d <db> -u l10n_ec_base --test-enable --test-tags /l10n_ec_base --stop-after-init

# Un solo test
odoo-bin -c odoo.conf -d <db> -u l10n_ec_base --test-enable \
  --test-tags /l10n_ec_base:TestEcIdentity.test_ruc_valido --stop-after-init

# Por tag de negocio (los tests usan tags: l10n_ec, sri, regulatory, withholding, payroll, customs, calendar)
odoo-bin -c odoo.conf -d <db> --test-enable --test-tags regulatory --stop-after-init
```

Despliegue al servidor (Ubuntu, Odoo 19 en `/opt/odoo19`, systemd `odoo19`, addons en `third-party-addons/odoo_saas_ecuador`):

```bash
sudo DB_NAME=<db> MODULES=l10n_ec_sri bash scripts/deploy_saas.sh
```

Hace `git reset --hard origin/19.0`, detecta si cada módulo está `installed` para elegir `-i` vs `-u`, y reinicia el servicio.

Dependencias Python externas: `zeep`, `cryptography`, `lxml`, `requests` (`requirements.txt`, declaradas en `external_dependencies` de `l10n_ec_edi` y `l10n_ec_sri`).

### Dónde viven los tests

- `l10n_ec_base/tests/`, `l10n_ec_sri/tests/` — descubiertos por Odoo.
- `tests/` en la raíz — **no lo descubre Odoo** (no es un módulo). Además `tests/unit/__init__.py` sólo importa 3 de los 7 archivos que existen. Al agregar tests nuevos, ponerlos dentro del módulo correspondiente.
- `l10n_ec_sri/tests/test_sri_signer.py` y `test_xml_generator.py` son `unittest.TestCase` puros (corren fuera del ORM). El de la firma ya **no exige** un `.p12` en disco: `tests/certificate_fixture.py` genera uno autofirmado RSA-2048 en memoria. Si existe `tests/certificates/test_certificate.p12` se usa ese; ese fichero no está ni debe estar en el repo (`.gitignore` excluye `*.p12`: lleva una clave privada). Un autofirmado sirve para ejercitar el camino criptográfico, **no para emitir**: el SRI sólo acepta certificados de una entidad acreditada.
- `l10n_ec_guia_remision/tests/` cubre la guía de remisión (06), que antes no tenía ningún test — y por eso convivían en ella cuatro fallos que la hacían inemitible.

## Arquitectura

### Capas de módulos

```
l10n_ec_base      → plan de cuentas (account.chart.template), validación RUC/cédula,
                    catálogos SRI, l10n_ec.config (parámetros por año), calendario tributario
   ↓
l10n_ec_edi       → clave de acceso, firma XAdES-BES, cliente SOAP, modelo de certificado,
                    campos SRI en account.move, plantilla QWeb de factura
   ↓
l10n_ec_sri       → segunda implementación de generación XML + orquestación, retenciones
   ↓
l10n_ec_withholding / _stock / _pos / _reports / _customs / _rimpe / _ice / _income_tax
l10n_ec_hr_payroll → _vacation / _sut / _loans / _bank_transfer / _portal
   ↓
l10n_ec           → meta-módulo "instala todo con un clic": wizard de setup,
                    plantillas de negocio, post_init_hook de configuración país/moneda/idioma
```

`l10n_ec` es el paquete instalable de cara al usuario (`"application": True`). Depende de casi todo Odoo Community (`sale_management`, `purchase`, `stock`, `point_of_sale`, `pos_restaurant`, `mrp`, `fleet`, `maintenance`, `crm`, `project`, `hr*`) además de todos los `l10n_ec_*`. Instalarlo arrastra medio ERP.

### Flujo de facturación electrónica

1. **Clave de acceso (49 dígitos)** — `fecha(8) + tipoDoc(2) + RUC(13) + ambiente(1) + estab(3) + ptoEmi(3) + secuencial(9) + códigoNumérico(8) + tipoEmisión(1) + dígitoVerificador(1)`, con Módulo 11 (pesos 2..7).
2. **Generación XML** — QWeb, plantillas en `l10n_ec_edi/data/edi_templates.xml` (`l10n_ec_edi.l10n_ec_edi_factura`) y `l10n_ec_sri/views/account_move_xml_template.xml` (`l10n_ec_sri.xml_invoice`).
3. **Firma** — `l10n_ec.sri.signer` (AbstractModel, `l10n_ec_edi/models/sri_signer.py`). XAdES-BES v1.3.2 *enveloped*, **RSA-SHA1 + SHA-1 + C14N inclusiva** — que es lo que exige el SRI, aunque el README diga "SHA-256". Construye el XML de la firma como strings concatenados (no con lxml) porque la canonicalización debe coincidir byte a byte con la referencia Java del SRI. **No "modernizar" a SHA-256 ni reescribir con lxml sin validar contra el SRI de pruebas.** `SignedInfo` referencia tres elementos: `#comprobante`, `#Certificate1`, `#SignedProperties`. `SigningTime` se calcula como UTC-5 fijo.
4. **Transmisión** — `l10n_ec.sri.service` (AbstractModel, zeep). Dos servicios SOAP: `validarComprobante` (recepción) y `autorizacionComprobante` con parámetro `claveAccesoComprobante` (autorización). Estados: `RECIBIDA`/`DEVUELTA` → `AUTORIZADO`/`NO AUTORIZADO`/`EN PROCESO`.
5. **Certificado** — modelo `l10n_ec.certificate` (`.p12`, password con `groups="base.group_system"`), estados draft/active/expired/invalid, validación con `cryptography.pkcs12`. `res.company.l10n_ec_certificate_id` apunta al activo.

Estados SRI en `account.move.l10n_ec_sri_status`: `draft → signed → sent → authorized | rejected`.

### Dos implementaciones paralelas del mismo flujo

Esto es lo primero que hay que entender antes de tocar código:

| | `l10n_ec_edi` | `l10n_ec_sri` |
|---|---|---|
| Clave de acceso | `models/access_key.py` (clase Python pura, `AccessKey.generate`) | `l10n_ec.sri.xml.generate_access_key` (AbstractModel) |
| XML | `account.edi.format._export_l10n_ec_edi` + QWeb `l10n_ec_edi_factura` | `l10n_ec.sri.xml.render_xml` + QWeb `xml_invoice` |
| Cálculo de impuestos | `_compute_tax_aggregates` (infiere código SRI del *nombre* del impuesto) | `_compute_sri_taxes` (infiere de `tax.amount` y `tax_group_id`) |
| Orquestación | `account.move.action_send_sri` (en `l10n_ec_edi`) | `account.move.action_send_sri` (en `l10n_ec_sri`, **sobrescribe** al anterior) |

Ambos módulos hacen `_inherit = "account.move"` y definen `action_send_sri`. Como `l10n_ec_sri` depende de `l10n_ec_edi`, **gana el de `l10n_ec_sri`**. Y la ruta de `l10n_ec_edi` está muerta **por completo**: su `_post_invoice_edi` sobrescribe un método que Odoo 19 ya no tiene, y su plantilla QWeb fue sacada del manifest. Igual con `res.company.l10n_ec_sri_reception_url`, definido en los dos.

Antes de agregar funcionalidad SRI: decidir en cuál de las dos rutas se consolida (lo sano es una sola) en vez de agregar una tercera.

### Cómo se añade un comprobante nuevo

`l10n_ec.sri.xml.render_xml` **despacha por `codDoc`**. La tabla de despacho es un
método, `_get_document_renderers()`, y no una constante:

```python
{codDoc: (xmlid_de_la_plantilla, nombre_del_metodo_de_valores)}
```

De ahí se derivan también los códigos que `_check_document_type_supported` deja pasar,
así que "lo que se puede emitir" y "lo que sabe renderizar" no pueden desincronizarse.

Para añadir uno: escribir la plantilla QWeb, escribir su `_get_*_values`, y registrar
la entrada. Si el comprobante vive en otro módulo —la guía de remisión (06) está en
`l10n_ec_guia_remision`, que depende de `stock`— se registra con un `super()` sobre
`_get_document_renderers()`. **La dirección de la dependencia es hacia `l10n_ec_sri`,
nunca al revés**: ese módulo no debe arrastrar Inventario a una instalación contable.

Un modelo emisor que no sea `account.move` (no tiene diario ni tipo de documento
LATAM) aporta sus componentes implementando `_l10n_ec_sri_components()` y
`_l10n_ec_sri_emission_date()`. `_get_document_components` y `generate_access_key` los
delegan si existen. Es lo que permite que la guía use la MISMA clave de acceso y el
mismo módulo 11 que la factura.

**No copiar `_get_invoice_values` para un comprobante nuevo.** La factura emite
`<propina>` y `<totalDescuento>`, que no existen en la nota de crédito ni en la de
débito; heredar su diccionario "quitando lo que sobra" acaba colando un tag de más y
el SRI responde error 35. Y el detalle no es intercambiable: factura y liquidación
usan `codigoPrincipal`/`codigoAuxiliar`; nota de crédito y guía usan
`codigoInterno`/`codigoAdicional`.

### Todo configurable, nada hardcodeado

Principio explícito del proyecto. Los valores regulatorios se leen en runtime, nunca se escriben en el código:

- **`ir.config_parameter`** — sembrados en `l10n_ec_base/data/l10n_ec_sri_config.xml`: `l10n_ec.consumidor_final_ruc`, `l10n_ec.consumidor_final_limit`, `l10n_ec.annulment_day_limit`, `l10n_ec.iva_rate`, `l10n_ec.sbu`, `l10n_ec.auto_send_sri`, URLs de recepción/autorización test y prod, códigos de tipo de documento, mapas de vencimientos por 9º dígito del RUC. Los getters (`_get_cf_ruc`, `_get_cf_limit`, `_get_annulment_day` en `l10n_ec_edi/models/account_move.py`) **lanzan `ValidationError` si el parámetro no existe** — no tienen default. Si se agrega un parámetro nuevo hay que sembrarlo en el XML.
- **`l10n_ec.config`** — registro por año fiscal (`l10n_ec_base/models/l10n_ec_config.py`) con SBU, tasas IESS/SECAP/IECE, recargos de horas extra, IVA general y de construcción, ISD, canasta básica. API: `get_current_config(year)`, `get_sbu()`, `get_iess_rates()`, `get_iva_rate()`.
- **`l10n_ec.retention.code`** / **`l10n_ec.tax.code`** — códigos y tasas de retención IR/IVA como datos, no como constantes.
- **Catálogos SRI** como modelos en `l10n_ec_base/models/l10n_ec_catalogs.py`: `l10n_ec.payment.method`, `l10n_ec.identification.type`, `l10n_ec.tax.support`, `l10n_ec.province`, `l10n_ec.canton`, `l10n_ec.ciiu`, `l10n_ec.contributor.type`.

### Validaciones regulatorias implementadas

Viven como `@api.constrains` en `l10n_ec_edi/models/account_move.py` y `l10n_ec_base/models/res_partner.py`:

- Límite Consumidor Final (`_check_consumidor_final_limit`) y prohibición de anular facturas CF autorizadas (`button_cancel_sri`).
- Plazo de anulación: día N del mes siguiente (`_check_annulment_deadline`, `_check_cancellation_allowed`).
- RUC/cédula: Módulo 10 para cédula y RUC natural (3er dígito <6), Módulo 11 para entidad pública (=6) y sociedad privada (=9) — `res_partner._validate_ec_document`.
- Contratistas del Estado requieren certificado UAF vigente (DE 045-2025).
- Auto-envío al SRI tras `action_post()` si `l10n_ec.auto_send_sri` está en true; los errores se loguean pero **no bloquean el asiento**.

### Servicios externos

- `l10n_ec.sri.ruc.service` (`l10n_ec_base/models/l10n_ec_sri_ruc_service.py`) — consulta REST a las APIs abiertas del SRI para autocompletar razón social, dirección y régimen tributario. Se dispara en `@api.onchange("vat")` de `res.partner` con errores silenciados (no interrumpe el flujo del usuario).
- `l10n_ec.tax.calendar` — calcula vencimientos según el 9º dígito del RUC.

### Setup wizard y plantillas de negocio

`l10n_ec.company.setup.wizard` (6 pasos) configura empresa, ambiente SRI, certificado, plan de cuentas, nómina y carga una `l10n_ec.business.template` (tipo de negocio × tamaño simple/mediano/grande) que siembra productos, proveedores y categorías. El `post_init_hook` de `l10n_ec` crea un `ir.actions.todo` para abrirlo tras la instalación.

### `l10n_ec_base/mcp/`

Clases Python planas (`InvoiceManager`, `PartnerManager`, `RetentionManager`, `PayrollManager`, …) que envuelven operaciones del ORM para exponerlas vía MCP. **No están importadas desde `l10n_ec_base/__init__.py`**, así que no se cargan al instalar el módulo — son librería opcional, no parte del addon en ejecución.

## Convenciones

- Encabezado en todo `.py` nuevo: coding utf-8, `# Part of Odoo...`, `# Copyright 2026 <autor>`, `# License LGPL-3.0 or later`.
- Manifest: `"author": "..., Somatech.dev, Odoo Community Association (OCA)"`, `"license": "LGPL-3"`, `"website": "https://github.com/somatechlat/odoo_saas_ecuador"`.
- Commits: `[MODULO] Descripción corta (máx 72 chars)`.
- Estilo OCA/PEP8. Prefijo `l10n_ec_` en todos los campos añadidos a modelos core.
- Nunca commitear `.p12`, `.pfx`, `.pem`, `.key`, `.crt` — ya están en `.gitignore`.

## Deuda técnica conocida (verificar antes de construir encima)

Estos puntos están confirmados leyendo el código, no son especulación. Si el trabajo pedido toca facturación electrónica, resolverlos es probablemente parte del alcance:

1. **Colisión de nombres con los addons oficiales — y es la causa raíz de varios "faltantes".** Odoo 19 **Community** trae `addons/l10n_ec` ("Ecuadorian Accounting" v3.9, TRESCLOUD) con **`auto_install: ['account']`**: se instala solo en cuanto haya `account` y una compañía EC. `l10n_ec_edi` y `l10n_ec_reports` sí son de Enterprise (libres en Community).

   Dos addons con el mismo nombre técnico no coexisten: gana el primero del `addons_path`, en silencio. Lo que el oficial ya aporta y este repo intenta reimplementar (o leer y no encontrar):
   - `account.journal.l10n_ec_entity` / `.l10n_ec_emission` / `.l10n_ec_emission_address_id` — **exactamente los campos que `l10n_ec_sri/models/l10n_ec_sri_xml.py:47` intenta leer y fallan**.
   - `account.move._get_ec_formatted_sequence()` / `_get_starting_sequence()` / `_get_last_sequence_domain()` — numeración `001-001-000000001` sobre el motor de secuencias nativo, con bloqueo de fila y reintento ante `UniqueViolation`.
   - `account.tax.group.l10n_ec_type` (clasificación SRI: `vat15`, `zero_vat`, `ice`, `withhold_income_purchase`…) y `account.tax.l10n_ec_code_base` / `_applied` / `_ats`.
   - `l10n_latam.document.type` con los IDs `ec_dt_01`…`ec_dt_41`, `internal_type` correcto (`03` = `purchase_liquidation`, `07` = `withhold`) y `_format_document_number`. El CSV de `l10n_ec_base` usa **los mismos IDs en otro namespace → duplica** y además declara `03` y `07` como `invoice`.
   - `res_partner` con validación RUC/cédula vía `stdnum` sobre `l10n_latam_identification_type_id`.
   - `template_ec.py`: el oficial define `_get_ec_template_data`, `_get_ec_res_company`, `_get_ec_account_journal`, `_get_ec_account_account`; el repo define tres de esos mismos nombres sobre el mismo AbstractModel → el MRO se queda con uno solo, en silencio.
2. **`_sql_constraints` ya no se aplica en Odoo 19** — verificado en `odoo/orm/model_classes.py`: loguea *"Model attribute '_sql_constraints' is no longer supported"* y lo **ignora en silencio**. No rompe la instalación; simplemente las restricciones de unicidad **desaparecen de la base**. Migrar a `models.Constraint`. **13 bloques en 5 archivos**: 
   - `l10n_ec_base/models/l10n_ec_catalogs.py` (7): líneas 43, 83, 110, 173, 205, 251, 289
   - `l10n_ec_base/models/l10n_ec_config.py` (3): líneas 254, 304, 366
   - `l10n_ec_edi/models/l10n_ec_certificate.py` (1): línea 229
   - `l10n_ec_ice/models/l10n_ec_ice_category.py` (1): línea 34
   - `l10n_ec_withholding/models/l10n_ec_withholding_tax.py` (1): línea 29

   Patrón: `_sql_constraints = [("name_uniq", "unique(name)", "msg")]` → `_name_uniq = models.Constraint("UNIQUE(name)", "msg")`.
   (Nota: `references/api-highlights.md` del skill sugiere que `_sql_constraints` sigue siendo válido; `references/odoo-19-model-guide.md` y el `CLAUDE.md` del skill dicen que no. Gana la mayoría — y en la duda, `models.Constraint` funciona en ambos casos.)
3. **`account.edi.format` está muerto aquí.** El módulo `account_edi` **sí existe** en Odoo 19 (verificado), pero el modelo ya **no tiene `_post_invoice_edi` ni `_cancel_invoice_edi`** — solo `_get_move_applicability` y compañía. `l10n_ec_edi/models/account_edi_format.py` sobrescribe `_post_invoice_edi` y hace `super()._post_invoice_edi(...)` → `AttributeError`. El archivo entero es código muerto. El enganche moderno es el AbstractModel `account.move.send` (`_get_all_extra_edis`, `_call_web_service_before_invoice_pdf_render`, `_get_invoice_extra_attachments`, `_get_alerts`).
4. **`account.tax.compute_all()` y `_compute_amount()` fueron eliminados en Odoo 19.** API nueva: `_prepare_base_line_for_taxes_computation` → `_add_tax_details_in_base_lines` → `_round_tax_details_tax_amounts` → `_aggregate_base_lines_tax_details`. Impacto: `l10n_ec_ice/models/account_tax.py` sobrescribe un método inexistente → **el ICE nunca se calcula, en silencio**; `l10n_ec_sri/models/l10n_ec_retention.py:152` revienta con `AttributeError`.
5. **`hr_contract` fue eliminado en Odoo 19** (verificado: 404 en la rama 19.0, presente en 18.0). `hr.contract` → `hr.version`, dentro de `hr`, con `hr.employee._inherits = {'hr.version': 'version_id'}`. No hay formulario propio de `hr.version`: se edita en la ficha del empleado. `hr.contract.type` sí sobrevive. Esto **sí bloquea la instalación** de `l10n_ec` y `l10n_ec_hr_payroll`. (La nómina usa un modelo propio `l10n_ec.payslip`, no `hr.payslip`, para funcionar en Community.)
6. **Dígito de ambiente invertido.** Spec SRI: `1` = pruebas, `2` = producción. `l10n_ec_sri/models/l10n_ec_sri_xml.py` y `account_edi_format._get_l10n_ec_edi_values` lo hacen bien; `l10n_ec_edi/models/account_move.py:_generate_access_key` y `action_send_sri` lo hacen al revés (`"1" if production`). Si la clave de acceso y el tag `<ambiente>` no coinciden, el SRI rechaza el comprobante.
7. **~~Las URLs de producción nunca se usan~~ — RESUELTO.** `l10n_ec.sri.service._get_service_url` resuelve el endpoint **por ambiente y por compañía**, con la precedencia: campo de la compañía (override manual) → `ir.config_parameter` del ambiente → constante oficial de la Ficha §7.2. Los dos campos de la compañía nacen ya **vacíos**; llevaban un `default` a `celcer` que ganaba siempre, así que pasar a producción no cambiaba el endpoint. Hay migración (`l10n_ec_edi/migrations/19.0.1.1.0`) que limpia lo que ese default dejó escrito.
8. **~~No existe modelo de establecimiento / punto de emisión~~ — RESUELTO.** Lo aporta el `l10n_ec` oficial (`account.journal.l10n_ec_entity` / `.l10n_ec_emission`), declarado como dependencia explícita en `l10n_ec_base` y `l10n_ec_sri`. `_get_document_components` los lee del diario y **falla con `UserError` si faltan**, en vez de caer a `001`. Lo mismo vale ahora para retenciones (campo `journal_id` nuevo en `l10n_ec.retention`) y para guías (`stock.picking.type.l10n_ec_guia_journal_id`, con respaldo en la compañía). El secuencial ya no se extrae con string-slicing: hay una `ir.sequence` por diario y tipo de comprobante (`account.journal._l10n_ec_get_sri_sequence`), porque el SRI numera por (establecimiento, punto de emisión, tipo de comprobante). **`l10n_ec_pos` sigue sin emitir**: genera una clave de acceso por ticket y no la usa.
9. **~~`l10n_ec_full/hooks.py` es código muerto~~ — RESUELTO.** El `post_init_hook` de `__init__.py` delega ahora en el de `hooks.py`, así que sí se aplican idioma `es_EC`, país, moneda y el `ir.actions.todo` que abre el asistente. En la misma línea, el asistente de configuración de empresa escribía cuatro `ir.config_parameter` que **nadie leía** (`l10n_ec.sri_environment`, `…obligado_contabilidad`, `…contribuyente_especial`, `…agente_retencion`) mientras el generador del XML lee campos de `res.company`: se completaban los 6 pasos y la empresa quedaba sin configurar para emitir. Ahora escribe los campos.
10. **`action_check_expiry` del certificado no tiene `ir.cron`** que lo dispare.
11. **Datos muertos.** `l10n_ec_base/data/account.account.template.csv`, `account.tax.template.csv` y `l10n_ec_sri/data/account.*.csv` + `l10n_ec_chart_data.xml` no están en ningún manifest y usan modelos `*.template` eliminados desde Odoo 17.
12. **`t-esc` deprecado (→ `t-out`)** — 74 usos, y la mayoría están en la ruta activa de generación de comprobantes: `l10n_ec_sri/views/account_move_xml_template.xml` (28), `l10n_ec_retention_xml_template.xml` (20), `l10n_ec_reports/report/form_templates.xml` (13), `l10n_ec_hr_payroll/report/form_107_template.xml` (10), `l10n_ec_portal/views/portal_templates.xml` (2), `l10n_ec_pos/static/src/xml/pos_sri.xml` (1). Las plantillas de `l10n_ec_edi` ya usan `t-out`, las de `l10n_ec_sri` no — otra manifestación de la duplicación del punto anterior.
13. **Grupos de seguridad sin `res.groups.privilege`.** Odoo 19 eliminó `category_id` de `res.groups` y lo reemplazó por `privilege_id` → `res.groups.privilege`. El repo no usa `category_id` (bien), pero tampoco define ningún `res.groups.privilege`, así que los ~13 grupos de `l10n_ec_base/security/l10n_ec_groups.xml` y `l10n_ec/security/l10n_ec_security.xml` quedan sin agrupar en la UI. El `ir.module.category` `module_category_l10n_ec` se crea pero nadie lo referencia — registro huérfano.
14. **`_compute_tax_aggregates` infiere el código de impuesto SRI parseando el nombre del impuesto** (`"15%" in tax_obj.name`). Frágil; la versión de `l10n_ec_sri` (por `tax.amount` y `tax_group_id`) es menos mala pero tampoco usa un campo explícito. Falta un campo de código SRI en `account.tax`.

## Referencias

- `referencias/FICHA TE_CNICA ... Versio_n 234.pdf` — **la Ficha Técnica del esquema offline v2.34 es la fuente autoritativa** para estructura XML, catálogos y códigos. El código y el README dicen v2.32; ante discrepancia, gana el PDF.
- `referencias/Links_referencia.txt` — enlaces SRI, doc oficial de Odoo 19 para Ecuador, y repos de referencia (OCA `l10n-ecuador` ramas 18.0/19.0).
- `l10n_ec_sri/docs/11_regulatory_knowledge_base/` — base de conocimiento regulatorio 2026 por organismo (SRI, IESS, MDT, SUPERCIAS, SENAE); empezar por `INDEX.md` y `KB_MASTER_REGULATORY_2026.md`.
- `docs/srs/` — SRS del sistema (plantillas de negocio, flujos HR/inventario, matriz de regulaciones ERP, wizard de empresa).
- `l10n_ec_sri/docs/05_data_mapping/` — mapeo campo a campo Odoo ↔ XML SRI por tipo de comprobante (factura, retención, NC, guía, liquidación, ATS).
- Skill `odoo-19` (en `.agents/skills/odoo-19/`) — **invocarla antes de escribir Python o XML de Odoo**; cubre los breaking changes de 19 (`models.Constraint`, `models.Index`, vistas list, grupos por privilegios, `@api.private`).
