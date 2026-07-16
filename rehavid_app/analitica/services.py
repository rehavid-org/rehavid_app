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
        "distribucion_servicio_mes": distribucion_servicio_mes(desde, hasta, servicio, ciudad),
        "treemap": treemap_servicio_ciudad(desde, hasta, servicio, ciudad),
        "sankey": sankey_servicio_ciudad_cliente(desde, hasta, servicio, ciudad),
        "perfil_ciudades": perfil_ciudades(desde, hasta, servicio, ciudad),
        "eficiencia_logistica": eficiencia_logistica(),
    }


PERFIL_CIUDADES_TOPE = 3  # top-N ciudades comparadas en el chart de perfil
EFICIENCIA_META_DIAS = 3  # meta de negocio: días de retorno esperados por servicio
DISTRIBUCION_MESES_TOPE = 6  # últimos N meses con datos, en vez de fijar 3 meses de calendario

MESES_ES = [
    "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic",
]


def distribucion_servicio_mes(desde=None, hasta=None, servicio=None, ciudad=None) -> dict:
    """Reservas por servicio x mes (stacked). A diferencia del prototipo origen
    (3 meses y 3 servicios fijos), usa los meses y servicios reales presentes en
    los datos, hasta los últimos DISTRIBUCION_MESES_TOPE con actividad."""
    activas = _rango_reservas(desde, hasta, servicio, ciudad).filter(cancelada=False)
    conteo: Counter = Counter()
    for fecha_salida, nombre_servicio in activas.values_list("fecha_salida", "servicio__nombre"):
        conteo[(fecha_salida.replace(day=1), nombre_servicio)] += 1
    meses = sorted({mes for mes, _ in conteo})[-DISTRIBUCION_MESES_TOPE:]
    servicios = sorted({s for _, s in conteo})
    return {
        "meses": [f"{MESES_ES[m.month - 1]} {m.year}" for m in meses],
        "series": [
            {"servicio": s, "data": [conteo[(m, s)] for m in meses]}
            for s in servicios
        ],
    }


def treemap_servicio_ciudad(desde=None, hasta=None, servicio=None, ciudad=None) -> list[dict]:
    """Treemap servicio→ciudad · valor = personas evaluadas (B15, sin datos quemados)."""
    activas = _rango_reservas(desde, hasta, servicio, ciudad).filter(cancelada=False)
    grupos = (
        activas.values("servicio__nombre", "ciudad__nombre")
        .annotate(valor=Sum("personas"))
        .order_by("servicio__nombre", "-valor")
    )
    por_servicio: dict[str, list[dict]] = {}
    for g in grupos:
        hijos = por_servicio.setdefault(g["servicio__nombre"], [])
        hijos.append({"name": g["ciudad__nombre"], "value": g["valor"]})
    return [{"name": nombre, "children": hijos} for nombre, hijos in por_servicio.items()]


def sankey_servicio_ciudad_cliente(desde=None, hasta=None, servicio=None, ciudad=None) -> dict:
    """Sankey servicio→ciudad→cliente · valor = personas evaluadas."""
    activas = _rango_reservas(desde, hasta, servicio, ciudad).filter(cancelada=False)
    nodos: set[str] = set()
    servicio_ciudad: Counter = Counter()
    ciudad_cliente: Counter = Counter()
    for r in activas.select_related("servicio", "ciudad", "cliente"):
        nodos.update([r.servicio.nombre, r.ciudad.nombre, r.cliente.nombre])
        servicio_ciudad[(r.servicio.nombre, r.ciudad.nombre)] += r.personas
        ciudad_cliente[(r.ciudad.nombre, r.cliente.nombre)] += r.personas
    links = [{"source": s, "target": t, "value": v} for (s, t), v in servicio_ciudad.items()]
    links += [{"source": s, "target": t, "value": v} for (s, t), v in ciudad_cliente.items()]
    return {"nodes": [{"name": n} for n in nodos], "links": links}


