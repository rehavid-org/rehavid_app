"""Analítica: KPIs calculados de la BD (B15) y motor de recomendaciones.

Motor = porte fiel de los 11 detectores del prototipo
(``seed_data/MOTOR_RECOMENDACIONES.md``). Cada detector devuelve 0 o 1
findings; ``analizar()`` los corre todos, tolera fallos por detector y
ordena por severidad descendente. Fecha de referencia: hoy real (B9).
"""

import logging
from collections import Counter
from dataclasses import asdict
from dataclasses import dataclass
from datetime import date
from datetime import timedelta

from django.db.models import Count
from django.db.models import Sum
from django.utils import timezone

from rehavid_app.equipos.models import Equipo
from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.planes.models import Plan
from rehavid_app.reservas.models import Reserva
from rehavid_app.solicitudes.models import EstadoSolicitud
from rehavid_app.solicitudes.models import Solicitud

logger = logging.getLogger(__name__)

# Escala: 1 informativo · 2 atención · 3 importante · 4 crítico
SEVERIDAD_LABEL = {1: "Informativo", 2: "Atención", 3: "Importante", 4: "Crítico"}

EPOCA_SEMANAS = date(2026, 1, 6)  # lunes de la semana 0 del prototipo


@dataclass
class Finding:
    id: str
    area: str
    severidad: int
    titulo: str
    observacion: str
    interpretacion: str
    recomendacion: str
    responsable_sugerido: str
    plazo_dias: int
    modulo: str
    tag: str

    def as_dict(self) -> dict:
        d = asdict(self)
        d["severidad_label"] = SEVERIDAD_LABEL[self.severidad]
        return d


# ────────────────────────────────────────────────────────────
# KPIs de negocio (B15 · nada quemado)
# ────────────────────────────────────────────────────────────
def _rango_reservas(desde=None, hasta=None, servicio=None, ciudad=None):
    qs = Reserva.objects.select_related("servicio", "cliente", "ciudad")
    if desde:
        qs = qs.filter(fecha_salida__gte=desde)
    if hasta:
        qs = qs.filter(fecha_salida__lte=hasta)
    if servicio:
        qs = qs.filter(servicio_id=servicio)
    if ciudad:
        qs = qs.filter(ciudad_id=ciudad)
    return qs


def kpis(desde=None, hasta=None, servicio=None, ciudad=None) -> dict:
    qs = _rango_reservas(desde, hasta, servicio, ciudad)
    total = qs.count()
    canceladas = qs.filter(cancelada=True).count()
    activas = qs.filter(cancelada=False)
    inventario = Equipo.objects.exclude(estado=EstadoEquipo.DE_BAJA)
    return {
        "reservas_total": total,
        "reservas_activas": activas.filter(confirmacion_retorno__isnull=True).count(),
        "reservas_canceladas": canceladas,
        "tasa_cancelacion": round(100 * canceladas / total) if total else 0,
        "personas_evaluadas": activas.aggregate(s=Sum("personas"))["s"] or 0,
        "clientes_activos": activas.values("cliente").distinct().count(),
        "ciudades_cubiertas": activas.values("ciudad").distinct().count(),
        "equipos_total": inventario.count(),
        "equipos_disponibles": inventario.filter(estado=EstadoEquipo.DISPONIBLE).count(),
        "solicitudes_pendientes": Solicitud.objects.filter(estado=EstadoSolicitud.PENDIENTE).count(),
        "planes_en_riesgo": Plan.objects.filter(estado=Plan.Estado.EN_RIESGO).count(),
    }


def series_dashboard(desde=None, hasta=None, servicio=None, ciudad=None) -> dict:
    """Series para los charts ECharts del dashboard/brief."""
    activas = _rango_reservas(desde, hasta, servicio, ciudad).filter(cancelada=False)

    por_servicio = list(
        activas.values("servicio__nombre").annotate(n=Count("id"), personas=Sum("personas")).order_by("-n"),
    )
    por_ciudad = list(activas.values("ciudad__nombre").annotate(n=Count("id")).order_by("-n"))
    por_cliente = list(activas.values("cliente__nombre").annotate(n=Count("id")).order_by("-n")[:8])

    # Evolución semanal (lunes como inicio)
    semanas: Counter = Counter()
    for fecha_salida in activas.values_list("fecha_salida", flat=True):
        lunes = fecha_salida - timedelta(days=fecha_salida.weekday())
        semanas[lunes] += 1
    evolucion = [{"semana": k.isoformat(), "n": v} for k, v in sorted(semanas.items())]

    estados_equipo = list(
        Equipo.objects.exclude(estado=EstadoEquipo.DE_BAJA)
        .values("estado")
        .annotate(n=Count("id"))
        .order_by("-n"),
    )
    display = dict(EstadoEquipo.choices)
    for e in estados_equipo:
        e["label"] = display.get(e["estado"], e["estado"])

    return {
        "por_servicio": por_servicio,
        "por_ciudad": por_ciudad,
        "por_cliente": por_cliente,
        "evolucion_semanal": evolucion,
        "estados_equipo": estados_equipo,
    }


