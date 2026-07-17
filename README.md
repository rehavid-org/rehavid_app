# REHAVID Operaciones

Plataforma Django de gestión logística y ergonomía de **Rehavid S.A.S.** — ciclo completo
de reservas de equipos de medición biomecánica (Xsens, EMG, Tobii, …) despachados a
empresas cliente, con portal externo para solicitantes, inventario por serial, paquetes
multi-equipo, alertas logísticas, predictivo ML, dashboards y auditoría.

Migración del prototipo FastAPI + HTML monolítico a una app Django modular.

## Stack

- **Python 3.14** con [uv](https://docs.astral.sh/uv/) (lockfile `uv.lock`)
- **Django 6** + DRF + django-allauth (login por email; SSO Microsoft/Entra opcional)
- **PostgreSQL 16**, **Redis 7**, **Celery 5.5** (+beat)
- Frontend: templates Django + Bootstrap 5 (modales/grid) + ECharts 5.5
- Lint: `ruff` (line-length 119). Tests: `pytest` + factories
- Docker en todo el ciclo (local y producción)

## Estado

**En producción en single Azure VM** (Ubuntu 24.04 LTS, Standard_D2as_v7, eastus) con
Docker Compose (Caddy + Django + Celery + Postgres + Redis). CI/CD vía GitHub Actions
(push a `main` → tests → deploy).

- URL actual (DNS temporal): <https://rehavid.20-119-43-198.nip.io/>
- Dominio definitivo (pendiente DNS del cliente): `https://operaciones.rehavid.com.co/`

## Comandos básicos

```bash
# Infra local (postgres, redis, mailpit):
docker compose -f docker-compose.local.yml up -d postgres redis mailpit

# Dependencias del host:
uv sync --group dev

# Variables para correr desde el host:
source .envs/.local/.postgres
export DATABASE_URL="postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB"

# Migrar + sembrar datos demo:
uv run python manage.py migrate
uv run python manage.py seed_demo    # idempotente: 14 usuarios, 10 equipos, 57 reservas

# Tests y lint:
uv run pytest -q                     # 154 tests
uv run ruff check .                  # debe quedar limpio antes de commit

# Servidor de desarrollo:
uv run python manage.py runserver    # → http://localhost:8000
```

## Documentación

| Archivo | Contenido |
|---|---|
| `CLAUDE.md` | Mapa operativo (stack, apps, convenciones, comandos) |
| `docs/ARQUITECTURA.md` | Mapa exhaustivo de la aplicación (modelos, URLs, permisos, API) |
| `ESTADO_MIGRACION.md` | Bitácora de avance por fases (0-8) |
| `PLAN_MIGRACION.md` | Plan original con reglas de negocio y defectos B1-B18 |
| `docs/DESPLIEGUE_AZURE.md` | Infraestructura de producción (VM Azure + CI/CD) |
| `AGENTS.md` | Guía para agentes automatizados y contribuidores |
| `CHANGELOG.md` | Historial de versiones |

## Licencia

Ver archivo `LICENSE`.
