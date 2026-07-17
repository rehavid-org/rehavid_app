# Plan de Migración · REHAVID Operaciones → Django

**Origen:** `/Users/yesid/Desktop/Desarrollo/Personal/rehavid` (FastAPI + Cosmos DB + HTML monolítico de 7.814 líneas)
**Destino:** este repositorio (`rehavid_app`, scaffold cookiecutter-django: Django 6.0, DRF, allauth, PostgreSQL)
**Infraestructura objetivo:** Docker en local y producción · Azure (Container Registry + App Service/Container Apps + PostgreSQL Flexible Server + Key Vault + Blob + App Insights)
**Fecha del análisis:** 2026-07-13

> **Nota de cierre (2026-07-17):** Las fases 0-7 están completas y la aplicación se
> encuentra **en producción** en una single Azure VM con CI/CD automatizado (push a
> `main` → deploy). Ver `docs/ARQUITECTURA.md` sección 7 y `docs/DESPLIEGUE_AZURE.md`
> para el detalle del despliegue. La Fase 8 (QA integral + go-live con Rehavid) sigue
> pendiente. El contenido de este documento se conserva como histórico inmutable del
> plan original.

---

## 1 · Qué es la aplicación

**REHAVID Operaciones** es la plataforma interna de gestión de **Rehavid S.A.S.**, empresa colombiana de ergonomía y evaluación de riesgo músculo-esquelético (DME). Gestiona el ciclo completo de **reservas de equipos de medición biomecánica** (Xsens, EMG Delsys, Tobii, Dinamómetro Mark-10, Lactómetro, Dron DJI, GoPro, más el software Tumeke sin unidad física) que se despachan a empresas cliente (ARL SURA, JD TASS, etc.) para estudios ergonómicos en campo.

Usuarios: equipo interno de Rehavid (dirección, operadores, coordinación de programación) + **portal externo** para empresas solicitantes.

### Módulos funcionales (inventario completo)

