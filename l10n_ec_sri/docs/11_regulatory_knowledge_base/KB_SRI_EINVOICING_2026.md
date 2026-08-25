# SRI ELECTRONIC INVOICING - COMPLETE REFERENCE 2026
## Facturación Electrónica, XML, Retenciones

**Last Verified**: 2026-01-22
**Source**: sri.gob.ec, Resolution NAC-DGERCGC25-00000017

---

## 1. CRITICAL 2026 CHANGES

> **EFFECTIVE JANUARY 1, 2026**: Real-time transmission is MANDATORY

| Old Rule | New Rule (2026) |
|:---------|:----------------|
| 72-hour transmission grace | **IMMEDIATE transmission** |
| CF invoices could be annulled | **CF CANNOT be annulled** |
| No recipient confirmation | **5-day acceptance required** |
| Annul anytime | **7-day maximum** |

**Legal Basis**: Resolution NAC-DGERCGC25-00000017

---

## 2. DOCUMENT TYPES

| Code | Document | XML Root | Version |
|:-----|:---------|:---------|:--------|
| 01 | Factura | `<factura>` | **1.1.0** (Anexo 3) |
| 03 | Liquidación de Compra | `<liquidacionCompra>` | 1.1.0 |
| 04 | Nota de Crédito | `<notaCredito>` | 1.1.0 |
| 05 | Nota de Débito | `<notaDebito>` | 1.1.0 |
| 06 | Guía de Remisión | `<guiaRemision>` | 1.1.0 |
| 07 | Comprobante de Retención | `<comprobanteRetencion>` | 2.0.0 |

---

## 3. ACCESS KEY (CLAVE DE ACCESO)

### 3.1 Structure (49 Digits)
| Position | Length | Content |
|:---------|:-------|:--------|
| 1-8 | 8 | Date (DDMMYYYY) |
| 9-10 | 2 | Document Type |
| 11-23 | 13 | RUC |
| 24 | 1 | Environment (1=Test, 2=Prod) |
| 25-27 | 3 | Establishment (001) |
| 28-30 | 3 | Emission Point (001) |
| 31-39 | 9 | Sequential |
| 40-47 | 8 | Numeric Code (random) |
| 48 | 1 | Emission Type (1=Normal) |
| 49 | 1 | Check Digit (Mod 11) |

### 3.2 Modulo 11 Algorithm
```python
def compute_mod11(data: str) -> str:
    """
    Compute check digit using Modulo 11
    data: 48-character string
    returns: single digit 0-9
    """
    weights = [2, 3, 4, 5, 6, 7]
    total = 0
    for i, char in enumerate(reversed(data)):
        total += int(char) * weights[i % 6]

    remainder = total % 11
    check = 11 - remainder

    if check == 11:
        return '0'
    elif check == 10:
        return '1'
    return str(check)
```

---

## 4. IVA RATES 2026

| Code | Rate | Description | XML Element |
|:-----|:-----|:------------|:------------|
| 0 | 0% | Tarifa 0% | `codigoPorcentaje="0"` |
| 2 | 12% | **OBSOLETE** | Legacy only |
| 3 | 14% | **OBSOLETE** | Legacy only |
| **4** | **15%** | **STANDARD 2026** | `codigoPorcentaje="4"` |
| 5 | 5% | Construcción | `codigoPorcentaje="5"` |
| 6 | N/A | No Objeto | `codigoPorcentaje="6"` |
| 7 | N/A | Exento | `codigoPorcentaje="7"` |
| 8 | N/A | IVA diferenciado (sector turístico) | `codigoPorcentaje="8"` |
| 10 | 13% | Tarifa 13% | `codigoPorcentaje="10"` |

> Tabla 17 completa: son **nueve** códigos (0, 2, 3, 4, 5, 6, 7, 8, 10). El 8 y el 10
> faltaban en este documento; el generador de XML sí los contempla
> (`L10N_EC_VAT_PERCENT_CODE` en `l10n_ec_sri/models/l10n_ec_sri_xml.py`).

---

## 5. WITHHOLDING CODES

### 5.1 Income Tax (IR)
| Code | Rate | Description |
|:-----|:-----|:------------|
| 303 | 10% | Honorarios Profesionales |
| 304 | 8% | Servicios Predomina Intelecto |
| 307 | 2% | Servicios Mano de Obra |
| 308 | 2% | Servicios Entre Sociedades |
| 309 | 1% | Publicidad y Comunicación |
| 310 | 1% | Transporte |
| 312 | 1.75% | Transferencia de bienes muebles de naturaleza corporal |
| 319 | 1% | Arrendamiento Mercantil |
| 320 | 1.75% | Arrendamiento Inmuebles |
| 322 | 1% | Seguros y Reaseguros |
| 323 | 2% | Rendimientos Financieros |
| 325 | 0.2% | Loterías, Rifas |
| 327 | 2% | Combustibles |
| 328 | 0.2% | Productos Agrícolas |
| 332 | Variable | Pagos No Residentes |
| 340 | 1% | Artes Gráficas |
| 343 | 0.2% | Combustibles Comercializadoras |
| 344 | 25% | Dividendos Residentes |
| 500 | 25% | Pagos Paraísos Fiscales |

### 5.2 IVA Withholding

> ⚠️ **Dos numeraciones distintas, no intercambiables.** Los códigos 721…731 son del
> **Catálogo del ATS** (declaración informativa). El `<codigoRetencion>` que va en el
> XML del comprobante es el de la **Tabla 20 de la Ficha**, que es otra numeración.
> Confundirlos hace que el SRI rechace el comprobante.

