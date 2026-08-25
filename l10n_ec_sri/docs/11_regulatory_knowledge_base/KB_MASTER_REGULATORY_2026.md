# COMPREHENSIVE REGULATORY KNOWLEDGE BASE 2026
## Ecuador ERP Implementation - Official Sources Verified

**Last Updated**: 2026-01-22
**Verification Method**: Official Government Websites + Legal Publications
**For Use By**: AI Agents and Development Teams

---

## REGULATORY AGENCIES OVERVIEW

| Agency | Portal | Domain |
|:-------|:-------|:-------|
| **SRI** | sri.gob.ec | Taxes, Electronic Invoicing |
| **IESS** | iess.gob.ec | Social Security, Payroll |
| **Min. Trabajo** | trabajo.gob.ec | Labor, Contracts, SUT |
| **SUPERCIAS** | supercias.gob.ec | Financial Statements, Companies |
| **SENAE** | aduana.gob.ec | Customs, ECUAPASS |
| **BCE** | bce.fin.ec | Banking, Check Standards |

---

## 1. SRI (SERVICIO DE RENTAS INTERNAS) - 2026

### 1.1 IVA (Value Added Tax)
| Rate | Code | Description | Effective |
|:-----|:-----|:------------|:----------|
| **15%** | 4 | Standard Rate | Jan 2026 |
| **5%** | 5 | Construction Materials | Jan 2026 |
| **0%** | 0 | Basic Goods, Exports | Ongoing |
| **N/A** | 6 | No Objeto de Impuesto | Government Services |
| **N/A** | 7 | Exento | Healthcare, Education |

**Source**: SRI Official Gazette, December 26, 2025

### 1.2 Electronic Invoicing 2026 Changes
| Requirement | Old Rule | New Rule (Jan 2026) |
|:------------|:---------|:--------------------|
| **Transmission** | 72 hours | **IMMEDIATE (Real-time)** |
| **CF Annulment** | Allowed | **PROHIBITED** |
| **Invoice Annulment** | Any time | **7 days max** |
| **Recipient Acceptance** | Not required | **5 business days** |

**Source**: Resolution NAC-DGERCGC25-00000017

### 1.3 Ficha Técnica Versions
| Version | Date | Status |
|:--------|:-----|:-------|
| 2.26 | March 2024 | Production |
| 2.28 | June 2024 | Gran Contribuyente |
| 2.32 | Oct 2025 | Anexo 25 — commercial transport operators |
| 2.33 | 13 Jul 2026 | Anexo 25 — mandatory `placa` field; Table 33 |
| **2.34** | **27 Jul 2026** | **LATEST** — Anexo 26, software provider RUC |

### 1.4 Document Types (codDoc)
| Code | Document | XML Required |
|:-----|:---------|:-------------|
| 01 | Factura | Yes |
| 03 | Liquidación de Compra | Yes |
| 04 | Nota de Crédito | Yes |
| 05 | Nota de Débito | Yes |
| 06 | Guía de Remisión | Yes |
| 07 | Comprobante de Retención | Yes |

### 1.5 Withholding Codes (IR)
| Code | Rate | Concept |
|:-----|:-----|:--------|
| 303 | 10% | Honorarios Profesionales |
| 304 | 8% | Servicios Predomina Intelecto |
| 307 | 2% | Servicios Mano Obra |
| 308 | 2% | Servicios Entre Sociedades |
| 312 | 1% | Bienes Muebles |
| 320 | 1.75% | Arrendamiento Inmuebles |
| 323 | 2% | Rendimientos Financieros |

### 1.6 IVA Withholding Rates
| Code | Rate | When |
|:-----|:-----|:-----|
| 721 | 10% | Bienes |
| 723 | 20% | Servicios |
| 725 | 30% | Bienes (CE) |
| 727 | 70% | Servicios (CE) |
| 729 | 100% | Liquidación Compra |
| 731 | 100% | Profesionales |

### 1.7 Consumidor Final Rules
| Rule | Value |
|:-----|:------|
| Maximum per invoice | **$50 USD** |
| RUC | 9999999999999 |
| ID Type Code | 07 |
| Can be annulled? | **NO (2026)** |

---

## 2. IESS (SOCIAL SECURITY) - 2026

### 2.1 Contribution Rates
| Contribution | Employee | Employer |
|:-------------|:---------|:---------|
| **Aporte Personal** | **9.45%** | - |
| **Aporte Patronal** | - | **11.15%** |
| **SECAP** | - | 0.5% |
| **IECE** | - | 0.5% |
| **Total Employee** | **9.45%** | - |
| **Total Employer** | - | **12.15%** |

**Contribution Ceiling**: 25 × SBU = $12,050/month

### 2.2 Fondos de Reserva
| Parameter | Value |
|:----------|:------|
| Rate | **8.33%** |
| Eligibility | After 13 months continuous |
| Payment | Monthly via IESS or retained |
| Default | Monthly through IESS |

---

