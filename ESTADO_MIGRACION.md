# Estado de la migración · 2026-07-15

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

### 🩹 Paridad visual con producción legacy · cerrado 2026-07-15
Auditoría con Playwright contra la app en producción (Azure Container Apps, la que REHAVID
usa hoy) encontró y corrigió:
- **Bug real**: doble serialización JSON rompía los accesorios dinámicos (O16) del portal de
  solicitud — `solicitudes/views.py` pasaba `json.dumps()` ya serializado a `|json_script`.
  Corregido; verificado creando una solicitud real end-to-end (SOL-008).
- **Gráficas faltantes portadas con cálculo real** (no se copiaron números fijos del origen,
  que en varios casos eran decorativos/simulados — ver commit): treemap y sankey
  servicio→ciudad→cliente + "perfil por ciudad" + gauge "salud del backlog" en
  Dashboard/Brief; histograma de riesgo poblacional en Predictivo; stock por categoría y
  equipos por ciudad en Equipos; distribución por empresa en Administración.
- **Actividad 30 días (Admin) y eficiencia logística (Dashboard)**: en el origen eran 100%
  inventados (el propio código lo admite); acá se calculan de verdad desde
  `EventoAuditoria`/`ConfirmacionRetorno` — mejor que el origen.
- **Predictivo poblacional** (trayectoria por cliente, diagrama corporal por zona, top-5
  zonas): el origen los tenía 100% simulados sin ningún modelo de datos detrás. Por decisión
  del usuario, se construyó infraestructura real nueva (`PrediccionRegistro.zonas` JSONField)
  en vez de copiar los números falsos — arrancan vacíos y se llenan con cada predicción real
  calculada. Verificado: con 0 predicciones muestran estado vacío; tras calcular una,
  se pueblan solas.
- Nuevo: señal `users/signals.py` registra cada login real en auditoría (antes no se
  registraba ningún evento de login).
- `estado_visual()`/`estado_visual_display()` en `Solicitud`: matiz de presentación
  "En curso" para una confirmada dentro de su ventana de ejecución (no es un estado
  persistido nuevo, solo mejora lo que ve el portal — el dato semilla traía `en_curso`
  que no existía en el enum `EstadoSolicitud` y se mostraba sin traducir).
- `uv run ruff check .` limpio tras todos los cambios.

### 🔍 Inventario exhaustivo de vistas · 2026-07-15 (segunda pasada)
El usuario pidió confirmar que TODAS las secciones de producción existen en Django. Se catalogaron
las 17 vistas reales del prototipo origen (menú `<nav>` completo, 1:1 con las 17 `<section class="view">`)
más la pantalla de login. Resultado: las 17 existen en Django. Se cerraron 2 brechas que esa
auditoría encontró:
- **Dashboard**: faltaba el chart "Distribución por servicio y mes" (stacked horizontal). Portado
  con `analitica.services.distribucion_servicio_mes()` — a diferencia del origen (3 meses y 3
  servicios hardcodeados), usa los meses/servicios reales presentes en los datos.
- **Arquitectura macro-app** (nivel 1, ítem de menú que nunca se había abierto): no existía en
  absoluto. Es documentación/roadmap interno (stack tecnológico, árbol de apps planificadas del
  ecosistema, spec del módulo común Planes de acción) — no dashboard de negocio, así que se replicó
  el contenido casi verbatim, pero corrigiendo el stack tecnológico para que describa la
  arquitectura REAL de esta migración (Django/PostgreSQL/GitHub Actions) en vez del stack
  aspiracional del prototipo FastAPI/CosmosDB/Azure DevOps que ya no aplica. Nueva vista
  `ArquitecturaView` (`users/admin_views.py`), url `administracion:arquitectura`, template
  `administracion/arquitectura.html`, registrada en `MENU_BY_LEVEL` solo nivel 1 (verificado 403
  para nivel 2).
- Verificado con Playwright sin cambios de código (ya estaban bien): Planes de acción, Calendario,
  Auditoría, vista de tarjetas de Equipos.
