# Guía de Instalación

## Requisitos Previos

### Sistema

- **Odoo 18** Community o Enterprise
- **Python 3.10+**
- **PostgreSQL 15+**

### Certificado Digital SRI

Debe obtener un certificado digital de un proveedor autorizado:
- Security Data
- ANF AC Ecuador
- Banco Central del Ecuador

## Dependencias Python

```bash
pip install zeep cryptography lxml requests
```

O usando el archivo de requisitos:

```bash
pip install -r requirements.txt
```

---

## Métodos de Instalación

### Método 1: Docker (Recomendado)

```bash
# Clonar repositorio
git clone https://github.com/somatechlat/odoo_saas_ecuador.git

# Agregar al docker-compose.yml
volumes:
  - ./odoo_saas_ecuador:/mnt/extra-addons

# Configurar odoo.conf
addons_path = /mnt/extra-addons,/mnt/addons

# Reiniciar contenedor
docker-compose restart odoo
```

### Método 2: Instalación desde Código Fuente

```bash
# Clonar al directorio de addons de Odoo
cd /ruta/a/odoo/addons
git clone https://github.com/somatechlat/odoo_saas_ecuador.git

# O copiar módulos individualmente
cp -r l10n_ec_* /ruta/a/odoo/addons/

# Actualizar configuración de Odoo
addons_path = /ruta/a/odoo/addons
```

### Método 3: Odoo.sh

1. Ir a configuración del proyecto en Odoo.sh
2. Agregar repositorio: `https://github.com/somatechlat/odoo_saas_ecuador.git`
3. Desplegar rama

---

## Orden de Instalación de Módulos

Instalar módulos en este orden:

1. **l10n_ec_base** (requerido primero)
2. **l10n_ec_edi** (facturación electrónica)
3. **l10n_ec_sri** (integración SRI)
4. **Otros módulos** según necesidad

```bash
# Vía línea de comandos
./odoo-bin -d su_base_datos -i l10n_ec_base,l10n_ec_edi,l10n_ec_sri
```

---

## Configuración Inicial

### 1. Configuración de Empresa

Ir a **Configuración > Empresas** y configurar:

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| RUC | 13 dígitos (validación automática) | 1791234567001 |
| Razón Social | Nombre registrado en SRI | Mi Empresa S.A. |
| Dirección | Dirección fiscal | Quito, Ecuador |

### 2. Cargar Certificado Digital

Ir a **Contabilidad > Configuración > Ecuador SRI > Certificados**:

1. Clic en **Crear**
2. Subir archivo `.p12`
3. Ingresar contraseña del certificado
4. Configurar fecha de vencimiento
5. Clic en **Activar**

### 3. Selección de Ambiente

Ir a **Configuración > Empresas > Ecuador SRI**:

| Ambiente | Uso | Servidor |
|----------|-----|----------|
| **Pruebas** | Desarrollo y testing | celcer.sri.gob.ec |
| **Producción** | Facturas reales | cel.sri.gob.ec |

### 4. Puntos de Emisión

Configurar en **Contabilidad > Configuración > Ecuador SRI > Puntos de Emisión**:

- Código establecimiento (001)
- Código punto emisión (001)
- Secuencias asignadas

---

## Verificación de Instalación

### Probar Conexión SRI

1. Crear una factura de prueba
2. Clic en botón **Enviar a SRI**
3. Verificar respuesta

### Respuestas Esperadas

| Estado | Significado |
|--------|-------------|
| ✅ **RECIBIDA** | Documento recibido, esperando autorización |
| ✅ **AUTORIZADO** | Autorizado exitosamente |
| ❌ **RECHAZADO** | Revisar mensaje de error |

---

## Solución de Problemas

### Errores de Certificado

| Error | Solución |
|-------|----------|
| Contraseña inválida | Verificar contraseña del .p12 |
| Certificado expirado | Renovar con proveedor autorizado |
| Certificado no activo | Verificar fecha de vencimiento |

### Errores de Conexión SRI

| Error | Solución |
|-------|----------|
| Tiempo de espera agotado | Verificar conexión a internet |
| Servicio no disponible | Mantenimiento SRI (intentar después) |
| RUC inválido | Verificar formato de RUC de empresa |

### Problemas Comunes

| Problema | Solución |
|----------|----------|
| Módulo no encontrado | Verificar que addons_path incluya el directorio |
| Error de dependencia | Instalar módulos en orden correcto |
| Paquetes Python faltantes | Ejecutar `pip install -r requirements.txt` |

---

## Soporte

| Canal | Contacto |
|-------|----------|
| GitHub Issues | https://github.com/somatechlat/odoo_saas_ecuador/issues |
| Email | soporte@somatech.dev |

---

**Licencia**: LGPL-3.0 | **Desarrollado por**: [Somatech.dev](https://somatech.dev)
