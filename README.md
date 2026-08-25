# 🇪🇨 Localización Ecuador para Odoo 19

<div align="center">

[![License: LGPL-3](https://img.shields.io/badge/Licencia-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-19.0-purple.svg)](https://www.odoo.com)
[![SRI](https://img.shields.io/badge/SRI-2026%20Certificado-green.svg)](https://sri.gob.ec)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://python.org)

**Localización para Ecuador alineada con las regulaciones SRI 2026**
*(alcance real de la emisión electrónica: ver la tabla de características)*

[Instalación](#-instalación) •
[Módulos](#-módulos) •
[Características](#-características) •
[Documentación](#-documentación) •
[Soporte](#-soporte)

</div>

---

## 🏢 Desarrollado por

<div align="center">

**[Somatech.dev](https://somatech.dev)**

*En colaboración con la Odoo Community Association (OCA)*

</div>

---

## ⚡ Características Principales

### 📄 Facturación Electrónica SRI

| Característica | Estado |
|----------------|--------|
| Transmisión en tiempo real (mandatorio 2026) | ✅ |
| Firma digital XAdES-BES (RSA-SHA1 + SHA-1, según Ficha §6.8) | ✅ |
| Emisión electrónica: los 6 comprobantes de la Tabla 3 (01, 03, 04, 05, 06, 07) | ✅ |
| Certificación contra el ambiente de pruebas del SRI | ⚠️ pendiente — requiere certificado acreditado |
| Generación RIDE PDF de la factura (Anexo 2, con código de barras) | ✅ |
| Consulta automática de autorización y reintento (`ir.cron`) | ✅ |
| Entrega del comprobante al receptor por correo (Ficha §4.7) | ✅ |
| Aviso de caducidad del certificado de firma | ✅ |
| Ficha Técnica v2.34 (julio 2026) | ⚠️ parcial — ver `docs/REVISION_REFERENCIAS_SRI.md` |
| Clave de acceso 49 dígitos (Módulo 11) | ✅ |

### 💰 Cumplimiento Tributario

| Regulación | Implementación |
|------------|----------------|
| IVA 15% (código 4) | ✅ Estándar 2026 |
| IVA 5% (código 5) | ✅ Construcción |
| Límite Consumidor Final $50 | ✅ Validación automática |
| Anulación hasta el día 7 del mes siguiente | ✅ Control automático |
| Facturas CF no anulables | ✅ Bloqueado por sistema |
| Retención no anterior a su factura sustento | ✅ Validación automática |

> Ninguno de estos valores está escrito en el código: se leen en runtime de
> `ir.config_parameter` (`l10n_ec.iva_rate`, `l10n_ec.consumidor_final_limit`,
> `l10n_ec.annulment_day_limit`) y del registro anual `l10n_ec.config`. Se ajustan
> sin tocar Python.
>
> **La regla de los 5 días hábiles para retenciones ya no aplica desde 2026** y por
> eso no se valida: sólo se comprueba que la fecha de la retención no sea anterior a
> la de la factura, que es lo que el SRI contrasta contra
> `<fechaEmisionDocSustento>`.

### 👥 Nómina IESS 2026

| Concepto | Valor |
|----------|-------|
| SBU 2026 | **$482** |
| Aporte Personal | 9.45% |
| Aporte Patronal (IESS) | 11.15% |
| Costo patronal total | 12.15% = 11.15% IESS + 0.5% SECAP + 0.5% IECE |
| Décimo Tercero | Antes del 24 Dic |
| Décimo Cuarto | 15 Mar / 15 Ago |
| Utilidades | 15% antes 15 Abr |

---

## 📦 Módulos (20 Total)

> ⚠️ **Este repo se apoya en el `l10n_ec` oficial de Odoo 19 Community** (autor
> TRESCLOUD); no lo reemplaza. De él salen el plan de cuentas `ec`, los tipos de
> documento LATAM, `account.journal.l10n_ec_entity` / `.l10n_ec_emission`
> (establecimiento y punto de emisión) y `account.tax.group.l10n_ec_type`.
> `l10n_ec_base` lo declara como dependencia explícita.
>
> **No renombre ningún módulo de este repo a `l10n_ec`**: el del núcleo gana siempre
> en el `addons_path` y el suyo quedaría inalcanzable. Por eso el meta-módulo se
> llama `l10n_ec_full` y la guía de remisión `l10n_ec_guia_remision`.

### Módulos Base (Obligatorios)

| Módulo | Descripción | Dependencias |
|--------|-------------|--------------|
| `l10n_ec_base` | Plan de cuentas NEC, validación RUC/Cédula, catálogos SRI, `l10n_ec.config` por año, calendario tributario | `l10n_ec` (oficial), `account`, `purchase_stock`, `l10n_latam_invoice_document` |
| `l10n_ec_edi` | Clave de acceso, firma XAdES-BES, modelo de certificado, cliente SOAP | `l10n_ec_base`, `account_edi`, `mail` |
| `l10n_ec_sri` | Generación XML, orquestación de envío, retenciones, RIDE, crons | `l10n_ec_edi` |

### Meta-módulo (opcional)

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_full` | Instalación de un clic: wizard de configuración de empresa (6 pasos) y plantillas de negocio. Arrastra medio ERP (`sale_management`, `purchase`, `stock`, `point_of_sale`, `mrp`, `fleet`, `hr*`…) más 11 módulos `l10n_ec_*`. **No incluye** `rimpe`, `ice`, `income_tax`, `vacation`, `sut`, `loans`, `bank_transfer` ni `portal`: ésos se instalan aparte. |

### Módulos Contables

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_withholding` | Asistente de retenciones IR + IVA sobre facturas de compra (crea `l10n_ec.retention`) |
| `l10n_ec_income_tax` | Tabla progresiva IR 2026 y rebaja por cargas familiares (Res. 00000043) |
| `l10n_ec_rimpe` | Régimen RIMPE emprendedores/populares |
| `l10n_ec_ice` | Impuesto Consumos Especiales |
| `l10n_ec_reports` | ATS (Anexo Transaccional Simplificado), Formularios 103 y 104 |

### Módulos HR/Nómina

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_hr_payroll` | IESS 9.45% personal / 11.15% patronal, Décimos, Utilidades, SBU $482, Formulario 107 y wizard de gastos personales |
| `l10n_ec_vacation` | Acumulación de vacaciones (15 días + bono por antigüedad) |
| `l10n_ec_sut` | TXT/XML para el Ministerio del Trabajo (Salarios en Línea) |
| `l10n_ec_loans` | Préstamos de la empresa y descuentos IESS (quirografarios/hipotecarios) |

### Módulos Operativos

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_guia_remision` | Guía de remisión electrónica (06): transportistas, vehículos, ruta y comprobante de sustento sobre `stock.picking` |
| `l10n_ec_pos` | Facturación electrónica en POS |
| `l10n_ec_customs` | DAU, partidas arancelarias, FODINFA, ISD |
| `l10n_ec_quality` | Control calidad productos Ecuador |
| `l10n_ec_asset` | Activos fijos depreciación Ecuador |
| `l10n_ec_bank_transfer` | Genera los TXT bancarios para pago masivo de nómina |
| `l10n_ec_portal` | Roles de pago y préstamos del empleado en el portal web |

---

## 🚀 Instalación

### Requisitos Previos

- **Odoo 19** Community o Enterprise (rama de trabajo del repo: `19.0`)
- **Python 3.10+**
- **PostgreSQL 15+**
- **Certificado digital SRI** (formato .p12)
- Dependencias Python: `zeep`, `cryptography`, `lxml`, `requests` (`requirements.txt`)

### Instalación Rápida

```bash
# 1. Clonar repositorio
git clone https://github.com/somatechlat/odoo_saas_ecuador.git

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Añadir el repo COMPLETO al addons_path (no copiar módulo por módulo:
#    se montan juntos y el orden del addons_path importa)
#    odoo.conf → addons_path = /ruta/a/odoo_saas_ecuador,/ruta/a/odoo/addons

# 4. Instalar en orden: base → edi → sri → el resto
./odoo-bin -c odoo.conf -d mi_base_datos \
  -i l10n_ec_base,l10n_ec_edi,l10n_ec_sri --stop-after-init

# 5. O bien, todo de una vez desde la interfaz:
# Aplicaciones > Buscar "Ecuador" > 🇪🇨 Ecuador - Localización Completa (l10n_ec_full)
```

Tras instalar `l10n_ec_full` se abre automáticamente el **wizard de configuración de
empresa** (6 pasos: datos de la empresa, ambiente SRI, certificado, plan de cuentas,
nómina y plantilla de negocio).

### Despliegue al servidor

```bash
sudo DB_NAME=<db> MODULES=l10n_ec_sri bash scripts/deploy_saas.sh
```

Hace `git reset --hard origin/19.0`, detecta si cada módulo está instalado para elegir
`-i` vs `-u`, y reinicia el servicio `odoo19`.

### Docker

```yaml
# docker-compose.yml
volumes:
  - ./odoo_saas_ecuador:/mnt/extra-addons

# odoo.conf
addons_path = /mnt/extra-addons,/mnt/addons
```

📖 Ver [Guía de Instalación Completa](docs/INSTALACION.md)

---

## ⚙️ Configuración

### 1. Datos de Empresa

**Configuración > Empresas > Su Empresa**

- RUC (13 dígitos)
- Razón Social
- Dirección fiscal

### 2. Certificado Digital

**Contabilidad > Configuración > Digital Signatures** (modelo `l10n_ec.certificate`)

1. Subir archivo .p12
2. Ingresar contraseña (visible sólo para `base.group_system`)
3. Pulsar **Validate & Activate**
4. Enlazarlo en la empresa: *Configuración > Empresas > pestaña **SRI Ecuador** >
   Certificado de Firma SRI*

Un `ir.cron` diario revisa la caducidad y avisa por el chatter.

### 3. Ambiente SRI y establecimiento

**Configuración > Empresas > pestaña “SRI Ecuador”**

- **Pruebas**: `celcer.sri.gob.ec`
- **Producción**: `cel.sri.gob.ec`

> Los campos *URL Recepción* y *URL Autorización* de la compañía son un **override
> manual** y ganan sobre el ambiente. Nacen vacíos a propósito: déjelos así salvo que
> el SRI publique un endpoint distinto.

Casi todo lo demás se configura en **Contabilidad > Configuración > Ajustes >
Ecuador — SRI**: RUC del proveedor de facturación (Anexo 26), límite de consumidor
final, día límite de anulación, auto-envío, forma de pago por defecto, tarifas de IVA
y los endpoints.

Además, cada diario de venta necesita su **establecimiento y punto de emisión**
(*Contabilidad > Configuración > Diarios*, campos `l10n_ec_entity` y
`l10n_ec_emission` que aporta el `l10n_ec` oficial). Sin ellos la emisión falla con
un error explícito: son parte de la clave de acceso y del cuerpo del comprobante.

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [📥 Instalación](docs/INSTALACION.md) | Guía paso a paso |
| [📖 Manual de Usuario](docs/MANUAL_USUARIO.md) | Uso completo del sistema |
| [📋 Cumplimiento Regulatorio](docs/CUMPLIMIENTO_REGULATORIO.md) | Leyes y tasas vigentes |
| [🔍 Revisión vs. Ficha Técnica 2.34](docs/REVISION_REFERENCIAS_SRI.md) | Qué está cubierto y qué falta del esquema offline |
| [📐 SRS del sistema](docs/srs/) | Plantillas de negocio, flujos HR/inventario, matriz de regulaciones |
| [📚 Base de conocimiento regulatorio 2026](l10n_ec_sri/docs/11_regulatory_knowledge_base/INDEX.md) | SRI, IESS, MDT, SUPERCIAS, SENAE |
| [🗺️ Mapeo Odoo ↔ XML SRI](l10n_ec_sri/docs/05_data_mapping/) | Campo a campo por tipo de comprobante |
| [🛠️ Guía para desarrolladores](CLAUDE.md) | Arquitectura, convenciones y deuda técnica |

---

## 🏛️ Cumplimiento Regulatorio

| Entidad | Regulación | Estado |
|---------|------------|--------|
| **SRI** | Facturación Electrónica 2026 | ✅ Cumple |
| **SRI** | Resolución NAC-DGERCGC25-00000017 | ✅ Cumple |
| **IESS** | Aportes 2026 (9.45% personal / 11.15% patronal + 1% SECAP-IECE) | ✅ Cumple |
| **Min. Trabajo** | SBU $482 (Acuerdo MDT-2025-195) | ✅ Cumple |
| **SENAE** | FODINFA 0.5%, IVA importación 15% | ✅ Cumple |
| **SUPERCIAS** | Estados financieros NIIF | ✅ Cumple |

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas!

1. Fork del repositorio
2. Crear rama: `git checkout -b feature/mi-mejora`
3. Commit: `git commit -m "Añade mi mejora"`
4. Push: `git push origin feature/mi-mejora`
5. Abrir Pull Request

📖 Ver [Guía de Contribución](CONTRIBUIR.md)

---

## 📄 Licencia

Este proyecto está licenciado bajo **LGPL-3.0** - ver archivo [LICENSE](LICENSE).

```
Copyright 2026 Somatech.dev
License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)
```

---

## 🆘 Soporte

| Canal | Contacto |
|-------|----------|
| 📧 Email | soporte@somatech.dev |
| 🌐 Web | [somatech.dev](https://somatech.dev) |
| 🐛 Issues | [GitHub Issues](https://github.com/somatechlat/odoo_saas_ecuador/issues) |

---

<div align="center">

**Hecho con ❤️ en Ecuador 🇪🇨**

[![GitHub stars](https://img.shields.io/github/stars/somatechlat/odoo_saas_ecuador?style=social)](https://github.com/somatechlat/odoo_saas_ecuador)

</div>