- Pendiente de decisión del usuario (no cerrado, son detalles menores dentro de vistas que ya
  existen, no secciones faltantes): tabs de severidad + botón "Reanalizar ahora" en Recomendaciones,
  posible import de Reservas desde Excel (hoy solo existe import de Equipos).

### 🔎 Auditoría exhaustiva de las 17 vistas · 2026-07-15 (tercera pasada)
El usuario pidió "revisa TODO y compara TODO" tras notar que el Resumen Ejecutivo tenía más
brechas de las detectadas en la segunda pasada. Se lanzaron 5 agentes en paralelo a diseccionar
línea por línea el JS/HTML origen de las 13 vistas restantes (Recomendaciones, Planes, Reservas,
Paquetes, Calendario, Alertas, Admin, Ficha de usuario, Auditoría, y las 4 del Portal), clasificando
cada dato como cálculo real o texto/número fijo. Hallazgo transversal: **hay 7 bloques
"conclusion-block" (síntesis "Auto-generada") repartidos en Brief/Dashboard/Predictivo/Planes/
Paquetes/Calendario/Admin, todos 100% texto fijo sin ninguna función que los genere** — mismo
patrón que ya se había encontrado en el Resumen Ejecutivo, no exclusivo de esa vista.

Brechas reales cerradas (cálculo real, no se copiaron los números fijos del origen):
- **Alertas**: faltaba por completo el panel "Estado de reservas en curso" (4 KPIs: no
  retornadas/vencen en 3 días/programadas esta semana/a tiempo) y la tabla de "reservas próximas
  a vencer" con acción sugerida por urgencia — en el origen los 4 KPIs eran fijos pero la tabla sí
  era lógica real que nunca se había portado. `alertas/services.py::estado_reservas()`.
- **Admin/Usuarios**: el banner de 4 KPIs (usuarios activos, empresas, administradores, tiempo de
  sesión) no existía en Django; en origen estaban hardcodeados y **desincronizados de su propio
  mock** (ej. "3 admins" cuando el array real tenía 2). Implementados reales; "tiempo de sesión"
  (no hay tracking de duración) se sustituyó por "acciones registradas últimos 7 días" desde
  `EventoAuditoria`.
- **Planes de acción**: el panel lateral (totales/en curso/en riesgo/cerrados/avance promedio/
  próximo vencimiento/apps origen) y el conclusion-block eran 100% fijos en origen, nunca
  recalculados ni al importar por Excel. Implementados con agregados reales de `Plan.objects` +
  síntesis basada en los planes en riesgo reales.
- **Recomendaciones**: agregados los tabs de severidad (Críticos/Importantes/Atención con conteos
  reales — en origen coexistían un HTML con conteos fijos y un JS que sí los recalculaba en
  runtime, la migración solo tenía el filtro por área), botón "Reanalizar ahora", timestamp de
  último escaneo, y "Lectura ejecutiva del motor" (semi-generada con datos reales, igual que el
  patrón parcial que ya tenía el origen aquí).
- **Paquetes**: "usos en 30 días" ahora es un conteo real (`Reserva.objects.filter(paquete=p,
  fecha_salida__gte=hace_30d)`) en vez del campo fijo del origen; tabs Activos/Inactivos/Más usados
  ahora filtran de verdad (en origen no tenían `onclick`, eran decorativos).
- **Portal · Inicio**: agregadas las 3 tarjetas de acceso rápido (Consultar/Solicitar/Seguir) que
  faltaban — son navegación simple, sin dato de por medio.

Verificado con Playwright, consola limpia, en las 7 vistas tocadas. `uv run ruff check .` limpio.

Nota operativa (no vinculada al código): el servidor de desarrollo (Werkzeug/autoreload) quedó dos
veces en un estado a medias tras varias ediciones seguidas de `.py`, sirviendo contexto vacío en
variables nuevas hasta reiniciar el contenedor (`docker compose restart django`). Si una plantilla
muestra un dato vacío que el shell de Django sí calcula bien, reiniciar el contenedor antes de
seguir depurando.