# ────────────────────────────────────────────────────────────
# Motor de recomendaciones · 11 detectores
# ────────────────────────────────────────────────────────────
def _activas():
    return Reserva.objects.filter(cancelada=False).select_related("servicio", "cliente", "ciudad")


def _plural(n: int, sufijo: str = "s") -> str:
    return sufijo if n > 1 else ""


def concentracion_ciudad() -> Finding | None:
    activas = list(_activas())
    total = len(activas)
    if not total:
        return None
    conteo = Counter(r.ciudad.nombre for r in activas)
    ciudad, n_top = conteo.most_common(1)[0]
    pct = round(100 * n_top / total)
    if pct < 40:  # noqa: PLR2004
        return None
    return Finding(
        id="concentracionCiudad",
        area="Operación",
        severidad=3 if pct >= 55 else 2,  # noqa: PLR2004
        titulo=f"{ciudad} concentra {pct}% de las reservas activas",
        observacion=(
            f"De {total} reservas activas, {n_top} están en {ciudad}. "
            f"Las otras {len(conteo) - 1} ciudades se reparten el resto."
        ),
        interpretacion=(
            "Una concentración por encima del 40% en una sola ciudad genera dos riesgos: "
            "(1) sobrecarga del equipo local, lo que aumenta probabilidad de retrasos y errores; "
            "(2) dependencia operativa de una sede, que vuelve frágil la operación ante incidentes "
            "locales (paros, clima, enfermedad del personal)."
        ),
        recomendacion=(
            "Reasignar 2-3 reservas próximas a Medellín o Bogotá donde la capacidad esté libre. "
            "Coordinar con el equipo de operaciones para revisar las rutas de los próximos despachos."
        ),
        responsable_sugerido="Operaciones · Jefferson Suárez",
        plazo_dias=14,
        modulo="reservas",
        tag="concentración",
    )


def sesgo_servicios() -> Finding | None:
    activas = list(_activas())
    total = len(activas)
    conteo = Counter(r.servicio.nombre for r in activas)
    if len(conteo) < 2:  # noqa: PLR2004
        return None
    comunes = conteo.most_common(2)
    (servicio_top, n_top), (segundo, n_segundo) = comunes[0], comunes[1]
    pct_top = round(100 * n_top / total)
    if pct_top < 50:  # noqa: PLR2004
        return None
    return Finding(
        id="sesgoServicios",
        area="Comercial",
        severidad=2,
        titulo=f"{servicio_top} concentra {pct_top}% del portafolio activo",
        observacion=(
            f"{servicio_top} ({n_top} reservas) y {segundo} ({n_segundo} reservas) lideran. "
            f"El resto suma {total - n_top - n_segundo} reservas."
        ),
        interpretacion=(
            "Tener un solo servicio que represente más del 50% del volumen es una concentración de "
            "ingresos. Si ese servicio enfrenta un problema técnico, comercial o regulatorio, el "
            "impacto sobre la operación es alto."
        ),
        recomendacion=(
            "Diseñar una estrategia comercial para incrementar la participación de servicios "
            f"complementarios (EMG, Tobii). Considerar paquetes combinados que vinculen {servicio_top} "
            "con servicios de menor uso para impulsarlos."
        ),
        responsable_sugerido="Comercial · Jeisson Mayorga",
        plazo_dias=30,
        modulo="comercial",
        tag="portafolio",
    )


