# MOTOR de Análisis y Recomendaciones — Especificación para porte a Python

Fuente: `frontend/rehavid_v13_produccion.html`, objeto `const MOTOR` (líneas ~6827–7098).

## Contexto global

- **Fecha de referencia**: `MOTOR.HOY = 2026-05-22` (fecha "congelada" de la demo; en producción usar fecha actual).
- **Helper** `MOTOR.diff(d)`: `Math.round((new Date(d) - HOY) / 86400000)` → días desde HOY hasta `d` (negativo = pasado).
- **Escala de severidad**: `1` informativo · `2` atención · `3` importante · `4` crítico.
- **Formato de finding** (todos los detectores producen este objeto):
  `{ area, severidad, titulo, observacion, interpretacion, recomendacion, responsable_sugerido, plazo_dias, modulo, tag }`
  y `analizar()` añade `_id` = clave del detector.
- **Ejecución** (`MOTOR.analizar()`): corre los 11 detectores en orden, concatena findings (cada detector retorna array de 0 o 1 findings), captura excepciones por detector (warn y sigue), y ordena descendente por `severidad`.
- Filtros auxiliares: `porArea(area)`, `porModulo(modulo)`, `top(n)` (primeros n tras ordenar).
- "Reservas activas" = `RESERVAS.filter(r => !r.cancelada)` salvo que se indique otra cosa.

---

## 1. `concentracionCiudad`

- **Área**: Operación · **Módulo**: `reservas` · **Tag**: `concentración`
- **Condición**: sobre reservas activas, agrupar por `ciudad`; sea `top` la ciudad con más reservas y `pct = round(100 * top / total_activas)`. Dispara si `pct >= 40`.
- **Severidad**: `3` si `pct >= 55`, si no `2`.
- **Título**: `"{ciudad} concentra {pct}% de las reservas activas"`
- **Observación**: `"De {total} reservas activas, {n_top} están en {ciudad}. Las otras {num_ciudades - 1} ciudades se reparten el resto."`
- **Interpretación**: "Una concentración por encima del 40% en una sola ciudad genera dos riesgos: (1) sobrecarga del equipo local, lo que aumenta probabilidad de retrasos y errores; (2) dependencia operativa de una sede, que vuelve frágil la operación ante incidentes locales (paros, clima, enfermedad del personal)."
- **Recomendación**: "Reasignar 2-3 reservas próximas a Medellín o Bogotá donde la capacidad esté libre. Coordinar con el equipo de operaciones para revisar las rutas de los próximos despachos."
- **Responsable**: Operaciones · Jefferson Suárez · **Plazo**: 14 días.

## 2. `sesgoServicios`

- **Área**: Comercial · **Módulo**: `comercial` · **Tag**: `portafolio`
- **Condición**: sobre reservas activas, agrupar por `servicio`; requiere ≥2 servicios distintos. Sea `top` el más frecuente y `pctTop = round(100 * top / total_activas)`. Dispara si `pctTop >= 50`.
- **Severidad**: `2` (fija).
- **Título**: `"{servicio_top} concentra {pctTop}% del portafolio activo"`
- **Observación**: `"{top} ({n_top} reservas) y {segundo} ({n_segundo} reservas) lideran. El resto suma {total - n_top - n_segundo} reservas."`
- **Interpretación**: "Tener un solo servicio que represente más del 50% del volumen es una concentración de ingresos. Si ese servicio enfrenta un problema técnico, comercial o regulatorio, el impacto sobre la operación es alto."
- **Recomendación**: "Diseñar una estrategia comercial para incrementar la participación de servicios complementarios (EMG, Tobii). Considerar paquetes combinados que vinculen {servicio_top} con servicios de menor uso para impulsarlos."
- **Responsable**: Comercial · Jeisson Mayorga · **Plazo**: 30 días.

## 3. `riesgoNoRetorno`

