# Estado de la migración · 2026-07-13

Bitácora de avance contra `PLAN_MIGRACION.md`. **Retomar por "PRÓXIMO PASO" abajo.**

## ✅ Fase 0 · Fundaciones — COMPLETA
- Celery 5.5.3 + django-celery-beat + openpyxl agregados a `pyproject.toml`; `uv sync --group dev` corrido (`uv.lock` actualizado).
- `TIME_ZONE=America/Bogota`, `LANGUAGE_CODE=es-co`, bloque completo de settings Celery en `base.py`; eager en `local.py`/`test.py`; `config/__init__.py` importa `celery_app` (B18 resuelto).
- Docker local completo: `docker-compose.local.yml` (django, postgres:16, redis, celeryworker, celerybeat, mailpit), `compose/local/django/Dockerfile` (uv, wait-for-it), scripts `start`/`start-celeryworker`/`start-celerybeat`/`entrypoint`, `compose/local/postgres/` con backup/restore.
- `.envs/.local/.django` con REDIS_URL/CELERY/EMAIL mailpit.
- **Verificado**: postgres+redis+mailpit corren en Docker; `migrate` aplicó todo. (El build de la imagen django NO se ha probado aún.)

## ✅ Fase 1 · Modelos, admin y seed — COMPLETA
- 10 apps creadas y registradas (ver tabla en `CLAUDE.md`). Migraciones `0001` generadas y aplicadas contra Postgres.
- `User` extendido (nivel/empresa/rol_descriptivo/modulos_permitidos/permisos_extra) + `MENU_BY_LEVEL`; migración `users/0002`.
- Admin registrado para todos los modelos (auditoría de solo lectura).
- `seed_demo` (en `catalogo/management/commands/`) carga TODO desde `seed_data/*.json`. **Verificado idempotente** (2 corridas): 9 servicios, 14 usuarios, 10 equipos, 5 paquetes, 57 reservas, 7 solicitudes, 9 planes, 3 canales. Usuarios nivel 1 quedan `is_staff+is_superuser`; emails marcados verificados (allauth).

## ✅ Fase 2 · Autenticación y permisos — COMPLETA
- Login por email (`ACCOUNT_LOGIN_METHODS={"email"}`). **Verificado**: login jhon.orrego OK (302 a `/users/~redirect/`), usuario inactivo → `/accounts/inactive/`.
- Provider `microsoft` en settings con env `AZURE_SSO_CLIENT_ID/SECRET/TENANT_ID` + `EMAIL_AUTHENTICATION` (auto-vincula por email). Sin credenciales reales aún.
- `users/permissions.py`: decorador `nivel_requerido`, `NivelRequeridoMixin`, `ModuloRequeridoMixin`, factory DRF `require_nivel`. 14 tests pasando (`users/tests/test_permissions.py`).
- Pendiente menor: tests de matriz vista×nivel se escriben cuando existan las vistas (Fase 4/5).

## ✅ Fase 3 · Lógica de negocio core — COMPLETA
- `reservas/services.py`: puerto fiel de R002-R009 + O08/O09/O18 con `transaction.atomic` + `select_for_update`, códigos por PK (B6), M2M completo de paquete (B8), +1 día por preparación pendiente, Tumeke siempre disponible, riesgo heurístico, `proxima_fecha_disponible`. Todo registra en auditoría (B12).
- `solicitudes/services.py`: crear (B4), editar, cancelar con regla 48h contra fecha del SERVICIO (B5, solo nivel 4; cancela reserva vinculada), observaciones, **`atender_solicitud` crea la Reserva vinculada (B2)**, `contar_pendientes` (O17).
- `auditoria/services.py`: `registrar()`.
- **38 tests pasando** (`pytest rehavid_app/reservas rehavid_app/solicitudes`), incluida concurrencia real con threads (2 reservas simultáneas al último equipo → una falla).