| # | Módulo | Qué hace | Estado actual |
|---|--------|----------|---------------|
| 1 | **Autenticación y permisos** | Login email/password + SSO Microsoft Entra ID. 4 niveles: 1 Admin Global, 2 Operador, 3 Coordinador, 4 Solicitante. Permisos granulares por módulo (`modulos_permitidos`) y extra (`agregar_equipos`, `editar_inventario`, `editar_usuarios`) | Backend OK; frontend demo usa contraseñas en texto plano y SSO cosmético |
| 2 | **Reservas** (núcleo, reglas R002–R009) | Crear con validación de stock, reprogramar, cancelar (libera equipos), confirmar retorno (OK/INCOMPLETO/DAÑADO) con preparación (+1 día de bloqueo, lavado camisetas Xsens), historial de auditoría por reserva, riesgo calculado | Lógica sólida; **sin UI de creación**; acciones de tabla nunca se renderizan (bug rol vs nivel) |
| 3 | **Equipos y stock** | Inventario por serial, 7 estados (disponible/en_uso/en_preparacion/en_revision/en_mantenimiento/en_transito/de_baja), accesorios (53 ítems, consumibles, requiere_lavado), ficha individual (O04) con métricas e historial, mantenimiento, dar de baja (O18, solo nivel 1, bloquea si hay reservas activas), KPI disponibles/total (O02), Tumeke como tarjeta especial sin stock (O07) | OK en backend; alta de equipo e import Excel crean un shape de objeto distinto (bug O06 parcial) |
| 4 | **Paquetes** | Combos multi-equipo (PKG-01…05) que reservan un equipo por categoría (`equipos_ids[]`, O08), disponibilidad tri-estado en tiempo real (O09), permisos de edición nivel ≤2 (O20) | Falta CRUD de paquetes en backend (crear/editar/eliminar son stubs o solo-local) |
| 5 | **Portal solicitante** | Crear solicitud (servicio, ciudad, empresa, personas, fecha mín. hoy+7, días), datos del profesional obligatorios (O19), accesorios dinámicos por servicio (O16), preview de disponibilidad/saturación (O10), editar/cancelar con regla 48h/observaciones (O11), mini-calendario | Backend **no persiste la fecha solicitada** (bug); edición vía `prompt()` |
| 6 | **Bandeja del operador** | Badge de pendientes en menú (O17), bandeja con últimas pendientes y urgencia >12h, "Atender" confirma la solicitud | **Atender NO crea la reserva** (flujo incompleto en frontend y backend) |
| 7 | **Alertas logísticas (O21)** | 4 detecciones automáticas: salidas próximas 48h, retornos vencidos, mantenciones ≤14 días, equipos en preparación. Canales WhatsApp/Email/Teams configurables, envío por alerta | Detección OK; envío real es placeholder (TODO); config guardada como hack en el container de solicitudes |
| 8 | **Predictivo MSK** | Score de probabilidad de hallazgo con factores explicativos (SHAP), gauge, histograma, diagrama corporal SVG. Azure ML con fallback a mock heurístico | Mock funcional; scripts de entrenamiento listos; falta histórico real (300+ filas) |
| 9 | **Dashboard / Brief ejecutivo** | KPIs, treemap, sankey, sunburst, radar, evolución semanal, tabla con totales, filtros servicio/ciudad/periodo | Todo con datos quemados en HTML; hay que calcularlo del modelo de datos |
| 10 | **Motor de recomendaciones** | 11 detectores (concentración por ciudad, sesgo de servicios, riesgo de no retorno, capacidad, cancelaciones, top clientes, evaluaciones masivas, planes en riesgo, solicitudes pendientes, equipos críticos, backlog) → findings convertibles en planes | Solo existe en JS; migrar a servicio Python |
| 11 | **Planes de acción** | CRUD de planes (open/risk/done) con avance vs esperado, filtros | CRUD backend básico; crear desde UI es stub |
| 12 | **Calendario** | Rejilla 12 meses con densidad de reservas, panel de detalle por día, filtro por servicio | Solo frontend, calculado de RESERVAS |
| 13 | **Administración** | CRUD usuarios, activar/desactivar, ficha con actividad, editor de permisos por módulo | Crear usuario es stub en frontend; ficha usa datos hardcodeados |
| 14 | **Auditoría** | Log global de eventos (quién, qué, módulo, cuándo, IP), filtros por usuario/fechas, export Excel | Logs mock en frontend; backend solo escribe auditoría en alertas |
| 15 | **Import/Export Excel** | Export XLSX de reservas/equipos/log/ficha (SheetJS), plantillas, import de equipos | Export funcional en cliente; import con schema inconsistente |

### Los 20 endpoints que el frontend ya espera (contrato de la capa `API` JS)

`POST /auth/login` · `GET /auth/sso/url` · `GET /auth/me` · `GET /reservas` · `GET /reservas/disponibilidad` · `POST /reservas` · `POST /reservas/{id}/cancelar` · `POST /reservas/{id}/reprogramar` · `POST /reservas/{id}/retorno` · `GET /equipos` · `POST /equipos/{id}/listo` · `POST /equipos/{id}/mantenimiento` · `GET /paquetes` · `GET /paquetes/{id}/disponibilidad` · `POST /predictivo/score` · `GET /planes` · `POST /planes` · `GET /admin/users` · `POST /admin/users`

Más los del backend FastAPI que el frontend consume solo en modo local (hay que exponerlos igual): solicitudes (listar/crear/editar/cancelar/observación/atender/badge), equipos (ficha, baja, CRUD), alertas (canales GET/PUT, detectadas, enviar), auditoría, planes (PUT/DELETE), paquetes CRUD (faltante hoy).

---

## 2 · Defectos a corregir durante la migración (no replicar)

**Flujos rotos (los "muchas cosas no funcionan"):**

