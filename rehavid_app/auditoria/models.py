from django.conf import settings
from django.db import models


class EventoAuditoria(models.Model):
    """B12 · evento real de auditoría; lo escriben las acciones de negocio."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eventos_auditoria",
    )
    # Copia desnormalizada para conservar el rastro si el usuario se elimina
    user_email = models.EmailField(blank=True)
    user_nombre = models.CharField(max_length=255, blank=True)
    accion = models.CharField(max_length=60, db_index=True)
    modulo = models.CharField(max_length=40, db_index=True)
    detalle = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "evento de auditoría"
        verbose_name_plural = "eventos de auditoría"

    def __str__(self):
        return f"{self.user_email} · {self.accion} · {self.timestamp:%Y-%m-%d %H:%M}"
