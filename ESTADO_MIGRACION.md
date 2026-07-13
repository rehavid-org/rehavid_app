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

## ⏳ Fase 4 · Vistas operación interna + API — NO INICIADA ← **PRÓXIMO PASO**
Plan (sección 4 de PLAN_MIGRACION.md):
1. Layout base: sidebar por nivel usando `user.modulos` (context processor o template tag), design tokens de `seed_data/DESIGN_TOKENS.md` (morado #4025CE, verde #02E577, fuente Outfit), Bootstrap 5 + crispy ya instalados. Usar skill `frontend-design`.
2. Vistas Reservas: tabla con filtros, **formulario Nueva Reserva** (B3) con preview de disponibilidad en vivo, acciones reprogramar/cancelar/retorno como modales gateados por `NivelRequeridoMixin(nivel_maximo=2)` (B1). Los servicios de negocio YA existen — las vistas solo los llaman.
3. Vistas Equipos: grid+tabla, KPI disponibles/total (O02), ficha modal (O04), acciones listo/mantenimiento/baja, tarjeta Tumeke (O07), alta con modelo canónico (B7).
4. Paquetes: tarjetas tri-estado (O09, usar `verificar_disponibilidad_paquete` + `proxima_fecha_disponible`) + CRUD nivel ≤2 (O20/B11).
5. Calendario 12 meses server-rendered.
6. API DRF espejo del contrato JS (sección 1 del plan) en `config/api_router.py` + serializers por app.
7. Tests de matriz de acceso vista×nivel.

## ⏳ Fase 5 · Portal solicitante — NO INICIADA
Servicios listos; faltan vistas: formulario solicitud (O16 accesorios dinámicos desde `AccesorioTipo`, O19 profesional, O10 preview saturación, fecha mínima hoy+7), mis solicitudes, bandeja operador + badge (polling a endpoint `contar_pendientes`), botón Atender → `atender_solicitud`.

## ⏳ Fase 6 · Analítica/predictivo/alertas/planes/admin — NO INICIADA
- Motor 11 detectores: spec exacta en `seed_data/MOTOR_RECOMENDACIONES.md` → portar a `analitica/services.py`.
- Predictivo: portar mock heurístico de `../rehavid/backend/app/services/prediccion_service.py` a `predictivo/services.py` (flag `AZURE_ML_ENABLED` por settings, fallback automático).
- Alertas: 4 detectores (copiar de `../rehavid/backend/app/routers/alertas.py` líneas 64-122) como servicio + task Celery beat; envío email real con anymail, WhatsApp/Teams stubs documentados.
- KPIs dashboard/brief desde BD (B15) + endpoints JSON para ECharts.
- CRUD planes y usuarios (B11/B13), export/import Excel con openpyxl (B14), vista auditoría.

## ⏳ Fase 7 · Docker producción + Azure — NO INICIADA
Dockerfile multi-stage producción, compose producción, settings Azure (Blob/App Insights), CI/CD. Guía origen: `../rehavid/docs/instrucciones_azure_ingeniero.md`.

## ⏳ Fase 8 · Verificación integral — NO INICIADA
Checklist funcional completo en sección 5 de `PLAN_MIGRACION.md`. También pendiente: build de la imagen Docker local (`docker compose -f docker-compose.local.yml build django`) y `docker compose up` completo.

---

## Cómo retomar (nueva sesión)

```bash
cd /Users/yesid/Desktop/Desarrollo/Personal/rehavid_app
docker compose -f docker-compose.local.yml up -d postgres redis mailpit
source .envs/.local/.postgres
export DATABASE_URL="postgres://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:5432/$POSTGRES_DB"
uv run pytest        # debe dar 83 tests en verde (verificado 2026-07-13)
```
Luego arrancar Fase 4 (arriba). Notas:
- El repo NO es git aún (`git init` recomendado antes de seguir).
- Ruff no se ha corrido sobre el código nuevo; puede haber ajustes menores de lint.
- `mypy` tampoco se ha corrido.
- Usuarios seed: `ariel.ramirez@rehavid.com.co`/`13011976` (nivel 1), `jhon.orrego@rehavid.com.co`/`demo123` (nivel 2), `liliana.hernandez@rehavid.com.co`/`demo123` (nivel 3), `monica.vargas@arlsura.com`/`demo123` (nivel 4).