| # | Defecto | Dónde está | Corrección en Django |
|---|---------|-----------|----------------------|
| B1 | Acciones de reservas (reprogramar/cancelar/retorno) **nunca se muestran**: gate `currentUser?.rol==='admin'` pero ningún usuario tiene ese rol | frontend 5797 | Autorización por **nivel** (1-2) en template/permiso DRF |
| B2 | **Atender solicitud no crea la reserva** — promete crearla y solo cambia estado | frontend 5745, backend `/solicitudes/{id}/atender` | El flujo atender = transacción: valida disponibilidad → crea Reserva vinculada a la Solicitud → confirma. FK `Solicitud.reserva` |
| B3 | **No existe UI para crear reservas** directamente; `editarReserva` es stub | frontend | Vista + formulario "Nueva reserva" (servicio o paquete) con preview de disponibilidad |
| B4 | La **fecha solicitada no se persiste** (`fecha_sugerida` se descarta al crear la solicitud) | backend `solicitudes.py` crear | Campo `fecha_sugerida` en el modelo, obligatorio |
| B5 | **Regla 48h mal calculada**: compara contra `fecha_confirmada` (día en que el operador confirmó, en el pasado) en lugar de la fecha programada del servicio | backend `solicitudes.py` cancelar | Comparar `fecha_programada` del servicio − ahora ≥ 48h |
| B6 | **IDs generados por COUNT(1)** (`R-###`, `SOL-###`): colisionan tras cancelaciones/borrados y con concurrencia | backend reservas/solicitudes | PK autoincrement de PostgreSQL + código legible derivado (`R-{pk:03d}`) o secuencia dedicada |
| B7 | **Modelo de equipo inconsistente**: inventario usa `categoria/modelo/ciudad_base`; alta manual e import Excel crean `nombre/servicio/ciudad` → equipos nuevos no aparecen ni entran en disponibilidad | frontend 7566, 7279 | Un solo modelo `Equipo` canónico; formulario e import mapean a los mismos campos |
| B8 | `marcarEquipoListo` del frontend usa `equipo_id` singular, ignora `equipos_ids[]` de paquetes | frontend 4218 | Lógica única en el servicio backend (ya correcta) y frontend consumiéndola |
| B9 | **Fecha "hoy" congelada** en `2026-05-22` en ~15 lugares | frontend | `timezone.now()` / `date.today()` en servidor; nada de fechas quemadas |
| B10 | Config de canales de alertas guardada como documento mágico `__canales_alertas__` **dentro del container de solicitudes** | backend alertas | Modelo `ConfiguracionCanal` propio |
| B11 | Stubs sin implementar: crear plan desde UI, crear/editar paquete, crear usuario, export PDF/Excel del topbar, `exportFicha` | frontend | Implementarlos de verdad (CRUDs Django) o eliminarlos del alcance con decisión explícita |
| B12 | Auditoría y ficha de usuario con **datos inventados/pseudoaleatorios** | frontend 6634, 7576 | Modelo `EventoAuditoria` real alimentado por middleware/señales en cada acción |
| B13 | Contraseñas en texto plano en el cliente; SSO botón cosmético | frontend USERS | Django auth (argon2 ya configurado) + allauth; SSO real con proveedor Microsoft |
| B14 | Export de reservas incluye columna `valor_contacto` inexistente | frontend 7273 | Definir el schema de export contra el modelo real |
| B15 | Dashboard/Brief con **KPIs quemados en el HTML** (28 reservas, 18 clientes, $741K…) que no cuadran con los datos (57 reservas) | frontend | Todos los KPIs calculados en servidor desde la BD |
| B16 | Predictivo: código Azure ML comentado referencia constantes inexistentes | frontend 5379 | Servicio backend único (mock ↔ Azure ML por settings), frontend nunca llama a Azure ML directo |
| B17 | Ninguna persistencia en modo demo (todo se pierde al recargar) | frontend | Irrelevante tras migrar: la BD es la fuente de verdad |
| B18 | `config/celery_app.py` existe en el scaffold pero **celery no está en las dependencias** | rehavid_app | Decidir: agregar Celery+Redis (recomendado para envío de alertas) o eliminar el archivo |

**Riesgos/mejoras adicionales:** condición de carrera al reservar (dos requests simultáneos pueden tomar el mismo equipo) → resolver con `select_for_update()` en transacción; JWT con secret default `CHANGE-ME` → secretos por env/Key Vault; CORS abierto con credenciales → configurar `django-cors-headers` estricto.

