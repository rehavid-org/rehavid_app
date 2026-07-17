# REHAVID Operaciones · Mapa de la aplicación

> Documento de contexto completo. Actualizado: 2026-07-17 (deploy single-VM + CI/CD en
> producción; fases 0-6 completas). Cómo levantar todo: `ESTADO_MIGRACION.md`;
> guía de infra: `docs/DESPLIEGUE_AZURE.md`.

## 1 · Dominio en una frase

Rehavid S.A.S. alquila/despacha **equipos de medición biomecánica** (Xsens, EMG, Tobii,
Dinamómetro, Lactómetro, Dron, GoPro + software Tumeke sin unidad física) a empresas
cliente (ARL SURA, JD TASS, …) para estudios ergonómicos. La app gestiona el ciclo:
**solicitud (portal externo) → atención del operador → reserva con asignación de equipos →
despacho → retorno → preparación/lavado → disponible de nuevo**, más analítica y alertas.

## 2 · Niveles y matriz de acceso

Regla: `user.nivel <= N` da acceso (nivel 1 es el más alto). `user.modulos` =
`modulos_permitidos` explícito o `MENU_BY_LEVEL[nivel]` (en `users/models.py`).

| Módulo (clave) | URL | 1 Admin | 2 Operador | 3 Coord. | 4 Solicitante |
|---|---|---|---|---|---|
| brief | `/analitica/brief/` | ✓ | ✓ | — | — |
| dashboard | `/analitica/dashboard/` | ✓ | ✓ | — | — |
| predictivo | `/predictivo/` | ✓ | ✓ | — | — |
| recos | `/analitica/recomendaciones/` | ✓ | ✓ | — | — |
| planes | `/planes/` (CRUD ≤2) | ✓ | ✓ | — | — |
| reservas | `/reservas/` (todo ≤2) | ✓ | ✓ | — | — |
| bandeja | `/solicitudes/bandeja/` (≤2) | ✓ | ✓ | — | — |
| equipos | `/equipos/` (lectura ≤3; mutación ≤2; **baja solo 1**) | ✓ | ✓ | ✓ | — |
| paquetes | `/paquetes/` (lectura ≤3; CRUD ≤2) | ✓ | ✓ | ✓ | — |
| calendario | `/analitica/calendario/` | ✓ | ✓ | ✓ | ✓ |
| alertas | `/alertas/` (canales solo 1) | ✓ | ✓ | — | — |
| admin | `/administracion/usuarios/` (solo 1) | ✓ | — | — | — |
| auditoria | `/auditoria/` (solo 1) | ✓ | — | — | — |
| portal / equipos-disp / solicitar / mis-solicitudes | `/portal/…` | — | — | — | ✓ |

Aterrizaje post-login (`users:redirect`): 1-2 → reservas · 3 → calendario · 4 → portal.
Permisos extra granulares (`permisos_extra`): `agregar_equipos`, `editar_inventario`,
`editar_usuarios` (definidos; el gating fino por permiso extra puede añadirse donde se requiera).

## 3 · Modelos por app (campos clave)

- **users.User**: AbstractUser + `name`, `nivel` (1-4), `empresa` FK, `rol_descriptivo`,
  `modulos_permitidos` (JSON, None=todos los del nivel), `permisos_extra` (JSON list).
- **catalogo**: `Servicio(nombre, requiere_equipo_fisico, activo)` — Tumeke tiene
  `requiere_equipo_fisico=False` (siempre disponible); `Ciudad`; `Empresa`;
  `AccesorioTipo(servicio, nombre, cantidad_default)` (O16).
- **equipos.Equipo**: `codigo` único (XS-01), `servicio` FK (categoría), `modelo`, `serial`
  único, `estado` (disponible/en_uso/en_preparacion/en_revision/en_mantenimiento/en_transito/
  de_baja), `ciudad_base`, `ultima_revision`, `proxima_mantencion`, `historial_uso`,
  `motivo_mantenimiento/baja`, `fecha_baja`. + `Accesorio(equipo, nombre, cantidad,
  requiere_lavado, consumible)`.