## 3. MINISTERIO DEL TRABAJO - 2026

### 3.1 SBU (Salario Básico Unificado)
| Year | SBU | Source |
|:-----|:----|:-------|
| 2025 | $470 | Reference |
| **2026** | **$482** | Acuerdo MDT-2025-195 |

**Hourly Rate**: $482 ÷ 240 = **$2.01**

### 3.2 Décimo Tercero (13th Salary)
| Attribute | Value |
|:----------|:------|
| Calculation | Total earnings / 12 |
| Period | Dec 1 - Nov 30 |
| Payment Date | **Before Dec 24** |
| Mensualización Request | Before Jan 15 |

### 3.3 Décimo Cuarto (14th Salary)
| Attribute | Value |
|:----------|:------|
| Amount | **1 SBU = $482** |
| Mensualizado | $40.17/month |
| Costa/Galápagos | **Before Mar 15** |
| Sierra/Amazonía | **Before Aug 15** |

### 3.4 Utilidades (Profit Sharing)
| Component | Rate | Distribution |
|:----------|:-----|:-------------|
| Individual | 10% | By days worked |
| Family | 5% | By dependents |
| **Total** | **15%** | Net profit |
| Payment Deadline | **April 15** |
| Max per Employee | 24 × SBU = $11,568 |

### 3.5 SUT System 2026 Changes
| Change | Description |
|:-------|:------------|
| Contract Registration | Extended to **30 days** |
| Document Custody | Employer responsibility (May 2026) |
| Digital Validation | Hash code required |

### 3.6 Horas Extras
| Type | Recargo | Rate 2026 |
|:-----|:--------|:----------|
| Suplementaria | +50% | $3.01/hr |
| Extraordinaria | +100% | $4.02/hr |
| Nocturna | +25% | $2.51/hr |

### 3.7 Vacaciones
| Attribute | Value |
|:----------|:------|
| Annual Days | 15 working days |
| After 5 Years | +1 day/year (max 30) |
| Minimum Consecutive | 6 days |

---

## 4. SUPERINTENDENCIA DE COMPAÑÍAS - 2026

### 4.1 Financial Statement Deadlines
| Obligation | Deadline |
|:-----------|:---------|
| Annual Statements | **April 30** (by RUC digit) |
| Form 101 (SRI) | Include with filing |
| Balance General | Required |
| Estado de Resultados | Required |

### 4.2 Reports Required
| Report | Frequency |
|:-------|:----------|
| Estado de Situación Financiera | Annual |
| Estado de Resultados Integral | Annual |
| Estado de Flujos de Efectivo | Annual |
| Estado de Cambios Patrimonio | Annual |
| Notas Explicativas | Annual |

### 4.3 Accounting Standards
- **NIIF** (Full IFRS) for large companies
- **NIIF PYMES** for SMEs

---

## 5. SENAE (CUSTOMS) - 2026

### 5.1 Import Taxes
| Tax | Rate | Base |
|:----|:-----|:-----|
| **AD VALOREM** | 0-40% | CIF |
| **FODINFA** | 0.5% | CIF |
| **ISD** | 5% | Payment abroad |
| **IVA Import** | 15% | CIF + duties |

### 5.2 Note on Tariffs
> All tariffs are defined in the Arancel Nacional (HS codes).
> Check official SENAE portal for current rates.

### 5.3 Systems
| System | Purpose |
|:-------|:--------|
| **ECUAPASS** | All customs declarations |
| **DAU** | Import/Export declaration |
| **VUE** | Ventanilla Única |

---

## 6. REGULATORY CALENDAR 2026

| Date | Obligation | Entity |
|:-----|:-----------|:-------|
| Jan 15 | Décimo mensualización request | Min. Trabajo |

| **Mar 15** | Décimo 14 Costa/Galápagos | Min. Trabajo |
| **Apr 15** | Utilidades payment | Min. Trabajo |
| **Apr 30** | Supercias statements | SUPERCIAS |
| **Aug 15** | Décimo 14 Sierra/Amazonía | Min. Trabajo |
| **Dec 24** | Décimo 13 payment | Min. Trabajo |

---

## 7. AGENT IMPLEMENTATION NOTES

### Required Validations
1. RUC: 13 digits, Mod 11 check
2. Cédula: 10 digits, Mod 10 check
3. Access Key: 49 digits, Mod 11 check
4. Real-time SRI transmission
5. 5-day withholding rule
6. $50 CF limit enforcement
7. CF invoice cannot be annulled

### Critical Business Rules
```python
# Consumidor Final Check
CF_LIMIT = 50.00  # USD
CF_RUC = "9999999999999"

# Withholding 5-Day Rule
MAX_WITHHOLDING_DAYS = 5

# IESS Ceiling
IESS_CEILING = SBU * 25  # $12,050

# SBU 2026
SBU_2026 = 482.00
```

---

**Document Classification**: Agent Knowledge Base
**Update Frequency**: Annual or on regulatory change