---

## 3 · Arquitectura destino

### Decisiones

1. **Un solo servicio Django** (no frontend estático separado + API): Django sirve las vistas HTML con templates y expone la API DRF bajo `/api/` para lo dinámico (disponibilidad en vivo, datos de charts, badge de pendientes, predictivo). Elimina CORS entre dominios, el modo dual demo/producción y el HTML monolítico.
2. **PostgreSQL** (ya en el scaffold) reemplaza Cosmos DB. El dominio es relacional (reservas↔equipos↔paquetes↔solicitudes): FKs, M2M y transacciones resuelven lo que en Cosmos se hacía con `ARRAY_CONTAINS` y queries cross-partition.
3. **Frontend**: templates Django + Bootstrap 5 (crispy ya instalado) con los design tokens de Rehavid (morado `#4025CE`, verde `#02E577`, fuente Outfit), **ECharts 5.5** (mismas gráficas) alimentado por endpoints JSON, y **SheetJS se reemplaza por export server-side con openpyxl** (más robusto y auditable). Los `prompt()/confirm()` se reemplazan por modales/formularios.
4. **Auth**: `django-allauth` (ya instalado) con el modelo `User` extendido (nivel, empresa, rol descriptivo, permisos por módulo). SSO con `allauth.socialaccount` proveedor `microsoft` (Entra ID). Para la API: sesión Django (mismo dominio) — no se necesita JWT propio.
5. **Tareas asíncronas**: agregar **Celery + Redis** (Redis ya está en deps) para envío de alertas (WhatsApp/Email/Teams), detección programada (celery beat) y llamadas a Azure ML sin bloquear requests.
6. **Docker en todo el ciclo**: compose local (django + postgres + redis + celeryworker + celerybeat + mailpit) y build de producción multi-stage con gunicorn; despliegue como contenedor en Azure.

### Apps Django a crear (dentro de `rehavid_app/`)

```
rehavid_app/
├── users/          (ya existe · extender: nivel, empresa, rol, modulos_permitidos, permisos_extra, activo, métricas)
├── catalogo/       Servicio (Xsens, EMG, …, Tumeke con flag sin_stock), Ciudad, Empresa cliente, AccesorioTipo por servicio
├── equipos/        Equipo, Accesorio, estados, ficha, mantenimiento, baja
├── reservas/       Reserva, ReservaEquipo (M2M), HistorialReserva, ConfirmacionRetorno, servicio de disponibilidad
├── solicitudes/    Solicitud, ProfesionalRequerido, AccesorioSolicitado, Observacion, flujo atender→reserva
├── paquetes/       Paquete, categorías requeridas, disponibilidad tri-estado
├── alertas/        ConfiguracionCanal, AlertaEnviada, detectores, integraciones (tasks Celery)
├── predictivo/     servicio mock/Azure ML, historial de scores
├── planes/         Plan de acción, conversión finding→plan
├── analitica/      KPIs, agregaciones para dashboard/brief/calendario, motor de recomendaciones (11 detectores)
└── auditoria/      EventoAuditoria + middleware/señales de registro
```

### Modelo de datos (esencial)

