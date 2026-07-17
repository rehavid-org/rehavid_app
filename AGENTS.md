# AGENTS.md · Guía para agentes automatizados y_contribuidores

> Instrucciones operativas y convenciones que **TODO commit**
> (humano, agente o hook pre-commit) debe respetar en este repositorio.
> Si un agente IA edits código acá, leer este archivo es **obligatorio** antes de largo.

## Qué es este repo

REHAVID Operaciones — plataforma Django 6 de gestión logística/ergonomía de Rehavid S.A.S.
Migración del prototipo FastAPI + HTML monolítico (`../rehavid/`) a una app Django modular.
Documentación de contexto completo: `CLAUDE.md` (mapa operativo),
`docs/ARQUITECTURA.md` (mapa exhaustivo de la app), `ESTADO_MIGRACION.md`
(fase actual y cómo levantar todo), `docs/DESPLIEGUE_AZURE.md` (infra en producción).

## Stack

- Python 3.14 con **uv** (lockfile en `uv.lock`).
- Django 6 + DRF + allauth (login por **email**; SSO Microsoft/Entra via env `AZURE_SSO_*`).
- PostgreSQL 16, Redis 7, Celery 5.5 (+beat), Mailpit (local), Mailgun (prod opcional).
- Frontend: templates Django + `static/css/rehavid.css` (tokens de la marca) + Bootstrap 5
  (solo modales/grid) + ECharts 5.5 (dashboard/predictivo). Layout: `templates/layouts/app.html`.
- Lint: `ruff` (line-length **119**, alineado a djLint). Tests: `pytest` + factories.
- Settings scaffold cookiecutter-django: `config/settings/{base,local,production,test}.py`.

## Comandos

```bash
uv sync --group dev                         # deps del host
uv run ruff check .                         # lint — TIENE que quedar limpio antes de commit
uv run pytest -q                            # 154 tests
uv run python manage.py migrate
uv run python manage.py seed_demo           # idempotente: datos reales del prototipo
uv run python manage.py runserver
docker compose -f docker-compose.local.yml up -d postgres redis mailpit   # servicios
```

## Convenciones de código (no negociables)

- **Códigos legibles por PK** en `save()` (ej. `R-001`, `SOL-001`, `PL-001`) — **NUNCA COUNT** (bug B6).
- Toda mutación de negocio pasa por `services.py` de su app (vistas delgadas), en
  `transaction.atomic`, con `select_for_update` donde haya concurrencia, registra auditoría
  y lanza `ReservaError`/`SolicitudError`/`AlertaError` con mensajes al usuario.
- Autorización **siempre** en servidor: `NivelRequeridoMixin`, `ModuloRequeridoMixin`,
  `nivel_requerido` (decorador), `require_nivel(n)` (factory DRF). Regla: `user.nivel <= N`.
- Fechas: `timezone.localdate()` (TZ `America/Bogota`) — **nunca hardcodeadas** (bug B9).
- Templates de módulo extienden `layouts/app.html` y setean `modulo_activo` en el contexto.
- Acciones destructivas/mutaciones desde UI = modales Bootstrap con POST + CSRF
  (patrón `js-accion` / `data-url` — ver `reservas/lista.html`).
- **Los tests e2e de fases 6-7 están pospuestos** a Fase 8 por decisión del usuario
  (los de Fase 5 sí existen: `solicitudes/tests/test_views.py`).

## Estructura del repo

- `rehavid_app/<app>/` — 10 apps de dominio (users, catalogo, equipos, paquetes, reservas,
  solicitudes, planes, alertas, predictivo, analitica, auditoria). Cada una con `models`,
  `views`, `services`, `urls`, `tests`.
- `config/settings/{base,local,production,test}.py` — settings.
- `compose/{local,production,vm}/` — Dockerfiles y scripts por ambiente.
- `docker-compose.{local,production,vm}.yml` — compose por ambiente.
- `.github/workflows/{ci,deploy}.yml` — CI/CD.
- `seed_data/` — datos reales del prototipo (cargados por `seed_demo`).
- `docs/` — guía de arquitectura (`ARQUITECTURA.md`), despliegue (`DESPLIEGUE_AZURE.md`),
  guía del cliente (`guia-despliegue-azure.html`).
- `scripts/` — scripts de ops (ej. `deploy-vm.sh`).
- `.envs/.{local,production_example,production}/` — envs. **`.envs/.production/` está
  git-ignored** (contiene secrets reales de la VM).

## Producción (single Azure VM)

Topología vigente: **una VM** (`rehavid-vm`, Ubuntu 24.04 LTS, `eastus`) corre todo
(Caddy + Django + Celery + Postgres + Redis) vía `docker-compose.vm.yml`. Detalles en
`docs/ARQUITECTURA.md` sección 7 y `docs/DESPLIEGUE_AZURE.md`. URLs:
- Hoy (DNS temporal gratis): `https://rehavid.20-119-43-198.nip.io/`
- Definitiva (cuando el cliente apunte el dominio): `https://operaciones.rehavid.com.co/`

## CI/CD

- **`ci.yml`**: cada PR/push a `main` → ruff (via pre-commit, non-blocking) + pytest contra
  postgres:16.
- **`deploy.yml`**: push a `main` (o manual) → test → rsync a VM → `deploy-vm.sh` → health.
  Secretos en `rehavid-org/rehavid_app`: `VM_SSH_KEY`, `VM_HOST`, `VM_USER`.
  **`.envs/.production/` en la VM nunca lo pisa el workflow** (protegido por `--filter`).

## Reglas de commit

- **Conventional commits** en español o inglés, según el tono del file modificado (ver
  `git log` para ejemplos).
- **NUNCA** agregar "Co-Authored-By" ni atribución a AI en mensajes de commit.
- **NUNCA** comitear `.envs/.production/`, `~/.ssh/rehavid-vm-key`, ni ningún secret.
- Antes de commit: `uv run ruff check .` debe quedar **limpio** (line-length 119).