## ✅ Fase 4 · Vistas operación interna + API — COMPLETA
- **Layout**: `templates/layouts/app.html` (sidebar fijo morado #2A1788 por secciones, chip usuario, toasts) + `static/css/rehavid.css` con TODOS los tokens del manual v8 (rampa ink morada, chips de estados, KPI planas, escala del calendario). Menú por nivel: registro central `users/menu.py` (context processor `sidebar_menu`); módulos de fases 5-6 apuntan a `ModuloEnMigracionView` (placeholder gateado por módulo) para que la navegación y la matriz de permisos ya existan. Login rebrandeado (`allauth/layouts/entrance.html`, panel izquierdo brand-dark).
- **Home/redirect por nivel** (`users:redirect`): 1-2 → reservas, 3 → calendario, 4 → portal. `path("")` redirige ahí.
- **Reservas** (`reservas/views.py`, nivel ≤2): lista con filtros (q/servicio/ciudad/estado/rango) + paginación; **Nueva Reserva (B3)** servicio o paquete con preview de disponibilidad en vivo (fetch a la API); reprogramar/cancelar/retorno como modales POST (B1 — server-side). Reserva de paquete guarda `servicio = primer servicio del paquete` (mismo criterio de los tests de Fase 3).
- **Equipos** (nivel ≤3; mutaciones ≤2, baja solo 1): KPI O02, grid + tabla, tarjeta Tumeke (O07 — servicios `requiere_equipo_fisico=False`), ficha modal O04 vía `/api/equipos/{id}/ficha/`, alta canónica B7 (`EquipoCreateView`, registra auditoría).
- **Paquetes**: tarjetas tri-estado O09 (`estado_paquete()` en `paquetes/views.py`: disponible/parcial/agotado + próxima fecha estimada) + CRUD nivel ≤2 (B11/O20). Eliminar con reservas históricas ⇒ desactiva en vez de borrar.
- **Calendario** (`analitica/views.py::CalendarioView`, todos los niveles): 12 meses server-rendered, densidad por día (escala del manual), detalle por día vía `?dia=`, filtro por servicio.
- **API DRF** (`config/api_router.py`): `ReservaViewSet` (list/create ≤2 · `disponibilidad` GET ≤4 para O10 · cancelar/reprogramar/retorno POST ≤2), `EquipoViewSet` (list/ficha ≤3 · create/listo/mantenimiento ≤2 · baja 1), `PaqueteViewSet` (lectura+disponibilidad ≤3 · CRUD ≤2). Errores de negocio → 400 con `detail`.
- **Tests**: 137 en verde. Nuevos: `users/tests/test_matriz_acceso.py` (matriz vista×nivel + API) y `reservas/tests/test_views.py` (flujo crear→reprogramar→retorno→listo, cancelar libera, filtros). Smoke real contra seed: todas las vistas 200/403 correctos con jhon (n2), liliana (n3), monica (n4).
- **Lint**: `ruff check` limpio. `line-length = 119` (alineado a djLint) y per-file-ignores para tests en `pyproject.toml`.

## ✅ Fase 5 · Portal solicitante + bandeja — COMPLETA
- **Portal nivel 4** (`solicitudes/views.py` + `urls_portal.py`, reemplaza placeholders): inicio con KPIs y próximos servicios; equipos disponibles read-only con próxima fecha libre por categoría; **formulario de solicitud** (`portal:solicitar`): O16 accesorios dinámicos por servicio (JSON embebido + inputs `acc-<id>`), O19 profesional (perfil obligatorio), O10 preview de saturación (fetch a `/api/reservas/disponibilidad/`), fecha mínima hoy+7 validada en form y `min` del input (B4: `fecha_sugerida` persistida vía `services.crear_solicitud`).
- **Mis solicitudes**: tabla con accesorios/observaciones/reserva vinculada; modales editar (solo pendiente), cancelar (48h vía servicio B5; cancela la reserva ligada) y observación. Guard server-side: un nivel 4 solo opera sus propias solicitudes.
- **Bandeja del operador** (`solicitudes:bandeja`, nivel ≤2, módulo nuevo "bandeja" en MENU_BY_LEVEL 1-2): pendientes con urgencia >12h, filtro por estado, **Atender → `atender_solicitud` (B2)** con mensajes de error de stock (solicitud queda pendiente).
- **Badge O17**: `/api/solicitudes/badge/` (`SolicitudViewSet` ≤2, también list + atender por API) + polling de 60s en el layout (`data-badge="bandeja"`).
- 154 tests en verde (incluye e2e solicitud→reserva escrito antes de la instrucción de posponer tests). Smoke con seed: portal 200 con monica (n4), bandeja+badge 200 con jhon (n2).
- **Nota**: por pedido del usuario, de la Fase 6 en adelante se prioriza implementación; tests e2e quedan para el final (Fase 8).

## ✅ Fase 6 · Analítica/predictivo/alertas/planes/admin/Excel — COMPLETA
- **Analítica** (`analitica/services.py`): `kpis()` y `series_dashboard()` 100% desde BD (B15); **motor de 11 detectores** fiel a `MOTOR_RECOMENDACIONES.md` (`analizar()` tolera fallos por detector, ordena por severidad; con seed disparan 6: solicitudesPendientes S3, sesgoServicios, capacidadCiudad, evaluacionesMasivas, planesEnRiesgo, equiposCriticos). Vistas: **Brief** (KPIs + top findings + salidas/retornos próximos), **Dashboard** (filtros + ECharts 5.5: barras por servicio/ciudad/cliente en morado marca, evolución semanal, dona de estados con paleta validada con el validador de dataviz), **Recomendaciones** (cards con observación/interpretación/recomendación + **Convertir en plan** → `crear_plan_desde_finding`). Endpoints: `/api/analitica/dashboard/`, `/api/analitica/recomendaciones/` (nivel ≤2).
- **Predictivo** (B16): `predictivo/services.py` = mock heurístico del prototipo + cliente Azure ML (`AZURE_ML_ENABLED/ENDPOINT/KEY/DEPLOYMENT` en settings por env) con fallback automático; registra todo en `PrediccionRegistro`. Vista con gauge ECharts, factores estilo SHAP, diagrama corporal SVG e historial. API `POST /api/predictivo/score/`.
- **Alertas** (O21): `alertas/services.py` con los 4 detectores contra BD y fecha real (B9); envío **email real** (`send_mail`, verificado), WhatsApp/Teams stubs documentados que registran el intento; `AlertaEnviada` + auditoría. Config de canales en BD (B10) editable por nivel 1 desde la vista. Task `alertas.tasks.detectar_y_notificar` en `CELERY_BEAT_SCHEDULE` cada 4h.
- **Planes**: CRUD completo (B11) con barra avance-vs-esperado; API `PlanViewSet` (contrato GET/POST/PUT/DELETE /planes).
- **Admin usuarios** (nivel 1, B11/B13): lista con filtros, crear (UserCreationForm → Argon2), editar con **editor de módulos y permisos extra** (vacío = todos los del nivel), activar/desactivar (no a sí mismo), **ficha con actividad real de auditoría** (B12).
- **Auditoría**: vista global con filtros (usuario/módulo/texto/fechas) + export.
- **Excel openpyxl** (B14): helper `rehavid_app/xlsx.py` (estilo marca); export de reservas (respeta filtros, schema del modelo real), equipos, auditoría; **plantilla + import de equipos** validado todo-o-nada contra el modelo canónico (B7).
- Smoke con seed (ariel n1): 16 rutas en 200, KPIs cuadran (57 reservas), finding→plan crea PL-010, email de alerta enviado y registrado, stub whatsapp registrado. 154 tests + ruff limpio.

## 🔶 Fase 7 · Docker producción + Azure — CÓDIGO ESCRITO, VERIFICACIÓN PENDIENTE

### Hecho (commiteado, sin verificar en runtime)
- `compose/production/django/Dockerfile` multi-stage: builder uv (`--no-dev`) → runtime `python:3.14-slim-trixie`, usuario `django` no-root, HEALTHCHECK a `/health/`, gunicorn :5000. **Imagen construida OK: 263MB** (antes 641MB — el fix fue crear `.dockerignore`, faltaba y el `COPY . /app` metía `.venv` y `.git`).
- Scripts `compose/production/django/{entrypoint,start,celery/worker/start,celery/beat/start}`: entrypoint espera BD con psycopg (sin wait-for-it), start corre `migrate` + `collectstatic` + gunicorn.
- `docker-compose.production.yml` (staging local: django+postgres+redis+celeryworker+celerybeat) + plantillas `.envs/.production_example/` (los reales van en `.envs/.production/`, git-ignored).
- `config/views.py::health` → `/health/` con chequeo de BD (lo usan Docker y el probe de App Service).
- `config/settings/production.py`: ALLOWED_HOSTS default `operaciones.rehavid.com.co`; STORAGES condicional (con `DJANGO_AZURE_ACCOUNT_NAME` → Blob; sin ella → **whitenoise**, dependencia agregada, para staging local); Application Insights opcional por `APPLICATIONINSIGHTS_CONNECTION_STRING` (guard de import).
- `.github/workflows/deploy.yml`: tags `v*` → tests (postgres 16 en CI) → build+push a ACR → deploy App Service (django + worker/beat opcionales) → espera 200 de `/health/`.
- `docs/DESPLIEGUE_AZURE.md`: guía completa az CLI adaptada de la del prototipo (RG, ACR, PG Flexible, Redis, Blob, Key Vault, App Services, SSO Entra, dominio, App Insights, Azure ML).
- Fix también en `compose/local/django/Dockerfile`: `gcc` → `build-essential` (psycopg-c no compilaba: faltaba `assert.h`/libc6-dev).

### ⏳ PENDIENTE de la Fase 7 (retomar aquí)
1. **Liberar espacio en disco del Mac** (~1GB libre; el daemon de Docker se cayó con errores de I/O a mitad del staging). Reiniciar Docker Desktop y `docker builder prune -af` (son capas de build; no toca datos).
2. `docker compose -f docker-compose.production.yml up --build` → verificar `curl localhost:5000/health/` = `{"status": "ok"}`, login y estáticos (whitenoise). Los `.envs/.production/` locales de staging **ya están creados** con valores de prueba.
3. Verificar celeryworker/celerybeat arriba en ese compose.
4. Build de la imagen **local** (`docker compose -f docker-compose.local.yml build django`) y `up` completo full-docker (pendiente desde Fase 0; el fix de build-essential aún no se probó).
5. Al terminar: re-correr `pytest` (los 144 errores de la última corrida fueron por la caída de Docker/postgres por disco lleno, NO por código — la suite completa pasaba minutos antes con 154 tests).
6. (Cuando exista la infra real) cargar secrets en GitHub y probar el workflow deploy.yml contra Azure.

## ⏳ Fase 8 · Verificación integral — NO INICIADA
Checklist funcional completo en sección 5 de `PLAN_MIGRACION.md`. También pendiente: build de la imagen Docker local (`docker compose -f docker-compose.local.yml build django`) y `docker compose up` completo.

---

## Cómo levantar TODO localmente (nueva sesión)

> **Sobre el `.venv`**: es SOLO conveniencia de desarrollo en el host (IDE, pytest rápido,
> ruff). Las imágenes Docker instalan sus dependencias adentro con `uv sync --locked` y el
> `.dockerignore` garantiza que `.venv`/`.git` nunca entren a una imagen. Producción es
> 100% Docker.

### Modo A · Híbrido (el usado en las fases 0-6: rápido para desarrollar)

```bash
cd /Users/yesid/Desktop/Desarrollo/Personal/rehavid_app

# 1 · Si Docker Desktop no corre:  open -a Docker  (esperar al daemon)
docker compose -f docker-compose.local.yml up -d postgres redis mailpit

# 2 · Variables para correr manage.py/pytest desde el host:
source .envs/.local/.postgres
export DATABASE_URL="postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB"

# 3 · (solo primera vez o tras cambiar pyproject) dependencias del host:
uv sync --group dev

uv run python manage.py migrate
uv run python manage.py seed_demo        # idempotente · datos reales del prototipo
uv run pytest -q                         # 154 tests en verde (última corrida sana 2026-07-13)
uv run ruff check .                      # limpio
uv run python manage.py runserver        # → http://localhost:8000
```
Mailpit UI (emails locales): http://localhost:8025 · Postgres expuesto en :5432.

### Modo B · Full Docker (todo en contenedores)

```bash
docker compose -f docker-compose.local.yml up -d --build   # django+celery incluidos; migra solo
docker compose -f docker-compose.local.yml run --rm django python manage.py seed_demo
docker compose -f docker-compose.local.yml run --rm django pytest
# → http://localhost:8000
```
⚠ El build de la imagen local aún NO se ha verificado (ver pendientes Fase 7, punto 4).

### Staging de producción local (cuando se retome Fase 7)

```bash
# .envs/.production/.{django,postgres} ya existen con valores de staging (git-ignored)
docker compose -f docker-compose.production.yml up -d --build
curl http://localhost:5000/health/       # → {"status": "ok"}
```

### Usuarios del seed (login por EMAIL)

| Email | Password | Nivel |
|---|---|---|
| `ariel.ramirez@rehavid.com.co` | `13011976` | 1 · Admin Global |
| `jhon.orrego@rehavid.com.co` | `demo123` | 2 · Operador |
| `liliana.hernandez@rehavid.com.co` | `demo123` | 3 · Coordinadora |
| `monica.vargas@arlsura.com` | `demo123` | 4 · Solicitante |

Aterrizaje post-login por nivel: 1-2 → `/reservas/` · 3 → `/analitica/calendario/` · 4 → `/portal/`.

### Estado del entorno / advertencias vigentes (2026-07-13)

- **El disco del Mac está casi lleno (~1GB libre)** — Docker se cayó por esto a mitad del
  staging de producción. Antes de builds pesados: liberar espacio y/o `docker builder prune -af`.
- Los 144 errores de la última corrida de pytest fueron por esa caída de Docker/postgres,
  no por código (la suite completa estaba en verde minutos antes).
- `mypy` no se ha corrido nunca sobre el proyecto.
- Documentación de contexto completo: `CLAUDE.md` (mapa operativo), `docs/ARQUITECTURA.md`
  (mapa exhaustivo de la app), `docs/DESPLIEGUE_AZURE.md` (infra).
- **Próximo trabajo**: pendientes de Fase 7 (arriba) → luego Fase 8 (QA integral + tests
  e2e pospuestos por decisión del usuario durante las fases 6-7).