- **User** (extiende AbstractUser): `nivel` (1-4), `empresa` FK, `rol_descriptivo`, `modulos_permitidos` (ArrayField/JSON), `permisos_extra`, `activo`. Grupos Django espejo de los 4 niveles para permisos.
- **Servicio**: nombre, `requiere_equipo_fisico` (False para Tumeke), catálogo de accesorios típicos (O16).
- **Equipo**: `servicio` FK (categoría), modelo, serial único, estado (choices, 7 estados), responsable, ciudad_base FK, ultima_revision, proxima_mantencion, notas, historial_uso, motivo_mantenimiento, motivo_baja, fecha_baja.
- **Accesorio**: equipo FK, nombre, cantidad, completo, requiere_lavado, consumible.
- **Paquete**: nombre, desc, `servicios_requeridos` M2M, duracion_dias, activo.
- **Reserva**: codigo legible, servicio FK, cliente (Empresa FK), ciudad FK, personas, contactos_efectivos, fecha_salida, fecha_retorno_esp, estado, cancelada, motivo_cancelacion, reprogramada_desde, paquete FK nullable, `equipos` M2M (reemplaza `equipos_ids[]` + `equipo_id` legacy), riesgo, solicitud FK nullable (B2).
- **ConfirmacionRetorno** (OneToOne Reserva): fecha, estado_kit, notas, operador FK, requiere_preparacion, preparacion_completa, preparacion_notas.
- **HistorialReserva**: reserva FK, timestamp, accion, usuario FK, detalle.
- **Solicitud**: codigo, solicitante FK, empresa_cliente FK, servicio FK, ciudad FK, personas, `fecha_sugerida` (B4), dias_estimados, fecha_confirmada, operador FK, estado, notas, profesional (campos O19), motivo/fechas de cancelación, editada, notificada_a/en. + **Observacion** y **AccesorioSolicitado** como tablas hijas.
- **ConfiguracionCanal**: canal (whatsapp/email/teams), activo, destino. **AlertaEnviada**: tipo, canal, mensaje, destino, enviada_por, timestamp, resultado.
- **Plan**: codigo, app/área, titulo, desc, responsable, vence, avance, esperado, estado.
- **EventoAuditoria**: usuario FK, accion, modulo, detalle, timestamp, ip.
- **PrediccionRegistro** (opcional): entrada, score, modelo_version, es_simulacion, factores JSON.

### Reglas de negocio a preservar (tests obligatorios)

- **R003/R008 disponibilidad**: solapamiento `inicio <= r_fin && fin >= r_ini`; excluye estados en_mantenimiento/en_transito/de_baja; +1 día si retorno con `requiere_preparacion` sin completar; Tumeke siempre disponible; exclusión de la propia reserva al reprogramar.
- **R006/O08/O09 paquetes**: todas las categorías deben tener stock; asigna 1 equipo por categoría; al cancelar libera todos (si ninguna otra reserva activa los usa); disponibilidad tri-estado (disponible/parcial/no) con fecha próxima de disponibilidad total.
- **R002 reprogramar/cancelar** con historial. **R007/R009 retorno**: estado kit, preparación → `en_preparacion` → "listo" vuelve a disponible y actualiza ultima_revision; incrementa historial_uso.
- **O18 baja**: solo nivel 1, bloqueada con reservas activas. **O11** regla 48h (corregida, B5). **O17** badge + bandeja + urgencia >12h. **O10** preview saturación. **O19** profesional obligatorio. **O16** accesorios por servicio.
- **Riesgo heurístico** al crear reserva: `min(0.85, 0.18 + personas*0.04)` (hasta que el modelo real esté activo).
- Matriz de permisos por nivel (ver §1) aplicada en backend (permisos DRF + mixins de vistas), no solo ocultando botones.

---

## 4 · Plan de trabajo por fases

> Cada fase termina con la app arrancando en Docker y sus tests en verde. Orden pensado para tener flujo end-to-end demo lo antes posible.

### Fase 0 · Fundaciones (1-2 días)
- [ ] Crear estructura Docker local: `compose/local/django/Dockerfile`, `docker-compose.local.yml` con servicios **django, postgres:16, redis, celeryworker, celerybeat, mailpit**; poblar `.envs/.local/` (.django, .postgres).
- [ ] Agregar Celery a `pyproject.toml` (o eliminar `config/celery_app.py` — decisión B18; recomendado: agregar).
- [ ] Ajustar settings: `TIME_ZONE = "America/Bogota"`, `LANGUAGE_CODE = "es-co"`, apps locales registradas.
- [ ] CI (GitHub Actions ya scaffolded): lint (ruff), mypy, pytest contra Postgres en contenedor.
- [ ] Verificación: `docker compose -f docker-compose.local.yml up` levanta y migra.