**Tabla 20 — `<codigoRetencion>` del XML** (esto es lo que emite el sistema):

| Código | Tarifa retenida |
|:-------|:----------------|
| 1 | 30% |
| 2 | 70% |
| 3 | 100% |
| 7 | 0% — retención en cero (Res. NAC-DGERCGC15-00000284) |
| 8 | 0% — no procede retención |
| 9 | 10% |
| 10 | 20% |
| 11 | 50% |

ISD: `<codigo>6</codigo>` con `<codigoRetencion>4586</codigoRetencion>` para el 2,5%
vigente desde el 01-05-2025 (4580 para los tramos históricos).

**Catálogo ATS** (sólo para el anexo transaccional, no para el XML):

| Code | Rate | When Applied |
|:-----|:-----|:-------------|
| 721 | 10% | Bienes |
| 723 | 20% | Servicios |
| 725 | 30% | Bienes (Contribuyente Especial) |
| 727 | 70% | Servicios (CE) |
| 729 | 100% | Liquidación de Compra |
| 731 | 100% | Profesionales |

### 5.3 5-Day Rule
> **CRITICAL**: Withholdings must be emitted within 5 BUSINESS DAYS of the invoice date

```python
# Validation
from datetime import date, timedelta

def validate_withholding_date(invoice_date: date, withholding_date: date) -> bool:
    """Returns True if withholding is within 5-day rule"""
    business_days = 0
    current = invoice_date
    while current < withholding_date:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Mon-Fri
            business_days += 1
    return business_days <= 5
```

---

## 6. CONSUMIDOR FINAL

| Attribute | Value |
|:----------|:------|
| RUC | 9999999999999 |
| ID Type Code | 07 |
| Name | CONSUMIDOR FINAL |
| **Invoice Limit** | **$50.00 USD** |
| **Can Annul?** | **NO (2026)** |

```python
def validate_consumidor_final(vat: str, total: float) -> bool:
    """
    Validates Consumidor Final rules
    Returns True if valid, raises ValidationError if not
    """
    CF_RUC = "9999999999999"
    CF_LIMIT = 50.00

    if vat == CF_RUC and total > CF_LIMIT:
        raise ValidationError(
            f"Invoice to Consumidor Final cannot exceed ${CF_LIMIT}"
        )
    return True
```

---

## 7. SRI SOAP ENDPOINTS

### 7.1 Test Environment
| Service | URL |
|:--------|:----|
| Reception | `https://celcer.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl` |
| Authorization | `https://celcer.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl` |

### 7.2 Production Environment
| Service | URL |
|:--------|:----|
| Reception | `https://cel.sri.gob.ec/comprobantes-electronicos-ws/RecepcionComprobantesOffline?wsdl` |
| Authorization | `https://cel.sri.gob.ec/comprobantes-electronicos-ws/AutorizacionComprobantesOffline?wsdl` |

### 7.3 Methods
| Method | Service | Input | Output |
|:-------|:--------|:------|:-------|
| `validarComprobante` | Reception | Signed XML (bytes) | RECIBIDA/DEVUELTA |
| `autorizacionComprobante` | Authorization | Access Key (49 chars) | AUTORIZADO/NO AUTORIZADO |

---

## 8. XADES-BES SIGNING

### Requirements
- Algorithm: **RSA-SHA1**, con digests SHA-1 y canonicalización C14N inclusiva.
  No hay alternativa: la Ficha §6.8 fija RSA-SHA1 y clave de 2048 bits. "Modernizar"
  a SHA-256 hace que el SRI rechace la firma.
- Certificate: P12/PFX from authorized provider
- Authorized Providers:
  - Security Data
  - ANF AC Ecuador
  - Banco Central del Ecuador

### Structure
```xml
<ds:Signature>
  <ds:SignedInfo>
    <ds:CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>
    <ds:SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>
    <ds:Reference URI="#comprobante">
      <ds:DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>
      <ds:DigestValue>...</ds:DigestValue>
    </ds:Reference>
  </ds:SignedInfo>
  <ds:SignatureValue>...</ds:SignatureValue>
  <ds:KeyInfo>
    <ds:X509Data>
      <ds:X509Certificate>...</ds:X509Certificate>
    </ds:X509Data>
  </ds:KeyInfo>
  <ds:Object>
    <xades:QualifyingProperties>...</xades:QualifyingProperties>
  </ds:Object>
</ds:Signature>
```

---

## 9. ERROR CODES

| Code | Description | Action |
|:-----|:------------|:-------|
| 35 | Documento Duplicado | Use existing authorization |
| 43 | Clave Acceso Registrada | Retrieve existing |
| 45 | Error en Estructura | Fix XML and retry |
| 70 | RUC No Inscrito | Invalid customer RUC |

---

## 10. FICHA TÉCNICA VERSION

| Version | Date | Notes |
|:--------|:-----|:------|
| 2.26 | Mar 2024 | Base |
| 2.28 | Jun 2024 | Gran Contribuyente |
| 2.32 | Oct 2025 | Anexo 25 — operadoras de transporte comercial |
| 2.33 | 13 Jul 2026 | Anexo 25 — campo `placa` obligatorio; Tabla 33 |
| **2.34** | **27 Jul 2026** | **LATEST** — Anexo 26, RUC del proveedor del sistema |

---

**Classification**: Agent Knowledge Base - SRI
**Update**: On SRI resolution changes