- **Área**: Operación · **Módulo**: `reservas` · **Tag**: `riesgo retorno`
- **Condición**: candidatas = reservas donde: NO `cancelada`, NO `confirmado_retorno` (falsy), `riesgo >= 0.55` (estrictamente: descarta si `(r.riesgo||0) < 0.55`), y `d = diff(fecha_retorno_esp)` cumple `-3 <= d <= 14` (retorno entre 3 días atrás y 14 días adelante). Dispara si hay ≥1 candidata.
- **Severidad**: `4` si `candidatas >= 4`, si no `3`.
- **Título**: `"{n} reserva(s) con alto riesgo de no retornar a tiempo"` (plural con "s" si n>1).
- **Observación**: top 3 por riesgo descendente: `"Las reservas con riesgo más alto son: {cliente} ({servicio}, retorno {fecha_retorno_esp}, riesgo {riesgo*100 sin decimales}%) · ..."`
- **Interpretación**: "Un equipo que no retorna a tiempo bloquea la próxima reserva. Cada día de retraso desplaza al cliente siguiente y puede generar penalización contractual. Los modelos predictivos identificaron estas 3 reservas con probabilidad ≥55% de retraso basándose en historial del cliente, ciudad y tipo de servicio."
- **Recomendación**: "Activar protocolo de contacto preventivo 48 horas antes del retorno esperado. Confirmar logística con el cliente. Si no responde, escalar a coordinador regional. Tener equipo de respaldo identificado por si el retraso se materializa."
- **Responsable**: Operaciones · Ariel Ramírez · **Plazo**: 7 días.

## 4. `capacidadCiudad`

- **Área**: Operación · **Módulo**: `capacidad` · **Tag**: `capacidad`
- **Condición**: sobre reservas activas, calcular semana ISO relativa: `semana = floor((fecha_salida - 2026-01-06) / (7 * 86400000))` (época = lunes 6 ene 2026). Bucket key = `"{ciudad}@W{semana}"`, contar reservas por bucket. Picos = buckets con `count >= 5`. Dispara si hay ≥1 pico; usa el pico mayor.
- **Severidad**: `3` si `pico >= 7`, si no `2`.
- **Título**: `"Pico de carga en {ciudad}: {n} reservas concurrentes"`
- **Observación**: `"La semana {semana} acumula {n} reservas simultáneas en {ciudad}. Esto excede la capacidad estándar (3-4 reservas por semana por sede)."`
- **Interpretación**: "Cuando una sede excede su capacidad operativa, aumentan los tiempos de respuesta, la fatiga del equipo y la probabilidad de errores en la captura de datos. También deja al equipo sin holgura para emergencias o solicitudes urgentes."
- **Recomendación**: "Contratar refuerzo temporal (1 técnico por 6 semanas) o redistribuir 2 reservas a otra sede. Presupuesto estimado: USD 2.800 para refuerzo. Decisión: o asume costo o asume el riesgo."
- **Responsable**: RRHH · Sergio Gómez · **Plazo**: 10 días.

## 5. `cancelacionesAlta`

- **Área**: Comercial · **Módulo**: `comercial` · **Tag**: `cancelaciones`
- **Condición**: `pct = round(100 * canceladas / total_reservas)` (sobre TODAS las reservas, no solo activas). Dispara si `pct >= 7`.
- **Severidad**: `3` si `pct >= 12`, si no `2`.
- **Título**: `"Tasa de cancelación en {pct}% · {canc} de {total} reservas"`
- **Observación**: "Las cancelaciones recientes vienen principalmente por: cliente reprograma sin penalización, y equipo dañado reasignado." (texto fijo, refleja los 2 motivos demo).
- **Interpretación**: "Una tasa de cancelación por encima del 7% impacta directamente el ingreso proyectado y desordena la programación. Si una buena parte se debe a equipos dañados, el problema es de mantenimiento preventivo, no comercial."
- **Recomendación**: "Establecer cláusula de penalización suave (10-20% del valor) para reprogramaciones con menos de 5 días de anticipación. Para los equipos dañados, programar mantenimiento preventivo trimestral con fechas en el calendario."
- **Responsable**: Comercial · Jeisson Mayorga · **Plazo**: 21 días.
- Nota: con los datos seed (2 canceladas de 57 = 4%) este detector NO dispara.

## 6. `topClientes`