### Fase 1 · Dominio y datos (3-4 días)
- [ ] Extender `users.User` (nivel, empresa, permisos) + migraciones + admin + grupos por nivel.
- [ ] Crear apps `catalogo`, `equipos`, `paquetes`, `reservas`, `solicitudes`, `planes`, `alertas`, `auditoria` con los modelos de §3.
- [ ] Django admin completo para todos los modelos (herramienta interna de rescate).
- [ ] **Fixtures/seed** (management command `seed_demo`): 10 equipos con accesorios, 5 paquetes, 5 usuarios (ariel n1, danna n1, jhon n2, liliana n3, monica n4), catálogos de servicios/ciudades/empresas, 7 solicitudes, y las **57 reservas** del array `RESERVAS` del HTML (extraerlas a fixture JSON).
- [ ] Verificación: seed corre idempotente; admin navega todos los modelos.

### Fase 2 · Autenticación y permisos (2-3 días)
- [ ] Login email/password con allauth (email como username, ya configurado en cookiecutter).
- [ ] SSO Microsoft Entra ID vía `allauth.socialaccount.providers.microsoft`; auto-vinculación por email para dominio `@rehavid.com.co`; usuarios externos por password.
- [ ] Sistema de permisos: decoradores/mixins `nivel_requerido(n)` + permisos DRF equivalentes a `require_nivel`; menú dinámico por `MENU_BY_LEVEL`; permisos extra granulares.
- [ ] Regla: usuario desactivado no entra (con mensaje).
- [ ] Tests de la matriz completa de acceso por nivel (las 18 vistas × 4 niveles).

### Fase 3 · Lógica de negocio core: reservas/equipos/paquetes (4-5 días)
- [ ] Portar `reservas_service` a `reservas/services.py` con transacciones y `select_for_update()`: disponibilidad, disponibilidad de paquete, crear, cancelar, reprogramar, retorno, listo, mantenimiento, baja.
- [ ] Corregir B5, B6, B8 al portar. IDs legibles generados de PK.
- [ ] **Suite de tests de negocio** (la red de seguridad de toda la migración): solapamientos, +1 día preparación, paquete multi-equipo asigna/libera todos, baja bloqueada con reservas activas, Tumeke, reprogramación que se auto-excluye, concurrencia (dos reservas simultáneas al último equipo → una falla).
- [ ] Verificación: cobertura de R002–R009 + O08/O09/O18 con tests que pasan.

### Fase 4 · Vistas y API: operación interna (5-7 días)
- [ ] Layout base (sidebar por nivel, breadcrumb, chip usuario, toasts) con design tokens Rehavid.
- [ ] **Reservas**: tabla con filtros/búsqueda, **formulario Nueva Reserva** (B3) con preview de disponibilidad en vivo (endpoint `/api/reservas/disponibilidad/`), acciones por nivel (B1): reprogramar/cancelar/retorno como modales con formularios (no `prompt`).
- [ ] **Equipos**: grid + tabla por serial, KPI disponibles/total (O02), ficha modal (O04) desde `/api/equipos/{id}/ficha/`, acciones listo/mantenimiento/baja, tarjeta Tumeke (O07), formulario de alta **con el modelo canónico** (B7).
- [ ] **Paquetes**: tarjetas con disponibilidad tri-estado (O09) + **CRUD completo** (B11) restringido a nivel ≤2 (O20).
- [ ] **Calendario**: rejilla 12 meses server-rendered + detalle por día.
- [ ] Endpoints DRF espejo del contrato de la capa `API` JS (§1) documentados con drf-spectacular.
- [ ] Verificación: flujo completo crear→reprogramar→retorno→preparación→listo desde el navegador.

### Fase 5 · Portal solicitante y bandeja (3-4 días)
- [ ] Vistas del portal (nivel 4): inicio con KPIs y mini-calendario, equipos disponibles (read-only + próxima fecha libre), **formulario de solicitud** (accesorios dinámicos O16, profesional O19, preview saturación O10, fecha mínima +7, persistiendo `fecha_sugerida` — B4), mis solicitudes con acciones por estado (editar/cancelar/observación, regla 48h corregida — B5).
- [ ] Bandeja del operador (O17): badge en menú (polling ligero a `/api/solicitudes/badge/`), lista de pendientes con urgencia >12h.
- [ ] **Atender = crear reserva** (B2): al confirmar, transacción que valida disponibilidad, crea la Reserva ligada a la Solicitud y notifica; si no hay stock, informa y deja pendiente.
- [ ] Verificación e2e: solicitante crea → operador atiende → se crea reserva → solicitante la ve confirmada.

