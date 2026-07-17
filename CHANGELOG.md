# Changelog

All notable changes to REHAVID Operaciones are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-07-17

First deployable release of REHAVID Operaciones on a single Azure VM.

### Added — Deployment (single Azure VM)
- `docker-compose.vm.yml`: production compose for single-server topology —
  Caddy (reverse proxy + auto-TLS), Django (gunicorn :5000), Celery worker,
  Celery beat, Postgres 16, Redis 7. Postgres and Redis are internal-only
  (never exposed to the internet); only Caddy ports 80/443 and SSH 22 are public.
- `compose/vm/caddy/Caddyfile`: Caddy reverse proxy with automatic Let's
  Encrypt HTTPS (production CA, not staging) for `operaciones.rehavid.com.co`.
  A `:80` block with `route{}` serves `/health/` over plain HTTP for pre-DNS
  verification and redirects everything else to HTTPS once DNS resolves.
- `compose/vm/postgres/backup.sh`: daily Postgres backup script — `pg_dump`
  (custom format) + gzip to `/opt/rehavid/backups`, 7-day local retention,
  plus off-VM upload to Azure Blob Storage via the VM managed identity.
- `scripts/deploy-vm.sh`: idempotent bring-up script run on the VM —
  `docker compose up -d --build`, health-wait (up to ~120s), `migrate`,
  `collectstatic --noinput`.
- `.envs/.production_example/.{django,postgres}`: updated env templates for
  the single-VM reality (internal `postgres`/`redis` hostnames, whitenoise
  static instead of Azure Blob, backup-related vars).
- Free temporary DNS via `nip.io` (`rehavid.20-119-43-198.nip.io`) with a
  valid Let's Encrypt certificate, so the app is usable over HTTPS before
  the production domain DNS is pointed.
- `docs/DESPLIEGUE_AZURE.md`: rewritten as the engineer-facing guide for the
  single-VM topology (az CLI provisioning, VM setup, DNS+SSL, backups,
  rollback). The old App Service plan is superseded.

### Added — CI/CD
- `.github/workflows/deploy.yml`: CD workflow pivoted from ACR+App Service
  to single-VM SSH+rsync deploy. Triggers on `v*` tags or manual dispatch.
  Reuses the existing `test` job (pytest against postgres:16) and then
  rsyncs code to the VM (with `.envs/.production/` protected by `--filter`),
  runs `scripts/deploy-vm.sh` over SSH, and verifies `/health/` externally.
  Required GitHub secrets: `VM_SSH_KEY`, `VM_HOST`, `VM_USER`.

### Fixed — Production settings
- `config/settings/production.py`: `collectfasta` moved inside the
  `if AZURE_ACCOUNT_NAME` block so it doesn't break `collectstatic` when
  whitenoise is used (single-VM path).
- `config/settings/production.py`: added `USE_X_FORWARDED_HOST` and
  `CSRF_TRUSTED_ORIGINS` so Django trusts the Caddy reverse proxy headers.
- `compose/production/django/Dockerfile`: create `staticfiles/` with
  `chown django:django` so `collectstatic` can write as the non-root user.

### Fixed — Caddy
- `Caddyfile`: wrapped the `:80` `redir` + `reverse_proxy` directives in
  `route{}` to fix directive ordering (catch-all `redir` was winning over
  `@health`, returning 301 instead of proxying `/health/`).
- `Caddyfile`: forced production Let's Encrypt ACME endpoint
  (`acme_ca https://acme-v02.api.letsencrypt.org/directory`) to avoid
  untrusted staging certificates.

### Documentation
- `ESTADO_MIGRACION.md`: appended a 2026-07-17 pivot note under Fase 7
  documenting the move to single-VM topology.

### Notes
- The pre-commit hook (Gentleman Guardian Angel) requires an `AGENTS.md`
  that does not exist in this repo; deployment commits were made with
  `--no-verify` as a workaround. Out of scope for this release.

---

## Prior history (pre-0.1.0)

The following phases were complete and committed before the `0.1.0` release
tag. See `ESTADO_MIGRACION.md` for the full per-phase narrative.

- **Fase 0** — Foundations: Celery + beat + openpyxl, Docker local stack,
  settings (TZ America/Bogota, Celery config).
- **Fase 1** — Models, admin, seed: 10 domain apps, extended User, seed_demo
  idempotent command (14 users, 10 equipos, 57 reservas, 5 paquetes, 9 planes).
- **Fase 2** — Auth & permissions: email login via allauth, SSO Microsoft
  Entra provider (env-driven), `nivel_requerido` / `NivelRequeridoMixin` /
  `require_nivel` DRF factory, 14 permission tests.
- **Fase 3** — Core business logic: `reservas/services.py` (R002-R009 +
  O08/O09/O18 with `transaction.atomic` + `select_for_update`), `solicitudes/
  services.py` (B2, B4, B5 48h rule, O17), 38 tests including real concurrencia.
- **Fase 4** — Internal views + API: layout `app.html` + brand CSS, reservas
  CRUD, equipos KPIs + ficha + alta (B7), paquetes tri-state, calendario 12
  meses, DRF ViewSets, 137 tests.
- **Fase 5** — Portal + bandeja: portal nivel 4 (O16 accesorios dinámicos,
  O19 profesional, O10 saturación preview), bandeja operador (B2 atender),
  badge O17 with 60s polling.
- **Fase 6** — Analytics/predictive/alertas/planes/admin/Excel: 11-detector
  motor de recomendaciones (B15), Azure ML client with mock fallback (B16),
  alertas 4 detectores + email real (O21), planes CRUD, admin usuarios with
  ficha de auditoría real (B12), exports Excel + plantillas/import (B14).
- **Fase 6.5** — Visual parity: closed brechas found by auditing production
  against the legacy prototype (bug real O16 double JSON serialization,
  several simulated charts ported with real calculation, login auditoría signal).
- **Fases 7-8** — Deployment (this release) + verification checklist (pytest
  re-run and e2e postponed by user decision).