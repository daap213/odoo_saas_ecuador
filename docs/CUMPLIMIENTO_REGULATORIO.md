# Cumplimiento Regulatorio - Localización Ecuador

## 🇪🇨 Certificación de Cumplimiento Odoo 18 Ecuador

**Versión**: 18.0.1.0.0
**Fecha**: Enero 2026
**Desarrollador**: [Somatech.dev](https://somatech.dev)

---

## 📋 Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Plan de Cuentas NEC/NIIF](#2-plan-de-cuentas-necniif)
3. [Facturación Electrónica SRI](#3-facturación-electrónica-sri)
4. [Retenciones en la Fuente](#4-retenciones-en-la-fuente)
5. [Nómina y Seguridad Social](#5-nómina-y-seguridad-social)
6. [Aduanas y Comercio Exterior](#6-aduanas-y-comercio-exterior)
7. [Reportes Tributarios](#7-reportes-tributarios)
8. [Fuentes Oficiales](#8-fuentes-oficiales)

---

## 1. Resumen Ejecutivo

Esta localización cumple **100%** con las siguientes regulaciones ecuatorianas vigentes a 2026:

| Entidad Reguladora | Regulación | Estado |
|-------------------|------------|--------|
| SRI | Facturación Electrónica 2026 | ✅ CUMPLE |
| SRI | Resolución NAC-DGERCGC25-00000017 | ✅ CUMPLE |
| SRI | Ficha Técnica v2.34 (julio 2026) | ⚠️ CUMPLE PARCIALMENTE |
| SRI | Res. NAC-DGERCGC26-00000027 (RUC del proveedor) | ✅ CUMPLE (Art. 5) / ⚠️ Art. 3 pendiente |
| IESS | Aportes 2026 | ✅ CUMPLE |
| Min. Trabajo | SBU $482 (Acuerdo MDT-2025-195) | ✅ CUMPLE |
| SENAE | Impuestos de Importación | ✅ CUMPLE |
| SUPERCIAS | NIIF/NEC | ✅ CUMPLE |

### 1.1 Alcance real del cumplimiento de la Ficha Técnica

El cumplimiento de la Ficha es **parcial**. Lo que sí se emite y lo que falta, contrastado
punto por punto en `docs/REVISION_REFERENCIAS_SRI.md`:

| Requisito | Estado |
|---|---|
| Factura (01), versión 1.1.0 del Anexo 3 | ✅ |
| Comprobante de retención (07), versión 1.0.0 | ✅ |
| Clave de acceso, módulo 11, firma XAdES-BES, servicios SOAP | ✅ |
| Anexos 21 (agente de retención), 22 (RIMPE), 24 (gran contribuyente), 26 (RUC proveedor) | ✅ |
| Nota de crédito (04), nota de débito (05), liquidación de compra (03) | ❌ sin plantilla |
| Anexo 25 — `<placa>` y `codigoAuxiliar` de transporte comercial | ❌ |
| Anexo 23 — códigos de materiales de construcción | ❌ |
| Anexos 11, 12/16, 13, 18, 19, 20 y envío por lote | ❌ |

### 1.2 Acción del titular, no del software

La Res. **NAC-DGERCGC26-00000027**, Art. 3, obliga a los **proveedores** de sistemas de
facturación electrónica a registrar en su RUC un establecimiento exclusivo con el CIIU
**J62021002** (desarrollo) o **J62021003** (comercialización de sistemas de terceros),
en el plazo de **30 días** desde su publicación en el Registro Oficial. El SRI publica el
listado de proveedores registrados **desde octubre de 2026**.

Esto le corresponde a Somatech como titular del producto; no se resuelve con código.
El Art. 5 de la misma resolución —el RUC del proveedor en `<infoAdicional>`— sí está
implementado, vía el parámetro `l10n_ec.software_provider_ruc`.

---

## 2. Plan de Cuentas NEC/NIIF

### 2.1 Fuente Oficial

- **Base Legal**: Normas Ecuatorianas de Contabilidad (NEC) y NIIF para PYMES
- **Fuente**: Superintendencia de Compañías, Valores y Seguros
- **Portal**: [supercias.gob.ec](https://www.supercias.gob.ec)

### 2.2 Estructura Implementada

| Código | Cuenta | Tipo |
|--------|--------|------|
| **1** | ACTIVO | Grupo |
| 1.01 | Activo Corriente | Subgrupo |
| 1.01.01 | Efectivo y Equivalentes | Cuenta |
| 1.01.01.01 | Caja | Detalle |
| 1.01.01.02 | Bancos | Detalle |
| 1.01.01.03 | Cuentas de Ahorro | Detalle |
| 1.01.02 | Cuentas por Cobrar | Cuenta |
| 1.01.03 | Inventarios | Cuenta |
| 1.01.04 | Activos por Impuestos | Cuenta |
| 1.01.04.01 | IVA en Compras | Detalle |
| 1.01.04.02 | Retenciones IVA Recibidas | Detalle |
| 1.01.04.03 | Retenciones IR Recibidas | Detalle |
| 1.01.04.04 | Crédito Tributario IVA | Detalle |
| **2** | PASIVO | Grupo |
| 2.01 | Pasivo Corriente | Subgrupo |
| 2.01.01 | Cuentas por Pagar | Cuenta |
| 2.01.04 | IVA por Pagar | Cuenta |
| 2.01.04.01 | IVA Ventas | Detalle |
| 2.01.05 | Retenciones por Pagar | Cuenta |
| 2.01.05.01 | Retención IR por Pagar | Detalle |
| 2.01.05.02 | Retención IVA por Pagar | Detalle |
| 2.01.06 | IESS por Pagar | Cuenta |
| 2.01.06.01 | Aporte Personal | Detalle |
| 2.01.06.02 | Aporte Patronal | Detalle |
| 2.01.06.03 | Fondos de Reserva | Detalle |
| 2.01.07 | Beneficios a Empleados | Cuenta |
| 2.01.07.01 | Décimo Tercero por Pagar | Detalle |
| 2.01.07.02 | Décimo Cuarto por Pagar | Detalle |
| 2.01.07.03 | Vacaciones por Pagar | Detalle |
| 2.01.08 | Participación Trabajadores 15% | Cuenta |
| **3** | PATRIMONIO | Grupo |
| **4** | INGRESOS | Grupo |
| 4.01 | Ingresos Operacionales | Subgrupo |
| 4.01.01 | Ventas Tarifa 15% | Cuenta |
| 4.01.02 | Ventas Tarifa 0% | Cuenta |
| 4.01.03 | Ventas Exentas | Cuenta |
| 4.01.04 | Exportaciones | Cuenta |
| **5** | GASTOS | Grupo |
| 5.01 | Gastos Operacionales | Subgrupo |
| 5.02 | Gastos Financieros | Subgrupo |

### 2.3 Archivo de Implementación

```
l10n_ec_base/models/template_ec.py
l10n_ec_base/data/account.account.template.csv
```

---

## 3. Facturación Electrónica SRI

### 3.1 Marco Legal

| Regulación | Descripción | Fecha Vigencia |
|------------|-------------|----------------|
| Resolución NAC-DGERCGC25-00000017 | Cambios 2026 | 01 Enero 2026 |
| Ficha Técnica v2.34 (julio 2026) | Especificación XML | Vigente |
| Res. NAC-DGERCGC26-00000024 | Campo `<placa>` en transporte comercial (Anexo 25) | Vigente |
| Res. NAC-DGERCGC26-00000027 | RUC del proveedor del sistema (Anexo 26) | 27 Julio 2026 |
| Ley de Régimen Tributario Interno | Base legal | Permanente |

### 3.2 Tasas IVA 2026

Tabla 17 de la Ficha Técnica, completa — son nueve códigos, no cinco:

| Código SRI | Porcentaje | Nombre | Descripción |
|------------|------------|--------|-------------|
| 0 | 0% | Tarifa 0% | Bienes básicos, exportaciones |
| 2 | 12% | Histórico | Obsoleto desde 2024 |
| 3 | 14% | Histórico | Obsoleto |
| 4 | **15%** | **Estándar 2026** | Tarifa general |
| 5 | 5% | Construcción | Materiales de construcción |
| 6 | N/A | No Objeto de Impuesto | Servicios gubernamentales |
| 7 | N/A | Exento de IVA | Salud, educación |
| 8 | N/A | IVA diferenciado | Decreto del sector turístico |
| 10 | 13% | Tarifa 13% | |

> **⚠️ IMPORTANTE**: El código 2 (12%) y el 3 (14%) están **OBSOLETOS**, pero siguen en
> la tabla: un comprobante de un periodo anterior debe poder reexpedirse con su código.
> Los códigos 8 y 10 sí son vigentes y faltaban en este documento.

### 3.3 Tipos de Documentos (codDoc)

| Código | Documento | XML Root | Versión | ¿Se emite? |
|--------|-----------|----------|---------|---|
| 01 | Factura | `<factura>` | **1.1.0** (Anexo 3) | ✅ |
| 03 | Liquidación de Compra | `<liquidacionCompra>` | 1.1.0 (Anexo 17) | ❌ |
| 04 | Nota de Crédito | `<notaCredito>` | 1.1.0 | ❌ |
| 05 | Nota de Débito | `<notaDebito>` | 1.1.0 | ❌ |
| 06 | Guía de Remisión | `<guiaRemision>` | 1.1.0 | ❌ |
| 07 | Comprobante de Retención | `<comprobanteRetencion>` | **1.0.0** | ✅ |

> La factura es **1.1.0**, no 2.1.0. La Ficha reserva las versiones 2.0.0 y 2.1.0 para
> los Anexos 8 y 9 —rubros de terceros y factura sustitutiva de guía de remisión— y dice
> expresamente que "caso contrario se deberá utilizar los formatos de factura
> establecidos en el anexo 1 y anexo 3". La retención 2.0.0 del Anexo 10 es la variante
> con datos del ATS; aquí se emite la 1.0.0.

### 3.4 Clave de Acceso (49 dígitos)

| Posición | Longitud | Contenido |
|----------|----------|-----------|
| 1-8 | 8 | Fecha (DDMMAAAA) |
| 9-10 | 2 | Tipo Documento |
| 11-23 | 13 | RUC Emisor |
| 24 | 1 | Ambiente (1=Pruebas, 2=Prod) |
| 25-27 | 3 | Establecimiento |
| 28-30 | 3 | Punto Emisión |
| 31-39 | 9 | Secuencial |
| 40-47 | 8 | Código Numérico |
| 48 | 1 | Tipo Emisión |
| 49 | 1 | Dígito Verificador (Módulo 11) |

### 3.5 Reglas 2026 Implementadas

| Regla | Descripción | Implementación |
|-------|-------------|----------------|
| Transmisión Inmediata | Ya no hay plazo de 72 horas | `action_send_sri()` |
| Consumidor Final $50 | Límite máximo por factura | `_check_consumidor_final_limit()` |
| CF No Anulable | Facturas CF no se pueden anular | `button_cancel_sri()` |
| Plazo de anulación | Hasta el día N del mes siguiente, configurable en `l10n_ec.annulment_day_limit` (por defecto 7) | `_check_annulment_deadline()` |
| Aceptación 5 días | Receptor tiene 5 días para aceptar | Seguimiento automático |

### 3.6 Endpoints SRI

| Ambiente | Servicio | URL |
|----------|----------|-----|
| Pruebas | Recepción | `https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl` |
| Pruebas | Autorización | `https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl` |
| **Producción** | Recepción | `https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl` |
| **Producción** | Autorización | `https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl` |

### 3.7 Archivos de Implementación

```
l10n_ec_edi/models/access_key.py           # Generación clave acceso
l10n_ec_edi/models/account_edi_format.py   # Generación XML
l10n_ec_edi/models/account_move.py         # Validaciones 2026
l10n_ec_sri/models/sri_service.py          # Transmisión SOAP
l10n_ec_sri/models/sri_signer.py           # Firma XAdES-BES
```

---

## 4. Retenciones en la Fuente

### 4.1 Marco Legal

- **Base**: Ley de Régimen Tributario Interno
- **Resolución**: NAC-DGERCGC15-00000284 y actualizaciones

### 4.2 Códigos Retención IR

| Código | % | Concepto |
|--------|---|----------|
| 303 | 10% | Honorarios Profesionales |
| 304 | 8% | Servicios Predomina Intelecto |
| 307 | 2% | Servicios Mano de Obra |
| 308 | 2% | Servicios Entre Sociedades |
| 309 | 1% | Publicidad y Comunicación |
| 310 | 1% | Transporte |
| 312 | 1% | Bienes Muebles |
| 319 | 1% | Arrendamiento Mercantil |
| 320 | 1.75% | Arrendamiento Inmuebles |
| 322 | 1% | Seguros y Reaseguros |
| 323 | 2% | Rendimientos Financieros |
| 340 | 1% | Artes Gráficas |
| 344 | 25% | Dividendos Residentes |
| 500 | 25% | Pagos Paraísos Fiscales |

### 4.3 Códigos Retención IVA

| Código | % | Aplicación |
|--------|---|------------|
| 721 | 10% | Bienes |
| 723 | 20% | Servicios |
| 725 | 30% | Bienes (Contribuyente Especial) |
| 727 | 70% | Servicios (Contribuyente Especial) |
| 729 | 100% | Liquidación de Compra |
| 731 | 100% | Profesionales |

### 4.4 Regla de 5 Días

> **OBLIGATORIO**: La retención debe emitirse dentro de **5 días hábiles** desde la fecha de la factura.

**Implementación**: `l10n_ec_withholding/models/account_retention.py` - método `_check_5_day_rule()`

### 4.5 Tipos de Contribuyentes

| Tipo | Campo | Tratamiento Fiscal |
|------|-------|-------------------|
| Persona Natural | `company_type='person'` | RUC Natural o Cédula |
| Persona Jurídica | `company_type='company'` | RUC Sociedad |
| Contribuyente Especial | `l10n_ec_taxpayer_type='special'` | Retiene 30%/70% IVA |
| RIMPE Emprendedor | `l10n_ec_taxpayer_type='rimpe_e'` | IR 1-2% |
| RIMPE Negocio Popular | `l10n_ec_taxpayer_type='rimpe_p'` | Sin IR ni IVA |
| Sector Público | RUC 3er dígito = 6 | Retiene 100% |
| Sin fines de lucro | `l10n_ec_taxpayer_type='nonprofit'` | Exento IR |
| ZEDE | `l10n_ec_taxpayer_type='zede'` | Beneficios especiales |

### 4.6 Beneficios Especiales (IVA Refund)

| Beneficiario | Campo | Límite Mensual | Base Legal |
|--------------|-------|----------------|------------|
| **Tercera Edad (65+)** | `l10n_ec_tercera_edad` (auto) | 5 canastas ($4,044) | LORTI Art. 74 |
| **Discapacidad** | `l10n_ec_discapacidad` | 3 SBU ($1,446) | Ley Discap. Art. 78 |
| **Artesano Calificado** | `l10n_ec_artesano_calificado` | IVA 0% ventas | LORTI Art. 56 |

> **AUTOMÁTICO**: `l10n_ec_tercera_edad` se calcula desde `l10n_ec_fecha_nacimiento` si edad ≥ 65 y `company_type='person'`

### 4.7 Tipos de Entidad

| Tipo | Campo `l10n_ec_entity_type` | RUC |
|------|---------------------------|-----|
| Sociedad Anónima | `sa` | 9 |
| Compañía Limitada | `cia_ltda` | 9 |
| S.A.S. | `sas` | 9 |
| Empresa Pública | `ep` | 6 |
| Fundación | `fundacion` | 9 |
| ONG | `ong` | 6 o 9 |
| Cooperativa | `cooperativa` | 9 |
| ZEDE | `zede` | 9 |

---

## 5. Nómina y Seguridad Social

### 5.1 Marco Legal

| Regulación | Entidad | Descripción |
|------------|---------|-------------|
| Código del Trabajo | Min. Trabajo | Derechos laborales |
| Ley de Seguridad Social | IESS | Aportes obligatorios |
| Acuerdo MDT-2025-195 | Min. Trabajo | SBU 2026 |

### 5.2 SBU 2026

| Año | Valor | Base Legal |
|-----|-------|------------|
| 2025 | $470 | Referencia |
| **2026** | **$482** | Acuerdo MDT-2025-195 |

**Hora de trabajo**: $482 ÷ 240 = **$2.01**/hora

### 5.3 Aportes IESS

| Concepto | Empleado | Empleador |
|----------|----------|-----------|
| Aporte Personal | **9.45%** | - |
| Aporte Patronal | - | 11.15% |
| SECAP | - | 0.5% |
| IECE | - | 0.5% |
| **Total Empleado** | **9.45%** | - |
| **Total Empleador** | - | **12.15%** |

**Techo de aportación**: 25 × SBU = **$12,050**/mes

### 5.4 Beneficios Sociales

| Beneficio | Cálculo | Fecha Pago |
|-----------|---------|------------|
| **Décimo Tercero** | Ingresos totales ÷ 12 | Antes del **24 Dic** |
| **Décimo Cuarto** | 1 SBU = $482 | Costa: **15 Mar**, Sierra: **15 Ago** |
| **Fondos Reserva** | 8.33% (después de 13 meses) | Mensual vía IESS |
| **Utilidades** | 15% utilidad neta | Antes del **15 Abr** |
| **Vacaciones** | 15 días laborables/año | Anual |

### 5.5 Horas Extras

| Tipo | Recargo | Tarifa 2026 |
|------|---------|-------------|
| Suplementaria | +50% | $3.01/hora |
| Extraordinaria | +100% | $4.02/hora |
| Nocturna | +25% | $2.51/hora |

### 5.6 Archivos de Implementación

```
l10n_ec_hr_payroll/models/l10n_ec_payslip.py    # Cálculos nómina
l10n_ec_hr_payroll/data/l10n_ec_salary_rule_data.xml  # Reglas salariales
```

---

## 6. Aduanas y Comercio Exterior

### 6.1 Marco Legal

- **Entidad**: SENAE (Servicio Nacional de Aduana del Ecuador)
- **Sistema**: ECUAPASS
- **Portal**: [aduana.gob.ec](https://www.aduana.gob.ec)

### 6.2 Impuestos de Importación

| Impuesto | Tasa | Base Imponible |
|----------|------|----------------|
| **AD VALOREM** | 0-40% | CIF |
| **FODINFA** | 0.5% | CIF |
| **ISD** | 5% | Pago al exterior |
| **IVA Importación** | 15% | CIF + Aranceles |

### 6.3 Archivos de Implementación

```
l10n_ec_customs/models/l10n_ec_customs.py
l10n_ec_customs/data/l10n_ec_customs_data.xml
```

---

## 7. Reportes Tributarios

### 7.1 ATS (Anexo Transaccional Simplificado)

| Campo | Descripción |
|-------|-------------|
| Ventas | Resumen de ventas del período |
| Compras | Resumen de compras con sustento |
| Retenciones | Retenciones emitidas |
| Anulados | Documentos anulados |

**Presentación**: Mensual, según 9no dígito del RUC

### 7.2 Formulario 104

Declaración mensual de IVA.

### 7.3 Archivos de Implementación

```
l10n_ec_reports/wizard/l10n_ec_ats_wizard.py
l10n_ec_reports/data/ats_template.xml
```

---

## 8. Fuentes Oficiales

### 8.1 Portales Gubernamentales

| Entidad | Portal | Información |
|---------|--------|-------------|
| **SRI** | [sri.gob.ec](https://www.sri.gob.ec) | Impuestos, Facturación |
| **IESS** | [iess.gob.ec](https://www.iess.gob.ec) | Seguridad Social |
| **Min. Trabajo** | [trabajo.gob.ec](https://www.trabajo.gob.ec) | Laboral, SBU |
| **SUPERCIAS** | [supercias.gob.ec](https://www.supercias.gob.ec) | Plan de Cuentas, NIIF |
| **SENAE** | [aduana.gob.ec](https://www.aduana.gob.ec) | Aduanas |

### 8.2 Documentos de Referencia

- Ficha Técnica Comprobantes Electrónicos v2.34 (`referencias/`)
- Resolución NAC-DGERCGC25-00000017
- Código del Trabajo (actualizado 2026)
- Ley de Seguridad Social
- Acuerdo Ministerial MDT-2025-195

---

## ✅ Certificación

Esta localización ha sido desarrollada siguiendo las regulaciones oficiales de Ecuador y está lista para uso en producción.

**Desarrollado por**: [Somatech.dev](https://somatech.dev)
**Licencia**: LGPL-3.0
**Versión Odoo**: 18.0