- **paquetes.Paquete**: `codigo` (PKG-01), `servicios_requeridos` M2M, `duracion_dias`, `activo`.
- **reservas.Reserva**: `codigo` (R-001, del PK), servicio/cliente/ciudad FKs, `personas`,
  `fecha_salida`, `fecha_retorno_esp`, `cancelada`+motivo, `reprogramada_desde`,
  `equipos` M2M (un equipo por categoría si es paquete), `paquete` FK null, `solicitud` FK
  null (B2), `riesgo` float. Propiedad `activa` = no cancelada y sin retorno.
  + `ConfirmacionRetorno` (OneToOne: estado_kit OK/INCOMPLETO/DAÑADO, requiere_preparacion,
  preparacion_completa) + `HistorialReserva` (acción/usuario/detalle por evento).
- **solicitudes.Solicitud**: `codigo` (SOL-001), solicitante/empresa/servicio/ciudad FKs,
  `personas`, `fecha_sugerida` (B4, obligatoria), `dias_estimados`, `estado`
  (pendiente/confirmada/finalizada/cancelada), operador, `fecha_confirmada`, campos de
  profesional O19 (`prof_*`), cancelación, `editada`. + `AccesorioSolicitado` + `Observacion`.
- **planes.Plan**: `codigo` (PL-001), area, titulo, responsable, vence, avance/esperado (%),
  estado open/risk/done.
- **alertas**: `ConfiguracionCanal(canal whatsapp/email/teams, activo, destino)` único por
  canal (B10) · `AlertaEnviada(tipo, canal, mensaje, destino, resultado, enviada_por)`.
- **predictivo.PrediccionRegistro**: entrada (servicio/ciudad/cliente/personas/sector/jornada),
  `score`, `modelo_version`, `es_simulacion`, `factores` JSON.
- **auditoria.EventoAuditoria**: usuario FK + copia desnormalizada email/nombre, `accion`,
  `modulo`, `detalle`, `timestamp`, `ip`.

## 4 · Servicios de negocio (la única vía de mutación)

### `reservas/services.py` (R002-R009, transaccional, `select_for_update`)
- `verificar_disponibilidad(servicio, salida, retorno, *, excluir_reservas, para_actualizar)`
  → `Disponibilidad(disponible, motivo, equipos_libres)`. Solapamiento
  `inicio <= r_fin && fin >= r_ini`; +1 día si el retorno dejó preparación pendiente;
  excluye estados bloqueados; Tumeke siempre disponible.
- `verificar_disponibilidad_paquete(...)` → dict con `detalle` por categoría (todas deben tener stock).
- `proxima_fecha_disponible(servicio, duracion)` — primera fecha con stock (horizonte 120 días).
- `crear_reserva(**kw)` — bloquea filas, asigna 1 equipo/categoría, equipos → en_uso,
  historial + auditoría. Riesgo heurístico `min(0.85, 0.18 + personas*0.04)`.
  Nota: una reserva de paquete guarda `servicio = primer servicio del paquete`.
- `cancelar_reserva` — libera equipos que ninguna otra reserva activa use.
- `reprogramar_reserva` — revalida excluyéndose a sí misma.
- `confirmar_retorno(estado_kit, notas, requiere_preparacion)` — equipos → en_preparacion o
  disponible, `historial_uso += 1`.
- `marcar_equipo_listo` — en_preparacion → disponible, actualiza `ultima_revision`, completa
  la ConfirmacionRetorno pendiente.
- `enviar_a_mantenimiento` · `dar_de_baja_equipo` (bloqueada con reservas activas, O18).

### `solicitudes/services.py`
- `crear_solicitud(**kw)` — persiste `fecha_sugerida` (B4) + accesorios + profesional.
- `puede_cancelar_48h` / `cancelar_solicitud` — 48h contra la **fecha programada del
  servicio** (reserva vinculada o fecha sugerida, B5); solo aplica a nivel 4 con confirmada;
  cancela también la reserva vinculada.
- `editar_solicitud` (solo pendientes) · `agregar_observacion`.
- **`atender_solicitud(solicitud, operador)` → Reserva** (B2): valida stock, crea la reserva
  vinculada y confirma, todo en una transacción (sin stock → revierte, queda pendiente).
- `contar_pendientes()` — badge O17.

