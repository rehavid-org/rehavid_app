from django.conf import settings
from django.db import models


class Canal(models.TextChoices):
    WHATSAPP = "whatsapp", "WhatsApp Business"
    EMAIL = "email", "Correo logística"
    TEAMS = "teams", "Microsoft Teams"


class ConfiguracionCanal(models.Model):
    """O21/B10 · configuración de un canal de notificación (modelo propio,
    ya no un documento mágico dentro del container de solicitudes)."""

    canal = models.CharField(max_length=12, choices=Canal.choices, unique=True)
    activo = models.BooleanField(default=False)
    label = models.CharField(max_length=60, blank=True)
    destino = models.CharField(
        max_length=200,
        blank=True,
        help_text="Número de teléfono, correo o nombre del canal Teams",
    )

    class Meta:
        ordering = ["canal"]
        verbose_name = "configuración de canal"
        verbose_name_plural = "configuración de canales"

    def __str__(self):
        return f"{self.get_canal_display()} · {'activo' if self.activo else 'inactivo'}"


class AlertaEnviada(models.Model):
    """Registro de cada alerta disparada por un canal."""

    tipo = models.CharField(max_length=30)  # transito_salida, retorno_vencido, mantencion, preparacion
    canal = models.CharField(max_length=12, choices=Canal.choices)
    mensaje = models.TextField()
    destino = models.CharField(max_length=200, blank=True)
    enviada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alertas_enviadas",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    resultado = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "alerta enviada"
        verbose_name_plural = "alertas enviadas"

    def __str__(self):
        return f"{self.tipo} → {self.canal} ({self.timestamp:%Y-%m-%d %H:%M})"
