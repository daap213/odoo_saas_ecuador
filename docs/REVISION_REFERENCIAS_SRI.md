# Revisión de la documentación de referencia del SRI

**Fecha de la revisión:** 2026-08-23
**Corpus revisado:** `referencias/` (2 PDF + enlaces) y los 170 documentos `.md` del repo
**Rama:** `19.0` (commit `5bf9984`)

---

## 1. Jerarquía de autoridad del corpus

No todos los documentos del repo tienen el mismo peso. En orden descendente:

| Nivel | Documento | Estado |
|---|---|---|
| 1 — Autoritativo | `referencias/FICHA TE_CNICA ... Versio_n 234.pdf` (v2.34, jul-2026, 141 pág.) | Vigente |
| 1 — Autoritativo | `referencias/NAC-DGERCGC26-00000027.pdf` (27-jul-2026) | Vigente |
| 2 — Derivado | `l10n_ec_sri/docs/11_regulatory_knowledge_base/KB_SRI_*` | Desactualizado (declara 2.32 como "LATEST") |
| 2 — Derivado | `l10n_ec_sri/docs/05_data_mapping/DM_*` | Desactualizado (declara factura v2.1.0) |
| 3 — Descriptivo | `docs/CUMPLIMIENTO_REGULATORIO.md`, `README.md`, SRS | Desactualizado en varios puntos |

Ante cualquier discrepancia, **gana el PDF**. Los `.md` del repo son notas de trabajo,
no fuente normativa, y varios contradicen la Ficha (§5 y §6 de este informe).

---

## 2. Qué cambió respecto de lo que el repo documenta (v2.32 → v2.34)

La Ficha registra dos revisiones posteriores a la 2.32 que casi toda la documentación
interna todavía ignora:

| Versión | Fecha | Cambio |
|---|---|---|
| **2.33** | 13/07/2026 | **Anexo 25**: campo `<placa>` obligatorio en facturas de operadoras de transporte comercial (excepto taxis). Nueva **Tabla 33** con el formato de llenado. Base: Res. NAC-DGERCGC26-00000024. |
| **2.34** | 27/07/2026 | **Anexo 26**: RUC del proveedor del sistema de facturación, obligatorio en `<infoAdicional>`. Base: Res. NAC-DGERCGC26-00000027. |

### 2.1 Resolución NAC-DGERCGC26-00000027 (el PDF suelto de `referencias/`)

Firmada el 27-jul-2026. Dos obligaciones distintas, con destinatarios distintos:

- **Art. 5 — para el emisor** (todo cliente de este SaaS que use un facturador de
  terceros): incluir el RUC del proveedor en `<infoAdicional>`, tag `<campoAdicional>`
  con `nombre="RUC Proveedor"`, alfanumérico, máx. 300 caracteres.
  **Plazo: 60 días calendario desde la publicación en Registro Oficial.**
- **Art. 3 + Disp. Transitoria Primera — para Somatech como proveedor**: registrar en
  el RUC un establecimiento exclusivo con el CIIU **J62021002** (desarrollo de sistemas
  de comprobantes electrónicos) o **J62021003** (comercialización de sistemas de
  terceros). **Plazo: 30 días desde la publicación en Registro Oficial.**
  El SRI publicará el listado de proveedores registrados **a partir de octubre de 2026**.

> El Art. 3 es una obligación del titular del producto, no del software. No se resuelve
> escribiendo código. Conviene verificar el estado del RUC de Somatech antes de que se
> publique el listado.

---

## 3. Verificación punto por punto: Ficha 2.34 ↔ código

Lo que **sí** coincide (verificado leyendo el código, no asumido):

