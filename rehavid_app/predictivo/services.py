"""Predictivo MSK: mock heurístico ↔ Azure ML por settings (B16).

Puerto del ``prediccion_service.py`` del prototipo. El frontend recibe la
misma estructura en ambos modos; solo cambia ``es_simulacion``. Si el
endpoint real falla, cae al mock automáticamente.
"""

import logging

import requests
from django.conf import settings

from .models import PrediccionRegistro

logger = logging.getLogger(__name__)

SCORE_TOPE = 0.92
TIMEOUT_SEGUNDOS = 10

FACTORES_MOCK = [
    {"name": "N° personas en estudio", "value": 28, "expl": "A más personas, mayor riesgo"},
    {"name": "Sector industrial del cliente", "value": 21, "expl": "Manufactura > administrativo"},
    {"name": "Historial del cliente", "value": 19, "expl": "Quien ya tuvo hallazgos repite"},
    {"name": "Tipo de jornada (turnos)", "value": 16, "expl": "Rotativos elevan el riesgo"},
    {"name": "Antigüedad del cliente", "value": 13, "expl": "Nuevos = más expuestos"},
    {"name": "Servicio asignado", "value": 11, "expl": "Xsens detecta más"},
]


def _mock_prediccion(entrada: dict) -> dict:
    """Heurística simple, NO un modelo entrenado (misma del prototipo)."""
    base = 0.18 + entrada["personas"] * 0.04
    if entrada["servicio"] == "Xsens":
        base += 0.08
    if entrada["servicio"] == "EMG":
        base += 0.05
    sector = (entrada.get("sector") or "").lower()
    if "manufactura" in sector or "agro" in sector:
        base += 0.10
    return {
        "es_simulacion": True,
        "score": round(min(SCORE_TOPE, base), 3),
        "modelo_version": "mockup-v0",
        "factores": FACTORES_MOCK,
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
    )
    return resultado