- **Área**: Comercial · **Módulo**: `comercial` · **Tag**: `concentración cliente`
- **Condición**: sobre reservas activas, agrupar por `cliente`; sea `top` el mayor y `pct = round(100 * n_top / total_activas)`. Dispara si `pct >= 15`.
- **Severidad**: `3` si `pct >= 25`, si no `2`.
- **Título**: `"{cliente_top} representa {pct}% del volumen activo"`
- **Observación**: `"{cliente_top} acumula {n_top} reservas. El segundo cliente está en {n_segundo (0 si no hay)} reservas."`
- **Interpretación**: "Dependencia comercial alta: si este cliente reduce su demanda o cambia de proveedor, el impacto sobre el ingreso es directo. La diversificación de cartera es una prioridad estratégica."
- **Recomendación**: "Diseñar un plan de retención específico para {cliente_top} (descuento por volumen, servicio prioritario). En paralelo, abrir 3 cuentas nuevas en sectores donde no estamos representados."
- **Responsable**: Comercial · Jeisson Mayorga · **Plazo**: 45 días.

## 7. `evaluacionesMasivas`

- **Área**: Predictivo · **Módulo**: `predictivo` · **Tag**: `masivos`
- **Condición**: masivas = reservas activas con `personas >= 10`. Dispara si hay ≥1. `tot = suma de personas` de las masivas.
- **Severidad**: `2` (fija).
- **Título**: `"{n} estudio(s) con {tot} personas a evaluar"` (plural "s" si n>1).
- **Observación**: lista `"{cliente} ({ciudad}, {personas} personas, {servicio})"` unida por ` · `.
- **Interpretación**: "Los estudios masivos (>10 personas) requieren protocolos de logística, planificación de turnos y consolidación de datos diferentes a las mediciones individuales. Sin pre-tamizaje, se invierte tiempo en evaluar personas sin riesgo aparente." (Ojo: el texto dice ">10" pero el código usa `>= 10`.)
- **Recomendación**: "Aplicar cuestionario nórdico estandarizado a la población antes del despacho. Esto reduce el tiempo en campo en ~30% y eleva la calidad del estudio. Considerar contratar un asistente para estos casos."
- **Responsable**: Predictivo · Danna Villarraga · **Plazo**: 14 días.

## 8. `planesEnRiesgo`

- **Área**: Gestión · **Módulo**: `planes` · **Tag**: `planes`
- **Condición**: planes con `estado === 'risk'` en `PLANES`. Dispara si hay ≥1.
- **Severidad**: `3` si `n >= 3`, si no `2`.
- **Título**: `"{n} plan(es) de acción con avance por debajo del esperado"` (plural "es" si n>1).
- **Observación**: por plan: `"{id} · {titulo truncado a 60 chars} (avance {avance}% vs esperado {esperado}%)"` unido por ` · `.
- **Interpretación**: "Un plan en riesgo es una decisión que se aceptó pero no se está ejecutando. Si no se interviene, se convierte en compromiso incumplido y afecta la credibilidad del proceso de planificación."
- **Recomendación**: "Sesión de revisión semanal de 30 minutos con los responsables de planes en riesgo. Identificar bloqueos (recursos, dependencias, falta de claridad) y resolverlos. Si un plan ya no es viable, cerrarlo formalmente."
- **Responsable**: Calidad · Ariel Ramírez · **Plazo**: 7 días.

## 9. `solicitudesPendientes`

- **Área**: Servicio · **Módulo**: `solicitudes` · **Tag**: `SLA`
- **Condición**: pendientes = `SOLICITUDES` con `estado === 'pendiente'`; viejas = pendientes con `diff(fecha_solicitud) <= -3` (solicitadas hace 3+ días respecto a HOY). Dispara si hay ≥1 vieja.
- **Severidad**: `3` (fija).
- **Título**: `"{n} solicitud(es) pendiente(s) hace más de 3 días"` (plural "es"/"s" si n>1).
- **Observación**: por solicitud: `"{id} · {empresa_cliente} ({servicio}, {ciudad})"` unido por ` · `.
- **Interpretación**: "Las solicitudes recibidas y sin asignar generan percepción de servicio lento. El acuerdo de servicio interno establece respuesta dentro de 24 horas hábiles."
- **Recomendación**: "Asignar inmediatamente las solicitudes pendientes. Implementar alerta automática en Slack o correo cuando una solicitud cumpla 12h sin asignar para garantizar el SLA de 24h."
- **Responsable**: Operaciones · Jhon Orrego · **Plazo**: 2 días.