| Requisito de la Ficha | Dónde | Estado |
|---|---|---|
| Clave de acceso: 49 dígitos, composición de Tabla 1 | `l10n_ec_sri_xml.generate_access_key` | ✅ |
| Módulo 11, pesos 2..7 de derecha a izquierda; 11→0, 10→1 | `_get_modulo_11` | ✅ verificado contra 5 de las 6 claves de ejemplo de la Ficha (§7) |
| Secuencial rellenado a 9 dígitos | `_get_sequential` (`zfill(9)`) | ✅ |
| Tabla 2: sólo emisión normal (`1`) en esquema offline | literal `1` en la plantilla | ✅ |
| Tabla 4: ambiente `1`=Pruebas, `2`=Producción | `_get_document_components` | ✅ (la inversión histórica está corregida) |
| Tabla 6: tipos de identificación 04/05/06/07/08 | `l10n_ec_catalogs_data.xml` | ✅ los 5, con longitudes |
| Tabla 6 nota: consumidor final = `9999999999999` | `l10n_ec.consumidor_final_ruc` | ✅ |
| §9.10: sobre 50 USD hay que identificar al adquirente | `l10n_ec.consumidor_final_limit` = `50.00` | ✅ |
| Tabla 16: códigos de impuesto 2/3/5 | constantes `L10N_EC_TAX_CODE_*` | ✅ |
| Tabla 17: `codigoPorcentaje` 0/2/3/4/5/6/7/8/10 | `L10N_EC_VAT_PERCENT_CODE` | ✅ los 9, incluido el 8 (diferenciado) y el 10 (13%) |
| Tabla 19: 1=Renta, 2=IVA, 6=ISD | plantilla de retención | ✅ |
| Tabla 24: formas de pago 01/15/16/17/18/19/20/21 | `l10n_ec_catalogs_data.xml` | ✅ las 8, exactas |
| §6.2/6.8: XAdES-BES 1.3.2, enveloped, UTF-8, RSA-SHA1, 2048 bits, PKCS12 | `sri_signer.py` | ✅ |
| §6.4/6.5: firma sobre comprobante + SignedProperties + KeyInfo con cert base64 | 3 `<ds:Reference>` | ✅ |
| §7.2.1/7.2.2: URLs de pruebas (`celcer`) y producción (`cel`) | `DEFAULT_URLS` + `ir.config_parameter` | ✅ resuelve por ambiente y por compañía |
| §5.10: reenviar con la MISMA clave y secuencial | clave persistida, código numérico determinista | ✅ |
| §11 códigos 43 y 70 = ya recibido, no reenviar | `ALREADY_RECEIVED_CODES` | ✅ |
| Anexo 3 (factura 1.1.0): orden de etiquetas y 6 decimales | `account_move_xml_template.xml` | ✅ |
| Anexo 21: `<agenteRetencion>`, resolución sin ceros a la izquierda, máx. 8 | plantilla factura y retención | ✅ |
| Anexo 22: leyenda RIMPE literal de 27 / 45 caracteres | `res_company.l10n_ec_rimpe_legend` | ✅ |
| Anexo 24: "Gran Contribuyente" en `<infoAdicional>` | `_get_additional_info` | ✅ |
| **Anexo 26**: `nombre="RUC Proveedor"` en `<infoAdicional>` | `l10n_ec.software_provider_ruc` | ✅ **ya implementado** |
| §9.11: máximo 15 campos adicionales | `fields_list[:15]` | ✅ |

La elección de la versión **1.1.0** para la factura es correcta y está bien argumentada
en el comentario de la plantilla: la Ficha reserva 2.0.0/2.1.0 (Anexos 8 y 9) para rubros
de terceros y factura sustitutiva de guía de remisión, e indica que "caso contrario se
deberá utilizar los formatos de factura establecidos en el anexo 1 y anexo 3".

---

## 4. Hallazgos: dónde el código se aparta de la Ficha

### 4.1 La emisión de retenciones estaba rota de raíz — y los códigos, mal

> **Corrección a la primera versión de este informe.** Aquí se decía que el código 9 mal
> etiquetado corrompía el XML. No era exacto: **nada leía ese catálogo durante la
> emisión**. El daño real era mayor y estaba un nivel más abajo.

