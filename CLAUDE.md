# CLAUDE.md - Memoria del Proyecto

## Descripción General

Sistema Django para consultas de **Listas Restrictivas LAFT** (Lavado de Activos y Financiamiento del Terrorismo). Permite a empresas verificar clientes/proveedores contra listas restrictivas nacionales e internacionales mediante conexión a la API externa **ConsultaListasPeps**.

**Dominio de producción:** `comertex.vadomconsultas.com`

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| Framework | Django 5.2.7 |
| Base de Datos | PostgreSQL |
| Almacenamiento | AWS S3 (bucket: `vadomdata`) |
| Generación PDF | WeasyPrint |
| Config | python-decouple + python-dotenv |
| HTTP Client | requests |

---

## Estructura del Proyecto

```
comertex_listas/
├── gestor_listas/          # Proyecto principal Django
│   ├── settings.py         # Configuración (S3, DB, API credentials)
│   ├── urls.py             # URLs raíz
│   └── wsgi.py / asgi.py
│
├── consultas/              # APP PRINCIPAL - Motor de búsquedas
│   ├── models.py           # Busqueda, Resultado
│   ├── services.py         # Conexión API ConsultaListasPeps
│   ├── views.py            # dashboard, pagina_busqueda, historial, PDF
│   ├── forms.py            # BusquedaForm
│   └── templates/consultas/
│       ├── base.html
│       ├── dashboard.html
│       ├── pagina_busqueda.html
│       ├── historial.html
│       ├── detalle_busqueda.html
│       └── reporte_pdf.html
│
├── usuarios/               # Autenticación
│   ├── models.py           # Usuario (extiende AbstractUser)
│   └── templates/usuarios/login.html
│
├── empresas/               # Multi-tenancy
│   └── models.py           # Empresa
│
├── cargas_masivas/         # Consultas en lote (Excel → PDF)
│   ├── models.py           # LoteConsultaMasiva
│   ├── views.py            # ListarLotes, SubirLote, descargar_plantilla
│   └── templates/cargas_masivas/
│
├── core_admin/             # Panel superadministrador
│   ├── views.py            # Dashboard global, gestión lotes, reportes
│   ├── mixins.py           # SuperuserRequiredMixin
│   └── templates/core_admin/
│
└── DOCS/                   # Documentación del proveedor API
    └── WEB SERVICE CONSULTALISTASPEPS 2023 (3).pdf
```

---

## Apps y sus Responsabilidades

### 1. `consultas` - Motor Principal
**URLs base:** `/`

| Ruta | Vista | Función |
|------|-------|---------|
| `/` | `dashboard` | Panel KPIs con gráficos Chart.js |
| `/buscar/` | `pagina_busqueda` | Formulario de búsqueda (ID/Nombre) |
| `/historial/` | `historial_busquedas` | Lista búsquedas del usuario |
| `/historial/<id>/` | `detalle_busqueda` | Detalle con resultados |
| `/historial/<id>/pdf/` | `generar_pdf_busqueda` | Genera PDF (WeasyPrint) |

**Modelos:**
- `Busqueda`: Registro de cada consulta (usuario, término, fecha, flags)
- `Resultado`: Cada coincidencia del API (mapea BlsWsConsultaPeps)

### 2. `usuarios` - Autenticación
**URLs base:** `/cuentas/`

| Ruta | Vista |
|------|-------|
| `/login/` | LoginView (Django auth) |
| `/logout/` | LogoutView |

**Modelo:** `Usuario` extiende `AbstractUser` con FK a `Empresa`

### 3. `empresas` - Multi-Empresa
**Modelo:** `Empresa` (nombre, creado_en)

### 4. `cargas_masivas` - Consultas en Lote
**URLs base:** `/cargas-masivas/`

| Ruta | Vista |
|------|-------|
| `/` | `ListarLotesView` - Lotes del cliente |
| `/subir/` | `SubirLoteView` - Subir Excel |
| `/plantilla/` | `descargar_plantilla` |

**Modelo:** `LoteConsultaMasiva`
- Estados: `PENDIENTE` / `PROCESADO`
- `archivo_subido`: Excel cliente → S3
- `archivo_resultado`: PDF resultado → S3

### 5. `core_admin` - Panel Superusuario
**URLs base:** `/core-admin/`

| Ruta | Vista |
|------|-------|
| `/` | `DashboardView` - KPIs globales |
| `/usuarios/` | `UsuarioListView` - Listar usuarios |
| `/usuarios/crear/` | `UsuarioCreateView` - Crear usuario |
| `/usuarios/editar/<pk>/` | `UsuarioUpdateView` - Editar usuario |
| `/usuarios/eliminar/<pk>/` | `UsuarioDeleteView` - Eliminar usuario |
| `/cargas-masivas/` | `LoteListView` - Todos los lotes |
| `/cargas-masivas/procesar/<pk>/` | `LoteProcessView` |
| `/reporte-mensual/` | `ReporteMensualView` |

**Formularios:** `UsuarioCreateForm`, `UsuarioEditForm`, `ProcesarLoteForm`

---

## API Externa - ConsultaListasPeps

### Configuración
```python
# settings.py
API_TOKEN = config('API_TOKEN')      # Token del .env
API_BASE_URL = config('API_BASE_URL') # URL base del .env
```

### URL del Servicio
```
https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/
```

### Métodos Implementados (consultas/services.py)

| Función | Endpoint API | Descripción |
|---------|--------------|-------------|
| `consultar_api_por_id(id)` | `PepsExactaID/{token}/{id}` | Búsqueda exacta por cédula |
| `consultar_api_por_nombre(nombre)` | `PepsNombre/{token}/{nombre}` | Búsqueda por nombre |
| `consultar_api_por_id_y_nombre(id, nombre)` | `PepsIDNombre/{token}/{id}/{nombre}` | Búsqueda combinada |

