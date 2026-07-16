"""Predictivo MSK: mock heurístico ↔ Azure ML por settings (B16).

Puerto del ``prediccion_service.py`` del prototipo. El frontend recibe la
misma estructura en ambos modos; solo cambia ``es_simulacion``. Si el
endpoint real falla, cae al mock automáticamente.
"""

import logging
import random
from collections import defaultdict

import requests
from django.conf import settings

from .models import PrediccionRegistro

logger = logging.getLogger(__name__)

SCORE_TOPE = 0.92
TIMEOUT_SEGUNDOS = 10
BINS_RIESGO = 5  # bins de 20 puntos: 0-20, 20-40, 40-60, 60-80, 80-100
TRAYECTORIA_TOPE = 8  # últimas N evaluaciones por cliente

# Zonas anatómicas · heurística de simulación (NO viene de un modelo entrenado ni
# de mediciones reales; es un peso base + ajuste por servicio, igual de honesto
# que el resto del módulo, que ya se declara `es_simulacion`). Sirve para que el
# panel poblacional tenga una estructura real de datos que se llena con el uso,
# en vez de copiar los números fijos que el prototipo origen admite son inventados.
ZONAS_BASE = {
    "cuello": 30, "hombro_d": 30, "hombro_i": 28, "codo_d": 22, "codo_i": 20,
    "mano_d": 32, "mano_i": 30, "lumbar": 35, "cadera": 18, "rodilla_d": 20, "rodilla_i": 18,
}
ZONAS_LABEL = {
    "cuello": "Cuello", "hombro_d": "Hombro D", "hombro_i": "Hombro I",
    "codo_d": "Codo D", "codo_i": "Codo I", "mano_d": "Mano D", "mano_i": "Mano I",
    "lumbar": "Lumbar", "cadera": "Cadera", "rodilla_d": "Rodilla D", "rodilla_i": "Rodilla I",
}
# Ajuste por servicio: qué zonas se acentúan según el instrumento usado
ZONAS_POR_SERVICIO = {
    "Xsens": {"lumbar": 25, "hombro_d": 15, "hombro_i": 15},
    "EMG": {"mano_d": 20, "mano_i": 20, "codo_d": 12, "codo_i": 12},
    "Tobii": {"cuello": 25},
    "Dinamómetro": {"mano_d": 22, "mano_i": 22},
}


def _zonas_mock(entrada: dict) -> dict:
    """Score simulado (0-100) por zona anatómica para esta predicción individual."""
    ajuste = ZONAS_POR_SERVICIO.get(entrada["servicio"], {})
    return {
        zona: min(100, round(base + ajuste.get(zona, 0) + random.uniform(-6, 6)))  # noqa: S311
        for zona, base in ZONAS_BASE.items()
    }


def _factores_reales(entrada: dict) -> tuple[float, list[dict]]:
    """Heurística real, NO un modelo entrenado: cada "factor" es un término
    de la misma fórmula que calcula el score (incluido el historial real del
    cliente en BD), así que el peso relativo cambia con el input en vez de
    mostrar siempre la misma tabla fija."""
    from rehavid_app.reservas.models import Reserva  # noqa: PLC0415

    personas = entrada["personas"]
    servicio = entrada["servicio"]
    sector = (entrada.get("sector") or "").lower()
    jornada = (entrada.get("jornada") or "").lower()
    cliente = entrada.get("cliente") or ""

    historial = Reserva.objects.filter(cliente__nombre=cliente).count()

    base = 0.12
    contrib_personas = min(0.35, personas * 0.03)
    contrib_servicio = 0.08 if servicio == "Xsens" else 0.05 if servicio == "EMG" else 0.02
    contrib_sector = 0.10 if ("manufactura" in sector or "agro" in sector) else 0.03
    contrib_jornada = 0.06 if "rotativ" in jornada else 0.0
    contrib_historial = min(0.15, historial * 0.01)

    score = base + contrib_personas + contrib_servicio + contrib_sector + contrib_jornada + contrib_historial

    contribuciones = [
        ("N° personas en estudio", contrib_personas, "A más personas en el estudio, mayor riesgo agregado"),
        ("Historial del cliente", contrib_historial, f"{historial} reserva(s) previas registradas con Rehavid"),
        ("Sector industrial del cliente", contrib_sector, "Manufactura/agroindustria elevan el riesgo"),
        ("Tipo de jornada (turnos)", contrib_jornada, "Turnos rotativos elevan el riesgo"),
        ("Servicio asignado", contrib_servicio, "Xsens y EMG tienen mayor sensibilidad de detección"),
    ]
    total = sum(v for _, v, _ in contribuciones) or 1
    factores = [
        {"name": nombre, "value": round(100 * valor / total), "expl": expl}
        for nombre, valor, expl in sorted(contribuciones, key=lambda c: c[1], reverse=True)
        if valor > 0
    ]
    return min(SCORE_TOPE, score), factores


def _mock_prediccion(entrada: dict) -> dict:
    """Heurística real basada en el input + historial de BD (mismo espíritu
    "simulación" del prototipo, pero los factores sí varían con cada
    predicción en vez de una tabla fija idéntica siempre)."""
    score, factores = _factores_reales(entrada)
    return {
        "es_simulacion": True,
        "score": round(score, 3),
        "modelo_version": "mockup-v1",
        "factores": factores,
        "zonas": _zonas_mock(entrada),
    }