La plantilla del comprobante de retención lee `tax_id.l10n_ec_get_retention_code()`, que
resuelve sobre `account.tax.l10n_ec_code`. **Ningún `account.tax` del repo tenía ese
campo sembrado**, así que toda emisión de retención moría en `ValidationError`.

La causa de fondo era la duplicación: **tres catálogos de retención** y **dos modelos de
documento**, y la ruta viva no leía ninguno de los catálogos.

| Artefacto | Módulo | ¿Lo leía la emisión? |
|---|---|---|
| `l10n_ec.retention.code` (IR 303…500, IVA 721…731) | `l10n_ec_base` | ❌ nadie |
| `l10n_ec.withholding.tax` (IVA 1/2/3/9) | `l10n_ec_withholding` | ❌ sólo `account.retention.line` |
| `account.tax.l10n_ec_code` | `l10n_ec_sri` | ✅ sí, pero vacío |
| `l10n_ec.retention` + vistas + ACL + secuencia + XML | `l10n_ec_sri` | ✅ ruta viva |
| `account.retention` + vistas + ACL + wizard | `l10n_ec_withholding` | ❌ ruta paralela |

Los códigos IVA 721…731 del primer catálogo son del **Catálogo ATS**, no el
`<codigoRetencion>` del XML: tenerlos junto a los correctos era la fuente de la confusión.

**Resuelto.** `account.tax` es ahora la única fuente; el código se resuelve en cascada
(valor manual → campo del addon oficial → deducción por porcentaje para IVA e ISD, cuyas
tablas son cerradas). Los de renta siguen exigiendo configuración explícita, porque la
Ficha no los enumera y delega en el Catálogo ATS. Los catálogos y el modelo duplicados se
eliminaron, con `pre-migrate.py` para trasladar los datos existentes.

La Ficha, **Tabla 20**, fija estos `codigoRetencion` para IVA:

| % IVA retenido | Código |
|---|---|
| 10 % | **9** |
| 20 % | **10** |
| 30 % | 1 |
| 50 % | **11** |
| 70 % | 2 |
| 100 % | 3 |
| Retención en cero (0,00 %) | **7** |
| No procede retención (0,00 %) | **8** |

El catálogo eliminado declaraba sólo cuatro, y uno estaba mal:

```xml
<record id="tax_ret_iva_9" model="l10n_ec.withholding.tax">
    <field name="code">9</field>
    <field name="name">No Procede Retención IVA (0%)</field>
    <field name="percentage">0.0</field>
</record>
```

El código **9 es 10 %**, no "no procede". "No procede retención" es el **8**; "retención
en cero" es el **7**. Faltaban además el **7**, el **10** y el **11**.

La tabla completa vive ahora en `L10N_EC_VAT_WITHHOLD_CODE_BY_RATE`
(`l10n_ec_sri/models/account_tax.py`), con un test por cada porcentaje.

Segunda contradicción, ya resuelta: el código **312** figuraba como **1,0 %** en
`l10n_ec_base` y **1,75 %** en `l10n_ec_withholding`. Vale **1,75 %** (transferencia de
bienes muebles de naturaleza corporal). La Ficha no arbitra —delega los porcentajes de
renta en el Catálogo del ATS, que conviene archivar en `referencias/` (§6).

### 4.2 No hay código de retención de ISD

**Resuelto.** Tabla 19 admite el impuesto **6 = ISD** y Tabla 20 fija su código: **4586**
para el 2,5 % vigente desde el 1 de mayo de 2025 (el histórico 4580 cubre los tramos
anteriores). Ningún catálogo lo declaraba, aunque `l10n_ec_customs` sí calcula ISD, así
que la plantilla emitía `<codigo>6</codigo>` sin `codigoRetencion` válido. Ahora un
impuesto marcado como ISD resuelve a 4586 automáticamente
(`L10N_EC_ISD_WITHHOLD_CODE`).

### 4.3 `render_xml` genera siempre `<factura>`, sea cual sea el tipo de documento