def perfil_ciudades(desde=None, hasta=None, servicio=None, ciudad=None) -> dict:
    """Perfil operativo por ciudad · 5 dimensiones normalizadas a % del máximo
    entre las top-N ciudades por volumen (barras agrupadas — no es un radar,
    el propio prototipo origen ya documentaba ese cambio de diseño)."""
    activas = _rango_reservas(desde, hasta, servicio, ciudad).filter(cancelada=False)
    top_ciudades = [
        c["ciudad__nombre"]
        for c in activas.values("ciudad__nombre").annotate(n=Count("id")).order_by("-n")[:PERFIL_CIUDADES_TOPE]
    ]
    dims = ["reservas", "personas", "contactos", "riesgo_medio", "clientes_unicos"]
    datos: dict[str, dict] = {}
    for c in top_ciudades:
        qs = activas.filter(ciudad__nombre=c)
        n_reservas = qs.count()
        datos[c] = {
            "reservas": n_reservas,
            "personas": qs.aggregate(s=Sum("personas"))["s"] or 0,
            "contactos": qs.aggregate(s=Sum("contactos_efectivos"))["s"] or 0,
            "riesgo_medio": round((qs.aggregate(s=Sum("riesgo"))["s"] or 0) / n_reservas, 2) if n_reservas else 0,
            "clientes_unicos": qs.values("cliente").distinct().count(),
        }
    maximos = {d: max((datos[c][d] for c in top_ciudades), default=0) for d in dims}
    series = [
        {
            "name": c,
            "data": [round(100 * datos[c][d] / maximos[d]) if maximos[d] else 0 for d in dims],
        }
        for c in top_ciudades
    ]
    return {"dimensiones": dims, "ciudades": top_ciudades, "series": series}


def eficiencia_logistica() -> dict:
    """Días reales de retorno por servicio (confirmacion_retorno.fecha - fecha_salida),
    contra la meta de negocio (EFICIENCIA_META_DIAS). Reemplaza al bullet chart del
    prototipo origen, que eran valores fijos sin cálculo real."""
    dias_por_servicio: dict[str, list[int]] = {}
    qs = Reserva.objects.filter(confirmacion_retorno__isnull=False).select_related(
        "servicio", "confirmacion_retorno",
    )
    for r in qs:
        dias = (r.confirmacion_retorno.fecha - r.fecha_salida).days
        dias_por_servicio.setdefault(r.servicio.nombre, []).append(dias)
    servicios = sorted(dias_por_servicio)
    return {
        "servicios": servicios,
        "real": [round(sum(dias_por_servicio[s]) / len(dias_por_servicio[s]), 1) for s in servicios],
        "meta": EFICIENCIA_META_DIAS,
    }


def salud_backlog() -> int:
    """% de reservas activas con riesgo bajo (< 0.5) · gauge del Brief ejecutivo."""
    activas = Reserva.objects.filter(cancelada=False)
    total = activas.count()
    if not total:
        return 100
    en_riesgo = activas.filter(riesgo__gte=0.5).count()
    return round((1 - en_riesgo / total) * 100)


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