### Fase 6 · Analítica, predictivo, alertas, planes, admin (5-6 días)
- [ ] **Analítica**: servicio de KPIs y agregaciones (reemplaza todo dato quemado — B15); endpoints JSON para ECharts; vistas Brief y Dashboard con filtros; motor de recomendaciones portado (11 detectores) + convertir finding→plan.
- [ ] **Predictivo**: `predictivo/services.py` = puerto del mock heurístico + cliente Azure ML (`AZURE_ML_ENABLED` por settings, fallback automático — B16); vista con gauge, factores, diagrama corporal SVG.
- [ ] **Alertas**: detectores como servicio + tarea beat programada; `ConfiguracionCanal` en BD (B10); envío vía Celery con adaptadores stub documentados para WhatsApp Business/Graph API/`django-anymail` (email sí puede quedar funcional ya que anymail está instalado); registro en `AlertaEnviada` + auditoría.
- [ ] **Planes**: CRUD completo (B11).
- [ ] **Admin de usuarios**: CRUD real (B11, B13), activar/desactivar, editor de permisos, ficha con actividad **real** desde auditoría (B12).
- [ ] **Auditoría**: middleware/servicio que registra acciones de negocio (login, crear/cancelar/reprogramar, exports, cambios de permisos…), vista con filtros + export.
- [ ] **Excel server-side** (openpyxl, ya en el stack): export de reservas/equipos/log/ficha, plantilla e import de equipos con validación contra el modelo canónico (B7, B14).

### Fase 7 · Docker producción + Azure (3-4 días) — ✅ RESUELTA 2026-07-17

> **Cierre:** desplegada en single Azure VM (Ubuntu 24.04, Docker Compose con Caddy +
> Django + Celery + Postgres + Redis). CI/CD vía GitHub Actions (push a `main`).
> Detalles en `docs/ARQUITECTURA.md` sección 7 y `docs/DESPLIEGUE_AZURE.md`.
> El plan original de App Service/ACR queda superseded.
- [ ] `compose/production/django/Dockerfile` multi-stage (uv/pip → runtime slim, usuario no-root, collectstatic, gunicorn, healthcheck `/health/` — agregar endpoint con check de BD).
- [ ] `docker-compose.production.yml` para staging local de la imagen.
- [ ] Settings producción: `django-storages[azure]` para estáticos/media en Blob, Application Insights (opentelemetry), `SECURE_*`, allowed hosts.
- [ ] Infra Azure (adaptando la guía existente, sin Cosmos/Static Web App):
  - Resource Group · **Azure Container Registry** · **App Service for Containers** (o Container Apps) para django + celery worker/beat · **Azure Database for PostgreSQL Flexible Server** · **Azure Cache for Redis** · **Key Vault** (SECRET_KEY, DB, credenciales Entra/ML) · **Blob Storage** · **Application Insights** · App registration Entra ID · dominio `operaciones.rehavid.com.co` + SSL.
- [ ] CI/CD GitHub Actions: build & push a ACR → deploy → migrate como job de release.
- [ ] Azure ML: mantener scripts `ml/` tal cual (entrenamiento es offline); el servicio Django consume el endpoint cuando exista.
- [ ] Verificación: pipeline despliega a un slot/entorno de staging; health check verde.

### Fase 8 · Datos reales, QA integral y go-live (1-2 semanas, con Rehavid)
- [ ] Importar las 57 reservas reales + usuarios reales (management command de import desde Excel).
- [ ] **QA de todos los flujos** (checklist §5) con los 4 niveles de usuario.
- [ ] UAT con el equipo Rehavid (Ariel, Danna, Jhon, Liliana) y un solicitante externo.
- [ ] Hardening: rate limiting en login, backups de PostgreSQL, alertas de App Insights.
- [ ] Go-live y decomiso del prototipo.