### Métodos Disponibles (no implementados aún)
- `PepsExactaIDSimple` - Respuesta reducida por ID exacto
- `PepsID` - Búsqueda aproximada de ID (±1 dígito)
- `PepsIDSimple` - Versión simple de PepsID

### Estructura de Respuesta API
```json
{
  "ExtraInfo": "",
  "MensajeError": "",
  "TotalResultados": 3,
  "Resultados": [
    {
      "Registro": 167217,
      "Codigo": "BLS1342216",
      "NombreCompleto": "LONDONO ECHEVERRY RODRIGO",
      "Primer_Nombre": "RODRIGO",
      "Segundo_Nombre": "",
      "Primer_Apellido": "LONDONO",
      "Segundo_Apellido": "ECHEVERRY",
      "Id": "79149126",
      "Tipo_Id": "CC",
      "Tipo_Lista": "BOLETIN FISCALIA",
      "Origen_Lista": "COLOMBIA",
      "Tipo_Persona": "INDIVIDUO",
      "Relacionado_Con": "Descripción del caso...",
      "Rol_o_Descripcion1": "Información adicional",
      "Rol_o_Descripcion2": "Info secundaria",
      "Aka": "TIMOLEON JIMENEZ",
      "Fuente": "HTTP://WWW.FISCALIA.GOV.CO",
      "Fecha_Update": "/Date(1500354000000-0500)/",
      "Estado": "INGRESA LISTA: 20160801",
      "LlaveImagen": "",
      "Boletin": true,
      "Restrictiva": false,
      "CoincidenciaID": 100,
      "CoincidenciaNombre": 0
    }
  ]
}
```

---

## Sistema de Clasificación de Riesgo

Implementado en `consultas/views.py:get_classification()`

| Clasificación | Criterio | Color |
|---------------|----------|-------|
| **Rojo** | Todo lo que no sea amarillo o PEP | Máximo riesgo |
| **Amarillo** | Filtraciones: Panama Papers, Paradise Papers, Bahamas Leaks, Offshore Leaks | Riesgo medio |
| **PEP's** | Palabras clave: PEP, GOBIERNO, MINISTERIO, SENADO, PRESIDENCIA, etc. | Personas políticamente expuestas |

---

## Relaciones de Modelos

```
Empresa (1) ←──── (N) Usuario (1) ←──── (N) Busqueda (1) ←──── (N) Resultado
    │
    └──── (N) LoteConsultaMasiva
```

---

## Variables de Entorno (.env)

```bash
# Django
SECRET_KEY=
DEBUG=False

# Base de datos PostgreSQL
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=5432

# API ConsultaListasPeps
API_TOKEN=8495-4545-4487
API_BASE_URL=https://www.consultalistaspeps.com/ClientArea/BLS_WS_BLS/ConsultaListasPeps.svc/rest/

# AWS S3
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
S3_CLIENT_PREFIX=comertex

# Email SMTP
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
ADMIN_EMAIL=

# Dominio
MI_DOMINIO=https://comertex.vadomconsultas.com
```

---

## Almacenamiento S3

**Bucket:** `vadomdata`
**Estructura:**
```
vadomdata/
└── {S3_CLIENT_PREFIX}/     # ej: comertex/
    ├── static/             # Archivos estáticos (CSS, JS, imágenes)
    └── media/              # Archivos subidos
        └── cargas_masivas/
            └── empresa_{id}/
                ├── subidas/    # Excel de clientes
                └── resultados/ # PDF procesados
```

---

## Comandos Útiles

```bash
# Activar entorno virtual (Windows)
cd comertex_listas
.\venv\Scripts\activate

# Migraciones
python manage.py makemigrations
python manage.py migrate

# Servidor desarrollo
python manage.py runserver

# Collectstatic (sube a S3)
python manage.py collectstatic

# Crear superusuario
python manage.py createsuperuser
```

---

## Notas de Desarrollo

### Autenticación
- `LOGIN_URL = '/cuentas/login/'`
- `LOGIN_REDIRECT_URL = '/'` (dashboard)
- `AUTH_USER_MODEL = 'usuarios.Usuario'`

### Seguridad en Vistas
- Todas las vistas de consultas usan `@login_required`
- Vistas de core_admin usan `SuperuserRequiredMixin`
- Filtros por `usuario=request.user` para aislar datos entre usuarios
- Filtros por `empresa=request.user.empresa` para aislar datos entre empresas

### Templates
- Base template: `consultas/templates/consultas/base.html`
- Gráficos: Chart.js
- PDF: `consultas/templates/consultas/reporte_pdf.html` (WeasyPrint)

### Restricciones del API (según documentación proveedor)
- No usar herramientas automatizadas con llamados periódicos/masivos
- Formato nombre recomendado: `[PA] [SA] [PN] [SN]` (ej: SANTOS CALDERON JUAN MANUEL)

---

## Archivos Clave para Modificaciones Comunes

| Tarea | Archivo(s) |
|-------|------------|
| Agregar método API | `consultas/services.py` |
| Modificar clasificación | `consultas/views.py` → `get_classification()` |
| Cambiar campos guardados | `consultas/models.py`, `consultas/views.py` |
| Dashboard cliente | `consultas/views.py` → `dashboard()`, `templates/consultas/dashboard.html` |
| Dashboard admin | `core_admin/views.py`, `templates/core_admin/dashboard.html` |
| Formulario búsqueda | `consultas/forms.py`, `templates/consultas/pagina_busqueda.html` |
| Autenticación | `usuarios/urls.py`, `templates/usuarios/login.html` |
| Configuración general | `gestor_listas/settings.py` |