def riesgo_no_retorno() -> Finding | None:
    hoy = timezone.localdate()
    candidatas = [
        r
        for r in _activas().filter(confirmacion_retorno__isnull=True, riesgo__gte=0.55)
        if -3 <= (r.fecha_retorno_esp - hoy).days <= 14  # noqa: PLR2004
    ]
    if not candidatas:
        return None
    n = len(candidatas)
    top3 = sorted(candidatas, key=lambda r: r.riesgo, reverse=True)[:3]
    detalle = " · ".join(
        f"{r.cliente.nombre} ({r.servicio.nombre}, retorno {r.fecha_retorno_esp}, riesgo {round(r.riesgo * 100)}%)"
        for r in top3
    )
    return Finding(
        id="riesgoNoRetorno",
        area="Operación",
        severidad=4 if n >= 4 else 3,  # noqa: PLR2004
        titulo=f"{n} reserva{_plural(n)} con alto riesgo de no retornar a tiempo",
        observacion=f"Las reservas con riesgo más alto son: {detalle}",
        interpretacion=(
            "Un equipo que no retorna a tiempo bloquea la próxima reserva. Cada día de retraso "
            "desplaza al cliente siguiente y puede generar penalización contractual. Los modelos "
            "predictivos identificaron estas reservas con probabilidad ≥55% de retraso basándose en "
            "historial del cliente, ciudad y tipo de servicio."
        ),
        recomendacion=(
            "Activar protocolo de contacto preventivo 48 horas antes del retorno esperado. Confirmar "
            "logística con el cliente. Si no responde, escalar a coordinador regional. Tener equipo de "
            "respaldo identificado por si el retraso se materializa."
        ),
        responsable_sugerido="Operaciones · Ariel Ramírez",
        plazo_dias=7,
        modulo="reservas",
        tag="riesgo retorno",
    )


def capacidad_ciudad() -> Finding | None:
    buckets: Counter = Counter()
    for r in _activas():
        semana = (r.fecha_salida - EPOCA_SEMANAS).days // 7
        buckets[(r.ciudad.nombre, semana)] += 1
    picos = [(k, v) for k, v in buckets.items() if v >= 5]  # noqa: PLR2004
    if not picos:
        return None
    (ciudad, semana), n = max(picos, key=lambda kv: kv[1])
    return Finding(
        id="capacidadCiudad",
        area="Operación",
        severidad=3 if n >= 7 else 2,  # noqa: PLR2004
        titulo=f"Pico de carga en {ciudad}: {n} reservas concurrentes",
        observacion=(
            f"La semana {semana} acumula {n} reservas simultáneas en {ciudad}. "
            "Esto excede la capacidad estándar (3-4 reservas por semana por sede)."
        ),
        interpretacion=(
            "Cuando una sede excede su capacidad operativa, aumentan los tiempos de respuesta, la "
            "fatiga del equipo y la probabilidad de errores en la captura de datos. También deja al "
            "equipo sin holgura para emergencias o solicitudes urgentes."
        ),
        recomendacion=(
            "Contratar refuerzo temporal (1 técnico por 6 semanas) o redistribuir 2 reservas a otra "
            "sede. Presupuesto estimado: USD 2.800 para refuerzo. Decisión: o asume costo o asume el riesgo."
        ),
        responsable_sugerido="RRHH · Sergio Gómez",
        plazo_dias=10,
        modulo="capacidad",
        tag="capacidad",
    )


def cancelaciones_alta() -> Finding | None:
    total = Reserva.objects.count()
    if not total:
        return None
    canceladas = Reserva.objects.filter(cancelada=True).count()
    pct = round(100 * canceladas / total)
    if pct < 7:  # noqa: PLR2004
        return None
    return Finding(
        id="cancelacionesAlta",
        area="Comercial",
        severidad=3 if pct >= 12 else 2,  # noqa: PLR2004
        titulo=f"Tasa de cancelación en {pct}% · {canceladas} de {total} reservas",
        observacion=(
            "Las cancelaciones recientes vienen principalmente por: cliente reprograma sin "
            "penalización, y equipo dañado reasignado."
        ),
        interpretacion=(
            "Una tasa de cancelación por encima del 7% impacta directamente el ingreso proyectado y "
            "desordena la programación. Si una buena parte se debe a equipos dañados, el problema es "
            "de mantenimiento preventivo, no comercial."
        ),
        recomendacion=(
            "Establecer cláusula de penalización suave (10-20% del valor) para reprogramaciones con "
            "menos de 5 días de anticipación. Para los equipos dañados, programar mantenimiento "
            "preventivo trimestral con fechas en el calendario."
        ),
        responsable_sugerido="Comercial · Jeisson Mayorga",
        plazo_dias=21,
        modulo="comercial",
        tag="cancelaciones",
    )


