"""Endpoints de infraestructura (health check del contenedor)."""

from django.db import connection
from django.http import JsonResponse


def health(request):
    """Usado por el HEALTHCHECK de Docker y el probe de Azure App Service."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # noqa: BLE001 · el probe solo necesita saber que NO está sano
        return JsonResponse({"status": "error", "database": "unreachable"}, status=503)
    return JsonResponse({"status": "ok"})
