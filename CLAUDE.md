# CLAUDE.md · REHAVID Operaciones (Django)

Migración del prototipo FastAPI + HTML monolítico (`../rehavid`) a esta app Django.
**Lee `ESTADO_MIGRACION.md` primero**: fase actual, cómo levantar todo localmente y qué sigue.
Mapa exhaustivo de la aplicación (modelos, urls, permisos, API): `docs/ARQUITECTURA.md`.
Plan original con reglas de negocio y defectos B1-B18: `PLAN_MIGRACION.md`.

## Qué es

Plataforma de gestión de Rehavid S.A.S. (ergonomía/riesgo músculo-esquelético): reservas de
equipos de medición biomecánica (Xsens, EMG, Tobii, …) despachados a empresas cliente, con
portal externo para solicitantes, inventario por serial, paquetes multi-equipo, alertas
logísticas, predictivo ML, dashboards y auditoría. 4 niveles de usuario:
1 Admin Global · 2 Operador · 3 Coordinador · 4 Solicitante (regla: nivel <= N da acceso).

**Fases 0-6 completas y commiteadas. Fase 7 (Docker prod + Azure) escrita, verificación
pendiente** — ver "PENDIENTE de la Fase 7" en `ESTADO_MIGRACION.md`.

## Stack

- Django 6.0 + DRF + allauth (login por **email**; SSO Microsoft por env `AZURE_SSO_*`)
- PostgreSQL 16, Redis, Celery (+beat), Mailpit — vía `docker-compose.local.yml`
- Python 3.14 con **uv**. El `.venv` del repo es SOLO para desarrollo en el host
  (IDE/pytest/ruff); las imágenes Docker instalan lo suyo adentro (`.dockerignore` lo garantiza).
- Scaffold cookiecutter-django: settings en `config/settings/{base,local,production,test}.py`
- Frontend: templates Django + `static/css/rehavid.css` (tokens del manual de identidad v8:
  morado `#4025CE`, verde `#02E577`, Outfit, look editorial plano) + Bootstrap 5 (solo modales/grid)
  + ECharts 5.5 (dashboard/predictivo). Layout base: `templates/layouts/app.html` (sidebar por nivel).

## Comandos clave (detalle completo en ESTADO_MIGRACION.md)

```bash
# Infra local:
docker compose -f docker-compose.local.yml up -d postgres redis mailpit
# Host (híbrido):
source .envs/.local/.postgres
export DATABASE_URL="postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB"
uv run python manage.py migrate && uv run python manage.py seed_demo
uv run pytest -q          # 154 tests
uv run ruff check .       # config en pyproject: line-length 119, tests con ignores FBT/PLR2004/S106
uv run python manage.py runserver
```

## Estructura de dominio (apps en `rehavid_app/`)