### `analitica/services.py`
- `kpis(desde, hasta, servicio, ciudad)` y `series_dashboard(...)` — todo desde BD (B15).
- **Motor**: 11 detectores (`concentracion_ciudad`, `sesgo_servicios`, `riesgo_no_retorno`,
  `capacidad_ciudad`, `cancelaciones_alta`, `top_clientes`, `evaluaciones_masivas`,
  `planes_en_riesgo`, `solicitudes_pendientes`, `equipos_criticos`, `backlog_alto`) →
  `Finding(id, area, severidad 1-4, titulo, observacion, interpretacion, recomendacion,
  responsable_sugerido, plazo_dias, modulo, tag)`. `analizar()` tolera fallos y ordena por
  severidad. Umbrales exactos: `seed_data/MOTOR_RECOMENDACIONES.md`.
- `crear_plan_desde_finding(finding_id, usuario)` — finding→Plan (vence = hoy + plazo).

### `alertas/services.py`
- `detectar_alertas()` — 4 detectores: salidas ≤48h, retornos vencidos, mantenciones ≤14d,
  equipos en preparación.
- `enviar_alerta(tipo, canal, mensaje, usuario)` — email real (`send_mail`), whatsapp/teams
  stubs que registran el intento; siempre crea `AlertaEnviada` + auditoría.
- `detectar_y_notificar()` — usado por `alertas/tasks.py` (beat cada 4h, `CELERY_BEAT_SCHEDULE`).

### `predictivo/services.py`
- `obtener_prediccion(entrada, usuario)` — mock heurístico o Azure ML según
  `AZURE_ML_ENABLED` (fallback automático al mock si el endpoint falla); registra siempre
  en `PrediccionRegistro`.

### `auditoria/services.py`
- `registrar(usuario, accion, modulo, detalle, request=None)` — lo llaman TODOS los flujos.

## 5 · API (sesión Django, mismo dominio; router en `config/api_router.py`)

| Endpoint | Método(s) | Nivel | Nota |
|---|---|---|---|
| `/api/reservas/` | GET, POST | ≤2 | POST usa `crear_reserva`; errores negocio → 400 `{detail}` |
| `/api/reservas/disponibilidad/` | GET | ≤4 | preview vivo (Nueva Reserva y saturación O10 del portal); params `servicio|paquete, fecha_salida, fecha_retorno` |
| `/api/reservas/{id}/cancelar|reprogramar|retorno/` | POST | ≤2 | |
| `/api/equipos/` | GET (≤3), POST (≤2) | | |
| `/api/equipos/{id}/ficha/` | GET | ≤3 | O04: métricas + próxima reserva + accesorios |
| `/api/equipos/{id}/listo|mantenimiento/` | POST | ≤2 | |
| `/api/equipos/{id}/baja/` | POST | 1 | O18 |
| `/api/paquetes/` (+CRUD) | GET ≤3 / resto ≤2 | | destroy con reservas históricas ⇒ desactiva |
| `/api/paquetes/{id}/disponibilidad/` | GET | ≤3 | tri-estado |
| `/api/solicitudes/` | GET | ≤2 | filtro `?estado=` |
| `/api/solicitudes/badge/` | GET | ≤2 | `{pendientes}` · polling 60s del sidebar |
| `/api/solicitudes/{id}/atender/` | POST | ≤2 | B2 |
| `/api/planes/` (+CRUD) | todos | ≤2 | |
| `/api/analitica/dashboard/` | GET | ≤2 | `{kpis, series}` para ECharts |
| `/api/analitica/recomendaciones/` | GET | ≤2 | findings del motor |
| `/api/predictivo/score/` | POST | ≤2 | mock/Azure ML |
| `/health/` | GET | público | check de BD (Docker/App Service probe) |

Swagger: `/api/docs/` (solo admin). Los errores de negocio devuelven 400 con `{"detail": "..."}`.

## 6 · Frontend

- **Shell**: `templates/layouts/app.html` — sidebar fijo 232px `#2A1788` con secciones
  (Dirección/Operación/Sistema/Portal) armadas por el context processor
  `users.menu.sidebar_menu` según `user.modulos`; chip de usuario; toasts de `messages`;
  badge de bandeja con polling. Login: `templates/allauth/layouts/entrance.html` (panel marca).