**Estimación total: ~6-8 semanas** de desarrollo efectivo (fases 0-7) + UAT.

---

## 5 · Checklist de verificación funcional (criterio de "todo funciona")

Cada ítem debe pasar en la app Django desplegada en Docker antes de dar por migrado el flujo:

**Autenticación:** login password ✓ · login SSO Entra ✓ · usuario inactivo bloqueado ✓ · logout ✓ · cada nivel ve solo su menú ✓ · URL directa a vista prohibida → 403 ✓

**Reservas:** crear individual ✓ · crear con paquete (asigna N equipos) ✓ · stock agotado bloquea con motivo ✓ · reprogramar valida nueva fecha ✓ · cancelar libera todos los equipos ✓ · retorno OK/INCOMPLETO/DAÑADO ✓ · Xsens fuerza preparación ✓ · equipo en preparación bloquea +1 día ✓ · marcar listo ✓ · historial completo por reserva ✓ · dos usuarios simultáneos no duplican asignación ✓

**Equipos:** KPI disponibles/total en vivo ✓ · ficha con métricas/historial/próxima reserva ✓ · mantenimiento bloquea reservas ✓ · baja solo nivel 1 y bloqueada con reservas activas ✓ · alta manual aparece en inventario y disponibilidad ✓ · Tumeke visible sin stock ✓

**Solicitudes:** crear con accesorios+profesional ✓ · fecha sugerida persistida ✓ · preview de saturación ✓ · editar pendiente ✓ · cancelar con regla 48h sobre fecha programada ✓ · observación en confirmada ✓ · badge y bandeja del operador ✓ · urgencia >12h ✓ · **atender crea la reserva** ✓

**Paquetes:** tri-estado correcto ✓ · CRUD solo nivel ≤2 ✓ · solicitante solo elige ✓

**Alertas:** 4 detectores correctos con datos de prueba ✓ · config de canales persiste ✓ · envío email real funciona · WhatsApp/Teams registran intento (stub documentado) ✓

**Predictivo:** mock devuelve score+factores ✓ · flag Azure ML activa endpoint real con fallback ✓

**Analítica:** KPIs de brief/dashboard cuadran con la BD (nada quemado) ✓ · filtros ✓ · charts ✓ · motor de recomendaciones genera findings ✓ · finding→plan ✓

**Admin/Auditoría:** CRUD usuarios ✓ · permisos granulares aplican ✓ · toda acción de negocio queda en auditoría ✓ · exports Excel desde servidor ✓ · import de equipos ✓

**Infra:** app corre solo con `docker compose up` ✓ · imagen de producción < 500MB, no-root, healthcheck ✓ · deploy Azure por CI/CD ✓ · estáticos en Blob ✓ · logs en App Insights ✓ · secretos solo en Key Vault ✓

---

## 6 · Referencias al código origen

| Qué | Dónde (repo origen) |
|-----|---------------------|
| Lógica R002-R009 | `backend/app/services/reservas_service.py` |
| Schemas/contratos | `backend/app/models/schemas.py` |
| Endpoints actuales (44) | `backend/app/routers/*.py` |
| Mock predictivo + cliente Azure ML | `backend/app/services/prediccion_service.py` |
| Seed (equipos/paquetes/usuarios) | `backend/app/seed.py` |
| 57 reservas reales | `frontend/rehavid_v13_produccion.html` líneas ~3385-3448 (array `RESERVAS`) |
| Catálogo accesorios por servicio | frontend `ACCESORIOS_POR_SERVICIO` (~4598) |
| Motor de recomendaciones (11 detectores) | frontend `MOTOR` (~6827-7082) |
| Matriz de permisos por nivel | frontend `NIVELES`/`MENU_BY_LEVEL` (~3461-3524) |
| Diagrama corporal SVG | frontend `renderDiagramaCorporal` (~5514) |
| Entrenamiento ML (offline, se conserva) | `ml/entrenamiento_modelo.py`, `ml/score.py` |
| Guía Azure original (adaptar) | `docs/instrucciones_azure_ingeniero.md` |
