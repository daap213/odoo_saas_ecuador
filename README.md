# 🇪🇨 Localización Ecuador para Odoo 18

<div align="center">

[![License: LGPL-3](https://img.shields.io/badge/Licencia-LGPL--3-blue.svg)](https://www.gnu.org/licenses/lgpl-3.0)
[![Odoo Version](https://img.shields.io/badge/Odoo-18.0-purple.svg)](https://www.odoo.com)
[![SRI](https://img.shields.io/badge/SRI-2026%20Certificado-green.svg)](https://sri.gob.ec)
[![Python](https://img.shields.io/badge/Python-3.10+-yellow.svg)](https://python.org)

**Localización completa para Ecuador, 100% compatible con regulaciones SRI 2026**

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
| Emisión electrónica: Factura (01) y Comprobante de Retención (07) | ✅ |
| Emisión electrónica: NC (04), ND (05), Liquidación (03), Guía (06) | ❌ pendiente |
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
| Anulación máxima 7 días | ✅ Control automático |
| Facturas CF no anulables | ✅ Bloqueado por sistema |
| Regla 5 días retenciones | ✅ Validación automática |

### 👥 Nómina IESS 2026

| Concepto | Valor |
|----------|-------|
| SBU 2026 | **$482** |
| Aporte Personal | 9.45% |
| Aporte Patronal | 12.15% |
| Décimo Tercero | Antes del 24 Dic |
| Décimo Cuarto | 15 Mar / 15 Ago |
| Utilidades | 15% antes 15 Abr |

---

## 📦 Módulos (19 Total)

### Módulos Base (Obligatorios)

| Módulo | Descripción | Dependencias |
|--------|-------------|--------------|
| `l10n_ec_full` | Meta-módulo: instala toda la localización de una vez | todos los `l10n_ec_*` |
| `l10n_ec_base` | Plan de cuentas NEC, validación RUC/Cédula, SRI service | l10n_ec |
| `l10n_ec_edi` | Generación XML, firma XAdES-BES, clave de acceso | l10n_ec_base |
| `l10n_ec_sri` | Integración SOAP con SRI (pruebas/producción) | l10n_ec_edi |

### Módulos Contables

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_withholding` | Retenciones IR + IVA, regla 5 días |
| `l10n_ec_income_tax` | Impuesto a la renta, gastos personales |
| `l10n_ec_rimpe` | Régimen RIMPE emprendedores/populares |
| `l10n_ec_ice` | Impuesto Consumos Especiales |
| `l10n_ec_reports` | ATS, Formulario 104, reportes tributarios |

### Módulos HR/Nómina

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_hr_payroll` | IESS 9.45%/12.15%, Décimos, SBU $482 |
| `l10n_ec_vacation` | Libro de vacaciones, control días |
| `l10n_ec_sut` | Reportes MDT (Décimos, Utilidades) |
| `l10n_ec_loans` | Préstamos quirografarios/hipotecarios |

### Módulos Operativos

| Módulo | Descripción |
|--------|-------------|
| `l10n_ec_guia_remision` | Guía de Remisión electrónica |
| `l10n_ec_pos` | Facturación electrónica en POS |
| `l10n_ec_customs` | DAU, partidas arancelarias, FODINFA, ISD |
| `l10n_ec_quality` | Control calidad productos Ecuador |
| `l10n_ec_asset` | Activos fijos depreciación Ecuador |
| `l10n_ec_bank_transfer` | Transferencias bancarias Ecuador |
| `l10n_ec_portal` | Portal cliente/proveedor Ecuador |

---

## 🚀 Instalación

### Requisitos Previos

- **Odoo 18** Community o Enterprise
- **Python 3.10+**
- **PostgreSQL 15+**
- **Certificado digital SRI** (formato .p12)

### Instalación Rápida

```bash
# 1. Clonar repositorio
git clone https://github.com/somatechlat/odoo_saas_ecuador.git

# 2. Instalar dependencias Python
pip install -r requirements.txt

# 3. Copiar a directorio de addons de Odoo
cp -r l10n_ec_* /ruta/a/odoo/addons/

# 4. Reiniciar Odoo y actualizar lista de módulos
./odoo-bin -d mi_base_datos -u all

# 5. Instalar módulo base
# Desde Odoo: Aplicaciones > Buscar "Ecuador" > Instalar
```

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

**Contabilidad > Configuración > Ecuador SRI > Certificados**

1. Subir archivo .p12
2. Ingresar contraseña
3. Activar certificado

### 3. Ambiente SRI

**Configuración > Empresas > Ecuador SRI**

- **Pruebas**: `celcer.sri.gob.ec`
- **Producción**: `cel.sri.gob.ec`

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [📥 Instalación](docs/INSTALACION.md) | Guía paso a paso |
| [📖 Manual de Usuario](docs/MANUAL_USUARIO.md) | Uso completo del sistema |
| [🔧 Guía de Administración](docs/ADMINISTRACION.md) | Configuración avanzada |
| [📋 Referencia Regulatoria](docs/REGULACIONES_2026.md) | Leyes y tasas vigentes |

---

## 🏛️ Cumplimiento Regulatorio

| Entidad | Regulación | Estado |
|---------|------------|--------|
| **SRI** | Facturación Electrónica 2026 | ✅ Cumple |
| **SRI** | Resolución NAC-DGERCGC25-00000017 | ✅ Cumple |
| **IESS** | Aportes 2026 (9.45% / 12.15%) | ✅ Cumple |
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