- **Design system**: `static/css/rehavid.css` — SOLO morado/verde/blanco (manual v8):
  rampa de texto tintada (`--ink`…`--ink-6`), líneas lavanda, radios 2px, KPI planas con
  borde izquierdo de acento, chips por estado de equipo/reserva/solicitud, tarjetas
  tri-estado de paquetes, escala del calendario (`d1/d2/d3`), formularios `form-r`,
  botones `btn-r [primario|verde|peligro|mini]`.
- **Patrón de acciones**: botones `.js-accion` con `data-modal`/`data-url`/`data-codigo`
  llenan un modal Bootstrap único por tipo de acción; el form POSTea a la URL con CSRF.
- **Charts** (dashboard/predictivo): ECharts 5.5 por CDN, un solo tono de marca para
  magnitudes, dona de estados con paleta semántica validada (dataviz), tipografía Outfit.
- Preview de disponibilidad (Nueva Reserva y Solicitar) por `fetch` a la API.

## 7 · Infra y settings

> Topología vigente en producción: **single Azure VM** (todo en un servidor).
> Pivot al plan original de App Service: 2026-07-17. Detalles en `docs/DESPLIEGUE_AZURE.md`.

### Settings

- `config/settings/base.py`: TZ America/Bogota, es-co, Celery (broker Redis, eager en
  local/test), allauth email login + provider microsoft, DRF session+token,
  `AZURE_ML_*`, `CELERY_BEAT_SCHEDULE` (alertas c/4h), `ALERTAS_EMAIL_FROM`,
  context processor del menú.
- `local.py`: email consola, debug toolbar. `test.py`: eager, hashers rápidos.
- `production.py`: Blob Storage solo si está `DJANGO_AZURE_ACCOUNT_NAME` (en single-VM NO
  se setea → cae a **whitenoise**). anymail/Mailgun (si no hay creds, console backend).
  SECURE_*, App Insights opcional. Headers de reverse proxy behind-Caddy:
  `USE_X_FORWARDED_HOST`, `SECURE_PROXY_SSL_HEADER`, `CSRF_TRUSTED_ORIGINS` (default
  `https://operaciones.rehavid.com.co`). `collectfasta` se registra SOLO con Azure Blob
  (fuera de ese bloque rompe collectstatic con whitenoise).
- `ALLOWED_HOSTS` por env `DJANGO_ALLOWED_HOSTS` (en prod: dominio + ip + nip.io + FQDN Azure).

### Desarrollo (host híbrido)

- `docker-compose.local.yml`: django + postgres:16 + redis + celeryworker + celerybeat +
  mailpit. El `.venv` del repo es para correr `manage.py`/`pytest`/`ruff` en el host;
  las imágenes Docker instalan sus propias deps.
- Ver `ESTADO_MIGRACION.md` para el modo de levantar (híbrido o full-docker local).

### Producción — single Azure VM

Todo en un servidor Ubuntu 24.04 LTS en Azure (`rehavid-vm`, `Standard_D2as_v7`, `eastus`):

```
Internet (443/80)  →  Caddy :443/:80  →  Django (gunicorn :5000, interno)
   (auto-TLS Let's Encrypt prod)        ├── Celery worker + Celery beat
                                        ├── Postgres 16 (5432, interno, NO expuesto)
                                        └── Redis 7 (6379, interno, NO expuesto)
```

- `docker-compose.vm.yml` (repo): 6 servicios. Postgres/Redis **solo en red interna**
  del compose (sin `ports:` al host). Caddy es la única entrada pública.
- `compose/production/django/Dockerfile`: multi-stage (~263MB), non-root, HEALTHCHECK a
  `/health/`. `start` corre migrate+collectstatic+gunicorn. `entrypoint` espera BD con
  psycopg (sin wait-for-it).
- `compose/vm/caddy/Caddyfile`: bloque del sitio para `operaciones.rehavid.com.co` + host
  temporal `rehavid.20-119-43-198.nip.io`. `acme_ca` global fuerza Let's Encrypt **producción**
  (no staging). Bloque `:80` con `route{}` sirve `/health/` por HTTP (pre-DNS) y redirige
  el resto a HTTPS.
