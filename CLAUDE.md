# CLAUDE.md · REHAVID Operaciones (Django)

Migración del prototipo FastAPI + HTML monolítico (`../rehavid`) a esta app Django.
**Lee `ESTADO_MIGRACION.md` primero**: dice exactamente en qué fase va el trabajo y qué sigue.
El plan completo con reglas de negocio, defectos B1-B18 y checklist funcional está en `PLAN_MIGRACION.md`.

## Qué es

Plataforma de gestión de Rehavid S.A.S. (ergonomía/riesgo músculo-esquelético): reservas de
equipos de medición biomecánica (Xsens, EMG, Tobii, …) despachados a empresas cliente, con
portal externo para solicitantes, inventario por serial, paquetes multi-equipo, alertas
logísticas, predictivo ML, dashboards y auditoría. 4 niveles de usuario:
1 Admin Global · 2 Operador · 3 Coordinador · 4 Solicitante (regla: nivel <= N da acceso).

## Stack

- Django 6.0 + DRF + allauth (login por **email**; SSO Microsoft configurado por env `AZURE_SSO_*`)
- PostgreSQL 16, Redis, Celery (+beat), Mailpit — vía `docker-compose.local.yml`
- Python 3.14 gestionado con **uv** (`uv sync --group dev`, `uv run ...`)
- Scaffold cookiecutter-django: settings en `config/settings/{base,local,production,test}.py`

## Comandos clave

```bash
# Servicios de infraestructura (postgres/redis/mailpit ya corren en Docker):
docker compose -f docker-compose.local.yml up -d postgres redis mailpit

# Para manage.py/pytest fuera de Docker exporta DATABASE_URL:
source .envs/.local/.postgres
export DATABASE_URL="postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB"

uv run python manage.py migrate
uv run python manage.py seed_demo      # seed idempotente con los datos reales del prototipo
uv run pytest                          # suite completa
uv run python manage.py runserver
```

## Estructura de dominio (apps en `rehavid_app/`)

| App | Contenido |
|---|---|
| `users` | User extendido: `nivel`, `empresa`, `rol_descriptivo`, `modulos_permitidos`, `permisos_extra`. `users/permissions.py`: `nivel_requerido()`, `NivelRequeridoMixin`, `ModuloRequeridoMixin`, `require_nivel()` DRF |
| `catalogo` | `Servicio` (Tumeke = `requiere_equipo_fisico=False`), `Ciudad`, `Empresa`, `AccesorioTipo` (O16). Comando `seed_demo` |
| `equipos` | `Equipo` (7 estados, serial único, modelo canónico B7) + `Accesorio` |
| `paquetes` | `Paquete` con M2M `servicios_requeridos` |
| `reservas` | `Reserva` (M2M equipos, FK solicitud), `ConfirmacionRetorno`, `HistorialReserva`. **`services.py` = TODA la lógica R002-R009** (disponibilidad, crear/cancelar/reprogramar/retorno, listo, mantenimiento, baja) con `select_for_update` |
| `solicitudes` | `Solicitud` (B4 `fecha_sugerida`), `AccesorioSolicitado`, `Observacion`. `services.py`: crear/editar/cancelar (B5 regla 48h), **`atender_solicitud` crea la Reserva (B2)**, `contar_pendientes` (O17) |
| `planes` | `Plan` de acción (open/risk/done) |
| `alertas` | `ConfiguracionCanal` (B10), `AlertaEnviada`; detectores pendientes (Fase 6) |
| `predictivo` | `PrediccionRegistro`; servicio mock/Azure ML pendiente (Fase 6) |
| `analitica` | sin modelos; KPIs + motor de 11 recomendaciones pendiente (Fase 6) |
| `auditoria` | `EventoAuditoria` + `services.registrar()` — ya lo llaman todos los servicios de negocio |

## Convenciones

- Códigos legibles (`R-001`, `SOL-001`, `PL-001`) se generan del PK en `save()` — nunca COUNT (B6).
- Toda mutación de negocio pasa por `services.py` de su app (vistas delgadas), corre en
  `transaction.atomic` y registra auditoría. Los servicios lanzan `ReservaError`/`SolicitudError`
  con mensajes para el usuario.
- Autorización SIEMPRE en servidor con los mixins/permisos de `users/permissions.py` (corrige B1);
  el menú por nivel viene de `MENU_BY_LEVEL` en `users/models.py`.
- Fechas: `timezone.localdate()` (TZ America/Bogota) — nunca fechas quemadas (B9).
- Tests con pytest + factories (`rehavid_app/reservas/tests/factories.py`,
  `rehavid_app/users/tests/factories.py`). Los tests de reglas de negocio son la red de
  seguridad: `rehavid_app/reservas/tests/test_services.py` y
  `rehavid_app/solicitudes/tests/test_services.py`.
- Lint: `uv run ruff check .` (config estricta en pyproject; usa `# noqa: FBT003` en booleanos
  posicionales de tests).

## Datos y referencias

- `seed_data/*.json` — datos reales extraídos del prototipo (57 reservas, 14 usuarios `demo123`
  salvo ariel `13011976`, 10 equipos, 5 paquetes, 7 solicitudes, 9 planes, canales, permisos).
- `seed_data/MOTOR_RECOMENDACIONES.md` — spec exacta de los 11 detectores para Fase 6.
- `seed_data/DESIGN_TOKENS.md` — paleta Rehavid (morado `#4025CE`, verde `#02E577`, fuente
  Outfit) para las plantillas de Fase 4.
- Código origen: `../rehavid/backend/app/` (FastAPI) y
  `../rehavid/frontend/rehavid_v13_produccion.html` (7.814 líneas).
- Skills disponibles en `.agents/skills/`: `django-expert` y `frontend-design` — úsalas en
  el trabajo de backend y de UI respectivamente.