| App | Contenido (todo implementado salvo lo marcado) |
|---|---|
| `users` | User extendido (`nivel`, `empresa`, `modulos_permitidos`, `permisos_extra`), `MENU_BY_LEVEL` (+ módulo `bandeja` niveles 1-2), `menu.py` (registro sidebar + context processor), `permissions.py` (mixins/decorador/`require_nivel` DRF), `admin_views.py`+`urls_admin.py` (módulo Administración nivel 1: CRUD usuarios, permisos, ficha con auditoría real), redirect post-login por nivel en `views.py` |
| `catalogo` | `Servicio` (Tumeke=`requiere_equipo_fisico=False`), `Ciudad`, `Empresa`, `AccesorioTipo`. Comando `seed_demo` |
| `equipos` | `Equipo` (7 estados, serial único) + `Accesorio`. Vistas: lista+KPI+ficha modal+alta B7, listo/mantenimiento (≤2), baja (nivel 1), export/plantilla/import Excel. API `EquipoViewSet` |
| `paquetes` | `Paquete` M2M servicios. Tarjetas tri-estado O09 + CRUD ≤2. API con `disponibilidad` |
| `reservas` | **`services.py` = TODA la lógica R002-R009** (con `select_for_update`). Vistas: lista con filtros+export, Nueva Reserva con preview vivo, reprogramar/cancelar/retorno por modales (≤2). API `ReservaViewSet` (+`disponibilidad` GET ≤4) |
| `solicitudes` | `services.py`: crear (B4), 48h (B5), **`atender_solicitud` crea la Reserva (B2)**, `contar_pendientes`. Vistas: portal nivel 4 (`urls_portal.py`: inicio/equipos/solicitar/mis-solicitudes) + bandeja operador (`urls.py`, ≤2) con Atender. API badge O17 |
| `planes` | `Plan` + CRUD completo + API `PlanViewSet` |
| `alertas` | `services.py`: 4 detectores + envío (email real, WhatsApp/Teams stubs) · `tasks.py` beat c/4h · vista con config de canales (nivel 1, B10) |
| `predictivo` | `services.py`: mock ↔ Azure ML (`AZURE_ML_ENABLED`, fallback auto) · vista gauge+factores+SVG corporal · API `/api/predictivo/score/` |
| `analitica` | `services.py`: `kpis()`/`series_dashboard()` desde BD (B15) + **motor 11 detectores** + `crear_plan_desde_finding` · vistas Brief/Dashboard(ECharts)/Recos/Calendario 12 meses · API dashboard/recomendaciones |
| `auditoria` | `EventoAuditoria` + `services.registrar()` (lo llaman todos los servicios) · vista con filtros + export (nivel 1) |

Compartido: `rehavid_app/xlsx.py` (helper openpyxl para exports con estilo de marca).

## Convenciones

- Códigos legibles (`R-001`, `SOL-001`, `PL-001`) generados del PK en `save()` — nunca COUNT (B6).
- Toda mutación de negocio pasa por `services.py` de su app (vistas delgadas), en
  `transaction.atomic`, registra auditoría y lanza `ReservaError`/`SolicitudError`/`AlertaError`
  con mensajes para el usuario (las vistas los muestran con `messages`).
- Autorización SIEMPRE en servidor: `NivelRequeridoMixin`/`ModuloRequeridoMixin`/`nivel_requerido`/
  `require_nivel(n)` (B1). Menú por nivel: `MENU_BY_LEVEL` + registro `users/menu.py`.
- Fechas: `timezone.localdate()` (TZ America/Bogota) — nunca quemadas (B9).
- Templates de módulo extienden `layouts/app.html` y setean `modulo_activo` en el contexto.
- Acciones destructivas/mutaciones desde UI = modales Bootstrap con POST + CSRF (patrón
  `js-accion`/`data-url` — ver `reservas/lista.html`).
- Tests: pytest + factories. Red de seguridad: `reservas/tests/test_services.py`,
  `solicitudes/tests/test_services.py`, matriz `users/tests/test_matriz_acceso.py`.
  **Los e2e de fases 6-7 están pospuestos a Fase 8 por decisión del usuario.**
- Lint: `uv run ruff check .` debe quedar limpio antes de commit (line-length 119).

## Datos y referencias

- `seed_data/*.json` — datos reales del prototipo (57 reservas, 14 usuarios, 10 equipos,
  5 paquetes, 7 solicitudes, 9 planes). `seed_demo` es idempotente.
- `seed_data/MOTOR_RECOMENDACIONES.md` — spec de los 11 detectores (ya portados).
- `seed_data/DESIGN_TOKENS.md` — manual de identidad (ya implementado en `rehavid.css`).
- `docs/ARQUITECTURA.md` — **mapa exhaustivo de la app** (leer para contexto profundo).
- `docs/DESPLIEGUE_AZURE.md` — guía de infra Azure + CI/CD.
- Código origen: `../rehavid/backend/app/` (FastAPI) y `../rehavid/frontend/rehavid_v13_produccion.html`.
- Skills en `.claude/skills/`: `django-expert` y `frontend-design` — úsalas en backend y UI.