- Env reales en `.envs/.production/` (git-ignored) — hostnames internos `postgres`/`redis`.
- DNS temporal gratis vía **nip.io** (resuelve `<ip-con-guiones>.nip.io` sin registro),
  con cert Let's Encrypt válido. Suficiente para usar la app por HTTPS antes de apuntar
  el dominio real `operaciones.rehavid.com.co`.

### Backups

- `compose/vm/postgres/backup.sh`: `pg_dump` (custom format) + gzip a `/opt/rehavid/backups`,
  retención 7 días local + subida a **Azure Blob Storage** vía managed identity de la VM.
- Cron: `15 3 * * *` (ver `docs/DESPLIEGUE_AZURE.md`). Redis no se backupea (caché efímera).
- Storage: `rehavidbackupsyn6d` / container `rehavid-pg-backups`. VM tiene role
  "Storage Blob Data Contributor" sobre la cuenta.

### Hardening SSH de la VM

NSG permite 22/80/443. **22 está abierto a 0.0.0.0/0** (para runners de GitHub Actions)
con protección en `sshd_config` + **fail2ban**:
- `PasswordAuthentication no` (solo claves)
- `PermitRootLogin no` (root ni con clave)
- `PubkeyAuthentication yes`
- fail2ban jail `sshd`: maxretry 5, bantime 1h, findtime 10m

> Alternativa más segura (no implementada): self-hosted runner en la VM, cero inbound SSH.

### CI/CD — GitHub Actions

- `.github/workflows/ci.yml`: cada PR/push a `main` → `linter` (pre-commit, continue-on-error)
  + `pytest` contra postgres:16 service + `DATABASE_URL`.
- `.github/workflows/deploy.yml`: **push a `main`** (o `workflow_dispatch`) → `test` (pytest
  contra postgres:16) → `deploy-to-vm`: rsync repo a `/opt/rehavid/app/` (con
  `--filter='protect .envs/.production/'` para no tocar secrets), SSH run
  `scripts/deploy-vm.sh` (`up -d --build` + health-wait + migrate + collectstatic),
  verifica `http://<vm-ip>/health/` externo (6 reintentos).
- Requiere **GitHub Secrets** del repo `rehavid-org/rehavid_app`:
  `VM_SSH_KEY` (contenido de `~/.ssh/rehavid-vm-key`), `VM_HOST` (`20.119.43.198`),
  `VM_USER` (`azureuser`). `.envs/.production/` en la VM se gestiona out-of-band — nunca
  lo pisa el workflow.
- Rollback: SSH a VM, `git checkout <tag>` / rsync previo, `bash scripts/deploy-vm.sh`.
  Caveat: migraciones aplicadas no se auto-revierten.

### URL y entrada de la app

- Producción (dominio real pendiente de DNS): `https://operaciones.rehavid.com.co/`
- Hoy con DNS temporal: `https://rehavid.20-119-43-198.nip.io/`
- `/health/` (GET, público): `{"status":"ok"}` con check de BD — lo usan Caddy probe,
  CI health check y monitoreo manual.

## 8 · Decisiones y gotchas que conviene recordar

- Reserva de paquete: `servicio` = primer servicio del paquete (criterio de los tests Fase 3).
- Eliminar paquete/plan: paquete con reservas históricas se **desactiva** en vez de borrarse.
- `ModuloEnMigracionView` (users/views.py) fue el placeholder de módulos no migrados;
  ya no lo usa ningún url pero queda disponible.
- El módulo `bandeja` se AGREGÓ a `MENU_BY_LEVEL` (no existía en el prototipo como módulo);
  usuarios seed con `modulos_permitidos` explícito no lo verán salvo que se les agregue.
- ruff: line-length 119 (alineado a djLint); `**/tests/*` ignora FBT/PLR2004/S106.
- Los tests e2e de las fases 5-7 se posponen a Fase 8 por decisión del usuario
  (los de Fase 5 sí alcanzaron a escribirse: `solicitudes/tests/test_views.py`).
- Suite sana de referencia: **154 tests en verde** (2026-07-13).