def kpis_base_ejecutivo() -> dict:
    """Fila "Base" del resumen ejecutivo: reservas activas y contactos efectivos
    de esta semana vs la anterior, reservas en riesgo, utilización de flota.
    En el prototipo origen esta fila era texto fijo (28+4, $741K "facturación
    proyectada" sin ninguna fórmula) — acá todo sale de la BD; se sustituyó la
    "facturación proyectada" (sin ningún dato de precio en el modelo) por
    utilización de flota, que sí es real."""
    hoy = timezone.localdate()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_semana_pasada = inicio_semana - timedelta(days=7)
    activas = Reserva.objects.filter(cancelada=False)

    def _en_rango(desde, hasta=None):
        qs = activas.filter(fecha_salida__gte=desde)
        return qs.filter(fecha_salida__lt=hasta) if hasta else qs

    reservas_semana = _en_rango(inicio_semana).count()
    reservas_semana_pasada = _en_rango(inicio_semana_pasada, inicio_semana).count()
    contactos_semana = _en_rango(inicio_semana).aggregate(s=Sum("contactos_efectivos"))["s"] or 0
    contactos_semana_pasada = (
        _en_rango(inicio_semana_pasada, inicio_semana).aggregate(s=Sum("contactos_efectivos"))["s"] or 0
    )
    en_riesgo = activas.filter(confirmacion_retorno__isnull=True, riesgo__gte=0.55).count()

    inventario = Equipo.objects.exclude(estado=EstadoEquipo.DE_BAJA)
    total_equipos = inventario.count()
    en_uso = inventario.filter(estado=EstadoEquipo.EN_USO).count()

    return {
        "reservas_semana": reservas_semana,
        "reservas_semana_delta": reservas_semana - reservas_semana_pasada,
        "contactos_semana": contactos_semana,
        "contactos_semana_delta": contactos_semana - contactos_semana_pasada,
        "reservas_en_riesgo": en_riesgo,
        "utilizacion_flota": round(100 * en_uso / total_equipos) if total_equipos else 0,
    }


def resumen_ejecutivo(findings: list[Finding] | None = None) -> dict:
    """Cima de la pirámide Minto (mensaje principal + 3 puntos de soporte +
    síntesis) construida a partir de los hallazgos REALES del motor. En el
    prototipo origen todo este bloque era texto fijo en el HTML, sin ninguna
    función que lo generara — acá se deriva de ``analizar()`` para que cambie
    con los datos reales."""
    if findings is None:
        findings = analizar()
    hoy = timezone.localdate()
    activas = Reserva.objects.filter(cancelada=False)
    cobertura = {
        "reservas": activas.count(),
        "clientes": activas.values("cliente").distinct().count(),
        "ciudades": activas.values("ciudad").distinct().count(),
    }
    principal = findings[0] if findings else None
    soporte = findings[1:4]
    confianza = "Alta" if len(findings) >= 3 else "Media" if findings else "Sin datos suficientes"  # noqa: PLR2004
    return {
        "actualizado": timezone.localtime(),
        "cobertura": cobertura,
        "confianza": confianza,
        "principal": principal,
        "soporte": soporte,
        "sintesis": [f for f in [principal, *soporte] if f][:3],
        "hoy": hoy,
    }


def resumen_recomendaciones(findings: list[Finding]) -> dict:
    """"Lectura ejecutiva del motor" + conteos por severidad para los filtros.
    En el prototipo origen los conteos de los botones eran texto fijo (nunca
    igual al array real de hallazgos) y el resumen citaba cifras hardcodeadas;
    acá todo sale de ``findings`` ya calculado por ``analizar()``."""
    criticos = [f for f in findings if f.severidad >= 4]  # noqa: PLR2004
    importantes = [f for f in findings if f.severidad == 3]  # noqa: PLR2004
    atencion = [f for f in findings if f.severidad <= 2]  # noqa: PLR2004
    partes = []
    if criticos:
        partes.append(f"{len(criticos)} hallazgo{_plural(len(criticos))} crítico{_plural(len(criticos))}")
    if importantes:
        partes.append(f"{len(importantes)} importante{_plural(len(importantes))}")
    if atencion:
        partes.append(f"{len(atencion)} de atención")
    if not findings:
        texto = "La operación está dentro de los umbrales configurados: los 11 detectores corrieron sin hallazgos."
    else:
        top = findings[0].titulo
        texto = f'El motor identificó {", ".join(partes)}. El hallazgo de mayor prioridad es: "{top}".'
    return {
        "criticos": len(criticos),
        "importantes": len(importantes),
        "atencion": len(atencion),
        "texto": texto,
        "actualizado": timezone.localtime(),
    }


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