### ✅ Auditoría de "¿todas las gráficas están vivas?" · 2026-07-15 (cuarta pasada)
El usuario pidió verificar, dato por dato, que TODAS las gráficas del local estuvieran alimentadas
por datos reales (no solo comparadas contra producción). Se extrajo el `option` de cada instancia
ECharts vía `browser_evaluate` en las 5 páginas con gráficas (Dashboard, Resumen ejecutivo,
Predictivo, Equipos, Admin) — las 18 gráficas de negocio ya calculaban de BD. Se encontraron y
cerraron 2 excepciones:
- **Predictivo → "Factores que explican el score"**: probado con 2 inputs opuestos, siempre daba
  exactamente los mismos 6 pesos fijos (`FACTORES_MOCK`), sin importar servicio/personas/sector.
  Reescrito en `predictivo/services.py::_factores_reales()`: cada factor es ahora un término real
  de la propia fórmula heurística (incluye `Reserva.objects.filter(cliente__nombre=...).count()`
  como "Historial del cliente" real desde BD), así que el peso y el score varían genuinamente con
  el input. Verificado: Xsens/15 personas/Manufactura/rotativos → score 80%; Lactómetro/1 persona/
  Rehavid S.A.S. → score 20%, con factores y pesos distintos en cada caso.
- **Arquitectura macro-app → árbol de apps**: la rama "Rehavid · Operaciones" (que sí existe) ahora
  muestra conteos reales (reservas activas, predicciones calculadas, planes registrados) en vez de
  ser solo etiquetas. Las ramas "Salud ocupacional"/"Comercial" siguen siendo roadmap explícito
  ("planeada, aún no existe") — no hay dato real posible ahí porque esas apps no existen en el código.
- La barra "Meta" del chart de eficiencia logística (Dashboard) queda igual: es un umbral de negocio
  (3 días), no una medición — corresponde que sea constante, no dato calculado.

### 📊 Auditoría de Excel (export/import/plantillas) · 2026-07-15 (quinta pasada)
El usuario preguntó si todo lo de Excel (exportes, imports, plantillas) es funcional. Se probó
en vivo (descarga real + `openpyxl.load_workbook` sobre el archivo recibido, no solo el botón):
- **Ya existían y SÍ funcionan de punta a punta**: export de Reservas, export+plantilla+import de
  Equipos (probado subiendo la plantilla descargada — creó el equipo `XS-99` real, validación
  todo-o-nada confirmada), export de Auditoría.
- **Brecha real cerrada**: producción tiene botón "Excel" también en Planes, Paquetes,
  Usuarios/Admin y Portal·Mis-solicitudes — acá no existían. Se agregó export real (reutilizando
  `xlsx.py`) a las 4: `planes:export`, `paquetes:export`, `administracion:usuarios_export`,
  `portal:mis_solicitudes_export` (esta última filtrada por `request.user`, nivel 4).
- **Bug real encontrado y corregido en el camino**: el export de usuarios daba 500 —
  `openpyxl` no acepta datetimes con timezone y `User.last_login` es tz-aware; se corrigió
  formateando con `timezone.localtime(...).strftime(...)` (mismo patrón que ya usaba el export de
  auditoría, que sí lo hacía bien desde el principio).
- **Cierre inmediato**: se agregó también plantilla + import "todo o nada" a Planes y Paquetes
  (mismo patrón validado de Equipos), incluyendo el M2M `servicios_requeridos` en Paquetes.
  Probado subiendo la plantilla real de cada uno: creó `PL-011` y `PKG-99` con todos los campos
  correctos; probado también el rechazo todo-o-nada con un lote de 2 filas (1 válida + 1 con
  fecha/estado inválidos) → no se creó ninguna, confirmado por conteo antes/después.
- Verificado: requests reales (login vía curl + descarga + `openpyxl.load_workbook` + upload +
  re-descarga) en los 9 endpoints de Excel de la app (Reservas, Equipos ×3, Auditoría, Planes ×3,
  Paquetes ×3, Usuarios, Portal). `ruff check .` limpio.

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

### 📌 Pivot a VM unica Azure · 2026-07-16