## 10. `equiposCriticos`

- **Área**: Inventario · **Módulo**: `equipos` · **Tag**: `inventario`
- **Condición**: equipos "únicos" = categorías con exactamente 1 unidad en `EQUIPOS` (con seed: Tobii, Dinamómetro, Lactómetro, Dron). De esos, los que tienen al menos una reserva NO cancelada asociada (match por `r.equipos_ids.includes(e.id)` si es array, si no `r.equipo_id === e.id`). Dispara si hay ≥1.
- **Severidad**: `2` (fija).
- **Título**: `"{n} equipos únicos sin respaldo en flota"`
- **Observación**: por equipo: `"{categoria} · {modelo} ({serial})"` unido por ` · `.
- **Interpretación**: "Estos equipos son los únicos de su tipo en la flota. Si fallan o se dañan durante una operación, no hay reemplazo inmediato y se cae el contrato. Son puntos únicos de falla."
- **Recomendación**: "Para los equipos de mayor frecuencia de uso, evaluar la compra de una segunda unidad. Para los demás, mantener seguros con cobertura por avería y alianza con proveedor para préstamo emergente."
- **Responsable**: Inventario · Liliana Hernández · **Plazo**: 60 días.

## 11. `backlogAlto`

- **Área**: Operación · **Módulo**: `operacion` · **Tag**: `backlog`
- **Condición**: activas futuras = reservas NO canceladas con `fecha_salida > HOY` (estrictamente futuro). Dispara si `n >= 15`.
- **Severidad**: `2` (fija).
- **Título**: `"{n} reservas en backlog · planeación apretada"`
- **Observación**: `"Las próximas {n} reservas están programadas en las próximas 12 semanas. Volumen alto vs capacidad estándar."`
- **Interpretación**: "Backlog elevado es señal de buena demanda comercial, pero también de riesgo operativo. Sin holgura, cualquier evento adverso (enfermedad, daño de equipo) impacta varias semanas."
- **Recomendación**: "Mapear las próximas 4 semanas con detalle, identificar holguras y bloqueos. Si la holgura es < 20%, dejar de aceptar nuevas reservas hasta liberar capacidad o contratar refuerzo."
- **Responsable**: Operaciones · Jefferson Suárez · **Plazo**: 14 días.

---

## Resumen de umbrales (tabla rápida)

| # | Detector | Umbral de disparo | Escala de severidad |
|---|----------|-------------------|---------------------|
| 1 | concentracionCiudad | ciudad top ≥ 40% de activas | ≥55% → 3, si no 2 |
| 2 | sesgoServicios | servicio top ≥ 50% de activas | 2 fija |
| 3 | riesgoNoRetorno | riesgo ≥ 0.55 y retorno en [-3, +14] días | ≥4 reservas → 4, si no 3 |
| 4 | capacidadCiudad | ≥ 5 reservas ciudad+semana | ≥7 → 3, si no 2 |
| 5 | cancelacionesAlta | tasa cancelación ≥ 7% (todas) | ≥12% → 3, si no 2 |
| 6 | topClientes | cliente top ≥ 15% de activas | ≥25% → 3, si no 2 |
| 7 | evaluacionesMasivas | ≥1 reserva activa con personas ≥ 10 | 2 fija |
| 8 | planesEnRiesgo | ≥1 plan estado 'risk' | ≥3 planes → 3, si no 2 |
| 9 | solicitudesPendientes | pendiente con diff(fecha_solicitud) ≤ -3 | 3 fija |
| 10 | equiposCriticos | equipo único (1/categoría) con reserva activa | 2 fija |
| 11 | backlogAlto | ≥ 15 reservas futuras no canceladas | 2 fija |