def top_clientes() -> Finding | None:
    activas = list(_activas())
    total = len(activas)
    if not total:
        return None
    conteo = Counter(r.cliente.nombre for r in activas)
    comunes = conteo.most_common(2)
    cliente_top, n_top = comunes[0]
    n_segundo = comunes[1][1] if len(comunes) > 1 else 0
    pct = round(100 * n_top / total)
    if pct < 15:  # noqa: PLR2004
        return None
    return Finding(
        id="topClientes",
        area="Comercial",
        severidad=3 if pct >= 25 else 2,  # noqa: PLR2004
        titulo=f"{cliente_top} representa {pct}% del volumen activo",
        observacion=f"{cliente_top} acumula {n_top} reservas. El segundo cliente está en {n_segundo} reservas.",
        interpretacion=(
            "Dependencia comercial alta: si este cliente reduce su demanda o cambia de proveedor, el "
            "impacto sobre el ingreso es directo. La diversificación de cartera es una prioridad estratégica."
        ),
        recomendacion=(
            f"Diseñar un plan de retención específico para {cliente_top} (descuento por volumen, "
            "servicio prioritario). En paralelo, abrir 3 cuentas nuevas en sectores donde no estamos "
            "representados."
        ),
        responsable_sugerido="Comercial · Jeisson Mayorga",
        plazo_dias=45,
        modulo="comercial",
        tag="concentración cliente",
    )


def evaluaciones_masivas() -> Finding | None:
    masivas = list(_activas().filter(personas__gte=10))
    if not masivas:
        return None
    n = len(masivas)
    tot = sum(r.personas for r in masivas)
    detalle = " · ".join(
        f"{r.cliente.nombre} ({r.ciudad.nombre}, {r.personas} personas, {r.servicio.nombre})" for r in masivas
    )
    return Finding(
        id="evaluacionesMasivas",
        area="Predictivo",
        severidad=2,
        titulo=f"{n} estudio{_plural(n)} con {tot} personas a evaluar",
        observacion=detalle,
        interpretacion=(
            "Los estudios masivos (>10 personas) requieren protocolos de logística, planificación de "
            "turnos y consolidación de datos diferentes a las mediciones individuales. Sin "
            "pre-tamizaje, se invierte tiempo en evaluar personas sin riesgo aparente."
        ),
        recomendacion=(
            "Aplicar cuestionario nórdico estandarizado a la población antes del despacho. Esto reduce "
            "el tiempo en campo en ~30% y eleva la calidad del estudio. Considerar contratar un "
            "asistente para estos casos."
        ),
        responsable_sugerido="Predictivo · Danna Villarraga",
        plazo_dias=14,
        modulo="predictivo",
        tag="masivos",
    )


def planes_en_riesgo() -> Finding | None:
    riesgo = list(Plan.objects.filter(estado=Plan.Estado.EN_RIESGO))
    if not riesgo:
        return None
    n = len(riesgo)
    detalle = " · ".join(
        f"{p.codigo} · {p.titulo[:60]} (avance {p.avance}% vs esperado {p.esperado}%)" for p in riesgo
    )
    return Finding(
        id="planesEnRiesgo",
        area="Gestión",
        severidad=3 if n >= 3 else 2,  # noqa: PLR2004
        titulo=f"{n} plan{_plural(n, 'es')} de acción con avance por debajo del esperado",
        observacion=detalle,
        interpretacion=(
            "Un plan en riesgo es una decisión que se aceptó pero no se está ejecutando. Si no se "
            "interviene, se convierte en compromiso incumplido y afecta la credibilidad del proceso de "
            "planificación."
        ),
        recomendacion=(
            "Sesión de revisión semanal de 30 minutos con los responsables de planes en riesgo. "
            "Identificar bloqueos (recursos, dependencias, falta de claridad) y resolverlos. Si un "
            "plan ya no es viable, cerrarlo formalmente."
        ),
        responsable_sugerido="Calidad · Ariel Ramírez",
        plazo_dias=7,
        modulo="planes",
        tag="planes",
    )


def solicitudes_pendientes() -> Finding | None:
    limite = timezone.localdate() - timedelta(days=3)
    viejas = list(
        Solicitud.objects.filter(estado=EstadoSolicitud.PENDIENTE, fecha_solicitud__lte=limite)
        .select_related("empresa_cliente", "servicio", "ciudad"),
    )
    if not viejas:
        return None
    n = len(viejas)
    detalle = " · ".join(
        f"{s.codigo} · {s.empresa_cliente.nombre} ({s.servicio.nombre}, {s.ciudad.nombre})" for s in viejas
    )
    return Finding(
        id="solicitudesPendientes",
        area="Servicio",
        severidad=3,
        titulo=f"{n} solicitud{_plural(n, 'es')} pendiente{_plural(n)} hace más de 3 días",
        observacion=detalle,
        interpretacion=(
            "Las solicitudes recibidas y sin asignar generan percepción de servicio lento. El acuerdo "
            "de servicio interno establece respuesta dentro de 24 horas hábiles."
        ),
        recomendacion=(
            "Asignar inmediatamente las solicitudes pendientes. Implementar alerta automática en Slack "
            "o correo cuando una solicitud cumpla 12h sin asignar para garantizar el SLA de 24h."
        ),
        responsable_sugerido="Operaciones · Jhon Orrego",
        plazo_dias=2,
        modulo="solicitudes",
        tag="SLA",
    )