def _real_prediccion(entrada: dict) -> dict:
    """Llama al endpoint de Azure ML desplegado (score + factores SHAP)."""
    headers = {
        "Authorization": f"Bearer {settings.AZURE_ML_KEY}",
        "Content-Type": "application/json",
        "azureml-model-deployment": settings.AZURE_ML_DEPLOYMENT,
    }
    payload = {
        "input_data": {
            "columns": ["servicio", "ciudad", "cliente", "personas", "sector", "jornada"],
            "data": [[
                entrada["servicio"],
                entrada["ciudad"],
                entrada["cliente"],
                entrada["personas"],
                entrada.get("sector", ""),
                entrada.get("jornada", ""),
            ]],
        },
    }
    resp = requests.post(settings.AZURE_ML_ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT_SEGUNDOS)
    resp.raise_for_status()
    data = resp.json()
    return {
        "es_simulacion": False,
        "score": float(data["score"]),
        "modelo_version": data.get("modelo_version", settings.AZURE_ML_DEPLOYMENT),
        "factores": data.get("factores", []),
        "zonas": data.get("zonas", {}),
    }


def obtener_prediccion(entrada: dict, usuario=None) -> dict:
    """Azure ML si está habilitado (con fallback al mock) y registra el score."""
    if not settings.AZURE_ML_ENABLED:
        resultado = _mock_prediccion(entrada)
    else:
        try:
            resultado = _real_prediccion(entrada)
        except (requests.RequestException, KeyError, ValueError):
            logger.exception("Azure ML falló; usando mock")
            resultado = _mock_prediccion(entrada)

    PrediccionRegistro.objects.create(
        usuario=usuario if usuario is not None and usuario.is_authenticated else None,
        servicio=entrada["servicio"],
        ciudad=entrada["ciudad"],
        cliente=entrada["cliente"],
        personas=entrada["personas"],
        sector=entrada.get("sector", ""),
        jornada=entrada.get("jornada", ""),
        score=resultado["score"],
        modelo_version=resultado["modelo_version"],
        es_simulacion=resultado["es_simulacion"],
        factores=resultado["factores"],
        zonas=resultado.get("zonas", {}),
    )
    return resultado


# ────────────────────────────────────────────────────────────
# Panel poblacional · agregados reales sobre PrediccionRegistro y Reserva.
# Arrancan vacíos/en cero si aún no hay datos y se van llenando con el uso.
# ────────────────────────────────────────────────────────────
def distribucion_riesgo() -> dict:
    """Histograma de `Reserva.riesgo` en bins de 20 puntos (0-20 … 80-100)."""
    from rehavid_app.reservas.models import Reserva  # noqa: PLC0415

    bins = [0] * BINS_RIESGO
    for riesgo in Reserva.objects.values_list("riesgo", flat=True):
        idx = min(BINS_RIESGO - 1, int(riesgo * BINS_RIESGO))
        bins[idx] += 1
    etiquetas = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
    return {"etiquetas": etiquetas, "conteos": bins, "con_datos": any(bins)}


def diagrama_corporal_poblacional() -> dict:
    """Score promedio por zona anatómica sobre todas las predicciones acumuladas
    (vacío/en 0 si aún no hay ninguna) + ranking top-5."""
    sumas: dict[str, float] = dict.fromkeys(ZONAS_BASE, 0.0)
    conteos: dict[str, int] = dict.fromkeys(ZONAS_BASE, 0)
    for zonas in PrediccionRegistro.objects.exclude(zonas={}).values_list("zonas", flat=True):
        for zona, score in zonas.items():
            if zona in sumas:
                sumas[zona] += score
                conteos[zona] += 1
    promedios = {z: round(sumas[z] / conteos[z], 1) if conteos[z] else 0 for z in ZONAS_BASE}
    ranking = sorted(promedios.items(), key=lambda kv: kv[1], reverse=True)
    return {
        "zonas": [{"id": z, "nombre": ZONAS_LABEL[z], "score": s} for z, s in promedios.items()],
        "top5": [{"id": z, "nombre": ZONAS_LABEL[z], "score": s} for z, s in ranking[:5]],
        "con_datos": any(conteos.values()),
    }


def trayectoria_por_cliente() -> dict:
    """Últimas N evaluaciones por cliente (con al menos 1 registro) + banda
    P25-P75 de todos los scores históricos en cada posición."""
    por_cliente: dict[str, list[float]] = defaultdict(list)
    registros = PrediccionRegistro.objects.order_by("cliente", "creado_en").values_list(
        "cliente", "score",
    )
    for cliente, score in registros:
        por_cliente[cliente].append(score)

    clientes = {c: scores[-TRAYECTORIA_TOPE:] for c, scores in por_cliente.items() if scores}
    max_len = max((len(v) for v in clientes.values()), default=0)
    banda_sup, banda_inf = [], []
    for i in range(max_len):
        columna = sorted(v[i] for v in clientes.values() if len(v) > i)
        if columna:
            banda_inf.append(round(columna[len(columna) // 4], 3))
            banda_sup.append(round(columna[(3 * len(columna)) // 4], 3))
        else:
            banda_inf.append(None)
            banda_sup.append(None)
    return {
        "ejes": [f"Eval {i + 1}" for i in range(max_len)],
        "clientes": [{"nombre": c, "scores": scores} for c, scores in clientes.items()],
        "banda_inferior": banda_inf,
        "banda_superior": banda_sup,
    }