`l10n_ec_sri_xml.render_xml` renderiza incondicionalmente `l10n_ec_sri.xml_invoice`,
mientras que `generate_access_key` sí toma el `codDoc` real de
`l10n_latam_document_type_id`. Y `action_send_sri` no filtra por tipo.

Consecuencia: al publicar una **nota de crédito (04)** o **nota de débito (05)** con
`l10n_ec.auto_send_sri` activo, se firma y transmite un cuerpo `<factura>` cuya clave de
acceso lleva `codDoc` 04/05 → error 35 ("documento inválido", el XSD no corresponde) o 58
("clave de acceso con componentes diferentes a los del comprobante"). Nunca autorizará.

De los 6 tipos de comprobante electrónico de la Tabla 3, la ruta activa cubre dos:

| codDoc | Comprobante | Plantilla en la ruta activa |
|---|---|---|
| 01 | Factura | ✅ `l10n_ec_sri.xml_invoice` (1.1.0) |
| 03 | Liquidación de compra | ❌ (Anexo 17) |
| 04 | Nota de crédito | ❌ |
| 05 | Nota de débito | ❌ |
| 06 | Guía de remisión | ⚠️ `l10n_ec_stock/data/guia_template.xml`, fuera de la orquestación de `l10n_ec_sri` |
| 07 | Comprobante de retención | ✅ `l10n_ec_sri.xml_retention` (1.0.0) |

**Resuelto parcialmente.** `action_send_sri` y `_check_emission_requirements` rechazan
ahora con un `UserError` explicativo cualquier `codDoc` fuera de
`L10N_EC_SUPPORTED_DOCUMENT_CODES`, antes de generar la clave de acceso —así no se gasta
un secuencial en un envío que nunca autorizará. El auto-envío captura la excepción, de
modo que la nota de crédito se sigue publicando con el motivo registrado.

Las plantillas de NC, ND y liquidación siguen pendientes: emitirlas es trabajo aparte.

### 4.4 Anexo 25 (transporte comercial) no implementado

Dos requisitos, ambos ya exigibles:

- `<codigoAuxiliar>` con **H492001** (factura de la operadora al cliente) o **H492002**
  (factura del socio/accionista a la operadora), en cada ítem de transporte.
  *Obligatorio desde el 01-nov-2025.*
- `<placa>` entre `<moneda>` y `<pagos>`, formato Tabla 33: `ABC1234`, sin espacios,
  y con cero a la izquierda si sólo hay tres dígitos (`ABC0123`).
  *Obligatorio 90 días después de la publicación de la Res. NAC-DGERCGC26-00000024.*

La plantilla activa no emite `<placa>` y usa `<codigoAuxiliar>` para el `barcode` del
producto, que colisiona con este uso normativo.

### 4.5 Anexo 23 (materiales de construcción) no implementado

Tabla 31 exige códigos exactos en `<codigoAuxiliar>` para 18 subcategorías
(`F010101` varilla laminada, `F010201` arcilla, `F010301` hormigón premezclado,
`F010401` cemento…). Mismo conflicto con el `barcode`. Nótese que el repo **sí** tiene
el IVA 5 % de construcción (`l10n_ec.iva_rate_construccion`) — está la tarifa pero no
la trazabilidad del material que la justifica.

### 4.6 El plazo de anulación está hardcodeado

`l10n_ec_edi/models/account_move.py:153-156` construye el deadline con un `7` literal:

```python
deadline = date(emission_date.year, emission_date.month + 1, 7)
```

Existe `_get_annulment_day()` leyendo `l10n_ec.annulment_day_limit`, y existe el
parámetro sembrado — pero el constraint no lo usaba. Contradecía el principio "todo
configurable" del proyecto: cambiar el parámetro no cambiaba el comportamiento.