def equipos_criticos() -> Finding | None:
    unicos = (
        Equipo.objects.values("servicio")
        .annotate(n=Count("id"))
        .filter(n=1)
        .values_list("servicio", flat=True)
    )
    criticos = list(
        Equipo.objects.filter(servicio__in=unicos)
        .filter(reservas__cancelada=False)
        .select_related("servicio")
        .distinct(),
    )
    if not criticos:
        return None
    n = len(criticos)
    detalle = " · ".join(f"{e.servicio.nombre} · {e.modelo} ({e.serial})" for e in criticos)
    return Finding(
        id="equiposCriticos",
        area="Inventario",
        severidad=2,
        titulo=f"{n} equipos únicos sin respaldo en flota",
        observacion=detalle,
        interpretacion=(
            "Estos equipos son los únicos de su tipo en la flota. Si fallan o se dañan durante una "
            "operación, no hay reemplazo inmediato y se cae el contrato. Son puntos únicos de falla."
        ),
        recomendacion=(
            "Para los equipos de mayor frecuencia de uso, evaluar la compra de una segunda unidad. "
            "Para los demás, mantener seguros con cobertura por avería y alianza con proveedor para "
            "préstamo emergente."
        ),
        responsable_sugerido="Inventario · Liliana Hernández",
        plazo_dias=60,
        modulo="equipos",
        tag="inventario",
    )


def backlog_alto() -> Finding | None:
    n = Reserva.objects.filter(cancelada=False, fecha_salida__gt=timezone.localdate()).count()
    if n < 15:  # noqa: PLR2004
        return None
    return Finding(
        id="backlogAlto",
        area="Operación",
        severidad=2,
        titulo=f"{n} reservas en backlog · planeación apretada",
        observacion=(
            f"Las próximas {n} reservas están programadas en las próximas 12 semanas. "
            "Volumen alto vs capacidad estándar."
        ),
        interpretacion=(
            "Backlog elevado es señal de buena demanda comercial, pero también de riesgo operativo. "
            "Sin holgura, cualquier evento adverso (enfermedad, daño de equipo) impacta varias semanas."
        ),
        recomendacion=(
            "Mapear las próximas 4 semanas con detalle, identificar holguras y bloqueos. Si la holgura "
            "es < 20%, dejar de aceptar nuevas reservas hasta liberar capacidad o contratar refuerzo."
        ),
        responsable_sugerido="Operaciones · Jefferson Suárez",
        plazo_dias=14,
        modulo="operacion",
        tag="backlog",
    )


DETECTORES = [
    concentracion_ciudad,
    sesgo_servicios,
    riesgo_no_retorno,
    capacidad_ciudad,
    cancelaciones_alta,
    top_clientes,
    evaluaciones_masivas,
    planes_en_riesgo,
    solicitudes_pendientes,
    equipos_criticos,
    backlog_alto,
]


def analizar() -> list[Finding]:
    """Corre los 11 detectores; un detector que falle no tumba el análisis."""
    findings: list[Finding] = []
    for detector in DETECTORES:
        try:
            if finding := detector():
                findings.append(finding)
        except Exception:
            logger.exception("Detector %s falló", detector.__name__)
    findings.sort(key=lambda f: f.severidad, reverse=True)
    return findings


def crear_plan_desde_finding(finding_id: str, usuario) -> Plan:
    """Convierte un finding vigente en un Plan de acción (finding→plan)."""
    from rehavid_app.auditoria import services as auditoria  # noqa: PLC0415

    finding = next((f for f in analizar() if f.id == finding_id), None)
    if finding is None:
        msg = "La recomendación ya no está vigente (los datos cambiaron)"
        raise ValueError(msg)
    plan = Plan.objects.create(
        area=finding.area,
        titulo=finding.titulo,
        descripcion=f"{finding.observacion}\n\nRecomendación: {finding.recomendacion}",
        responsable=finding.responsable_sugerido,
        vence=timezone.localdate() + timedelta(days=finding.plazo_dias),
        avance=0,
        esperado=0,
        estado=Plan.Estado.ABIERTO,
    )
    auditoria.registrar(usuario, "crear_plan_desde_finding", "planes", f"{plan.codigo} ← {finding.id}")
    return plan