Se abandono el plan de App Service (multiples servicios gestionados) en favor de una
**unica VM Azure** con Docker Compose: Django + Celery worker/beat + Postgres 16 + Redis 7
+ Caddy (auto-TLS). Backups locales + off-VM a Azure Blob via managed identity.

Archivos creados:
- `docker-compose.vm.yml` — compose de produccion para la VM
- `compose/vm/caddy/Caddyfile` — reverse proxy con Let's Encrypt
- `compose/vm/postgres/backup.sh` — backup diario (cron host)
- `scripts/deploy-vm.sh` — script de despliegue idempotente
- `.envs/.production_example/{.django,.postgres}` — actualizados a la topologia VM
- `config/settings/production.py` — `USE_X_FORWARDED_HOST`, `CSRF_TRUSTED_ORIGINS`
- `docs/DESPLIEGUE_AZURE.md` — reescrito con el enfoque VM unica

El plan anterior de App Service queda **superseded** (ver nota en DESPLIEGUE_AZURE.md).

### ⏳ PENDIENTE de la Fase 7 (retomar aquí)
1. ~~Liberar espacio en disco del Mac~~ **RESUELTO** (2026-07-15).
2. `docker compose -f docker-compose.production.yml up --build` → verificar `curl localhost:5000/health/`, login y estáticos (whitenoise). **Pospuesto por decisión del usuario** (2026-07-15): por ahora solo se asegura que el código de producción esté completo, sin levantar el staging local.
3. Verificar celeryworker/celerybeat del compose de producción. **Pospuesto** junto con el punto 2.
4. ✅ **Build de la imagen local y `up` full-docker — VERIFICADO (2026-07-15)**: `docker compose -f docker-compose.local.yml build django` compiló OK (fix `build-essential` confirmado, psycopg-c compila sin problema); `up -d` levantó los 6 servicios (postgres, redis, mailpit, django, celeryworker, celerybeat); datos del seed ya presentes en el volumen persistente; login real por email (`jhon.orrego@rehavid.com.co`) → 302 → `/reservas/` → 200. Full-docker local queda validado de punta a punta.
5. Re-correr `pytest`. **Pospuesto por ahora** (decisión del usuario, 2026-07-15) — pendiente para más adelante.
6. Cargar secrets en GitHub y probar el workflow deploy.yml contra Azure — **cuando se vaya a desplegar a producción real** (no ahora).

## ⏳ Fase 8 · Verificación integral — NO INICIADA
Checklist funcional completo en sección 5 de `PLAN_MIGRACION.md`. El build de la imagen Docker local y `docker compose up` completo ya se verificaron (ver Fase 7, punto 4). Pendiente: pytest completo (pospuesto por decisión del usuario) y checklist funcional del plan.

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
✅ Build y `up` completo verificados (2026-07-15): los 6 servicios levantan y login real funciona. Nota:
`docker compose exec django ...` NO expone `DATABASE_URL` (solo el `entrypoint` la exporta para el proceso
principal) — para comandos puntuales via `exec` usar `docker compose run --rm django <comando>` en su lugar.

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

### Estado del entorno / advertencias vigentes (2026-07-15)

- Espacio en disco: **resuelto** (42GB libres verificado 2026-07-15). Full-docker local
  (`docker-compose.local.yml`) construido y levantado sin problemas.
- Staging de producción local (`docker-compose.production.yml`) y verificación de
  celeryworker/celerybeat: **pospuestos por decisión del usuario** — por ahora solo se
  garantiza que el código de producción esté completo, sin correr ese compose localmente.
- pytest: **pospuesto por decisión del usuario** por ahora (no es que esté roto; la última
  corrida sana fue 2026-07-13 con 154 tests).
- `mypy` no se ha corrido nunca sobre el proyecto.
- Documentación de contexto completo: `CLAUDE.md` (mapa operativo), `docs/ARQUITECTURA.md`
  (mapa exhaustivo de la app), `docs/DESPLIEGUE_AZURE.md` (infra).
- **Próximo trabajo**: cuando el usuario lo indique — correr pytest, y luego staging de
  producción local + Azure real (secrets, workflow deploy.yml) cuando se vaya a desplegar.