**Resuelto.** El cálculo se unificó en `_l10n_ec_get_annulment_deadline()`, que sí lee la
configuración y además recorta el día al último del mes destino (un parámetro de 30 o 31
hacía reventar `date()` en febrero). `_check_annulment_deadline` y
`_check_cancellation_allowed` comparten ese helper en vez de duplicar la aritmética.

### 4.7 Código numérico sin entropía (menor)

`numeric=components["sequential"][-8:].zfill(8)`. La Ficha deja el algoritmo a "potestad
absoluta del contribuyente emisor", así que **no es incumplimiento**, y el determinismo
es deliberado y correcto para la idempotencia de §5.10. Pero el secuencial ya está en la
clave: estos 8 dígitos aportan cero información nueva, y la Ficha describe el campo como
"un mecanismo para brindar seguridad al emisor". Un hash truncado de
`(RUC + estab + ptoEmi + secuencial + fecha)` sería igual de determinista y sí cumpliría
ese propósito.

### 4.8 Anexos no cubiertos (inventario)

Sin evidencia en el código, por si entran en alcance más adelante:

| Anexo | Materia |
|---|---|
| 11 | Factura comercial negociable |
| 12 / 16 | Combustibles líquidos derivados de hidrocarburos (campo `placa`) |
| 13 | Comprobantes emitidos desde máquina fiscal (marca, tipo, serie) |
| 17 | Liquidación de compra 1.0.0 / 1.1.0 |
| 18 | Fundas plásticas |
| 19 | Autorretenciones |
| 20 | Devolución automática de IVA a adultos mayores |
| — | `<valorRetIva>` / `<valorRetRenta>` de Anexo 3 (comercializadores de derivados de petróleo y prensa) |
| — | Envío por lote (Tabla 8/9): límite 500 kb o 50 comprobantes; individual 320 kb |

---

## 5. Documentación interna que contradice la Ficha

Estos `.md` inducen a error a quien los tome como especificación:

| Archivo | Dice | Debe decir |
|---|---|---|
| `docs/CUMPLIMIENTO_REGULATORIO.md:32,109,387` | Ficha v2.32 | v2.34 |
| `docs/CUMPLIMIENTO_REGULATORIO.md:128` | Factura `<factura>` v**2.1.0** | v1.1.0 (Anexo 3) — 2.1.0 es sólo Anexos 8/9 |
| `KB_SRI_EINVOICING_2026.md:249` / `KB_MASTER_REGULATORY_2026.md:51` | "2.32 — **LATEST**" | 2.34 |
| `KB_SRI_EINVOICING_2026.md` §2 | Factura v2.1.0 | v1.1.0 |
| `KB_SRI_EINVOICING_2026.md` §4 | Tabla IVA sin códigos 8 ni 10 | Tabla 17 tiene 9 códigos: 0,2,3,4,5,6,7,8,10 |
| `KB_SRI_EINVOICING_2026.md` §5.2 | Retención IVA = 721/723/725/727/729/731 | Esos son códigos **ATS**, no el `<codigoRetencion>` del XML. Tabla 20: 1,2,3,7,8,9,10,11 |
| `KB_SRI_EINVOICING_2026.md` §5.1 | código 312 = **1 %** | El dato del repo (`retention_codes_2026.xml`) dice **1,75 %**. Contradicción interna sin resolver desde la Ficha (§7) |
| `KB_SRI_EINVOICING_2026.md:200` | "RSA-SHA1 (legacy) **or** RSA-SHA256" | La Ficha §6.8 dice RSA-SHA1, sin alternativa |
| `README.md:41`, `l10n_ec_edi/__manifest__.py:19` | "XAdES-BES (**SHA-256**)" | SHA-1. El código está bien; la etiqueta miente |
| `l10n_ec_edi/__manifest__.py:11,26` | "Ficha 2.32" | 2.34 |
| `SRS_L10N_EC_2026.md:29` | "Ficha Técnica v2.1" | v2.34 |
| `ECUADOR_ODOO_18_MASTER_SPECIFICATION.md:645` | "v2.28" | v2.34 |
| `legacy_sri_analysis_report.md:27` | "Offline V2.21 (2025)" | v2.34 |
| `05_IT_ARCHITECT_GUIDE.md:275,373`, `DM_01_ELECTRONIC_INVOICE.md:15,202`, `SRS_MODULE_02:107,113`, `PF_01:49` | factura v2.1.0 | v1.1.0 |

