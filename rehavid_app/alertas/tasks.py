"""Tareas Celery de alertas logísticas (programadas con beat)."""

from celery import shared_task

from . import services


@shared_task(name="rehavid_app.alertas.tasks.detectar_y_notificar")
def detectar_y_notificar() -> int:
    """Detección periódica (ver CELERY_BEAT_SCHEDULE) + envío por canal activo."""
    return services.detectar_y_notificar()