La afirmación **"SRI · Ficha Técnica v2.32 · ✅ CUMPLE"** de
`docs/CUMPLIMIENTO_REGULATORIO.md:32` no es sostenible tal cual: la versión vigente es
otra y hay anexos exigibles sin implementar (§4.4, §4.5).

---

## 6. Afirmaciones que el corpus de referencia no respalda

`KB_SRI_EINVOICING_2026.md` §1 atribuye a la **Resolución NAC-DGERCGC25-00000017** cuatro
reglas que gobiernan constraints reales del código (`_check_consumidor_final_limit`,
`_check_annulment_deadline`):

- transmisión en tiempo real obligatoria desde el 01-01-2026,
- prohibición de anular facturas a consumidor final,
- aceptación del receptor en 5 días,
- plazo máximo de anulación de 7 días.

**Esa resolución no está en `referencias/`** y la Ficha 2.34 no menciona ninguno de los
cuatro puntos. No pude verificarlas contra el corpus disponible. Dado que sustentan
validaciones bloqueantes, conviene descargar el PDF y archivarlo junto a los otros dos.
Lo mismo aplica a la **NAC-DGERCGC26-00000024** (citada en la nota 17 de la Ficha como
base del campo `<placa>`) y al **Catálogo del ATS**, que es la fuente real de los
porcentajes de retención de renta — la Ficha explícitamente delega en él y no los lista.

---

## 7. Errata detectada en la propia Ficha

Verifiqué el algoritmo del dígito verificador contra las seis claves de acceso de ejemplo
que aparecen en el PDF. **Cinco coinciden**; una no:

```
0403201301176815353000110015010000000081234567816   (Anexo 3, factura 1.1.0)
                                                 ^ declara 6, el módulo 11 da 0
```

Descomponiendo: `04032013|01|1768153530001|1|001|501|000000008|12345678|1`. La
composición es coherente con el `<estab>001</estab><ptoEmi>501</ptoEmi>` del propio
ejemplo, así que es el dígito verificador del PDF el que está mal, no la implementación.
Las claves de §7.2.3 y de la Tabla 8 sí validan. **No cambiar el algoritmo por este caso.**

---

## 8. Estado del trabajo

Hecho en la tanda de correcciones posterior a esta revisión:

- **§4.1** — `account.tax` es la única fuente de códigos SRI, con resolución en cascada y
  la Tabla 20 completa. Eliminados `l10n_ec.retention.code` y `l10n_ec.withholding.tax`.
- **§4.2** — ISD resuelve a 4586.
- **§4.3** — bloqueado el envío de comprobantes sin plantilla.
- **§4.6** — plazo de anulación configurable de verdad.
- **§5** — versiones y afirmaciones corregidas en manifests, README y base de conocimiento.
- Consolidación de `account.retention` en `l10n_ec.retention`, con script de migración.

Pendiente, por orden:

1. **§2.1 Art. 3** — verificar el CIIU en el RUC de Somatech. Plazo administrativo
   corriendo; no se resuelve con código.
2. **§6** — archivar en `referencias/` la Res. NAC-DGERCGC25-00000017, la
   NAC-DGERCGC26-00000024 y el Catálogo del ATS.
3. **§4.4, §4.5** — Anexo 25 (transporte comercial) y Anexo 23 (materiales de
   construcción). Ambos exigen resolver antes el conflicto de `codigoAuxiliar` con el
   `barcode` del producto.
4. **§4.3** — plantillas XML de NC (04), ND (05) y liquidación de compra (03).
5. **§4.8** — el resto de anexos y el envío por lote.
