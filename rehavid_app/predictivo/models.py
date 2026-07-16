from django.conf import settings
from django.db import models


class PrediccionRegistro(models.Model):
    """Historial de scores calculados (mock o Azure ML)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="predicciones",
    )
    servicio = models.CharField(max_length=60)
    ciudad = models.CharField(max_length=80)
    cliente = models.CharField(max_length=120)
    personas = models.PositiveIntegerField()
    sector = models.CharField(max_length=80, blank=True)
    jornada = models.CharField(max_length=80, blank=True)
    score = models.FloatField()
    modelo_version = models.CharField(max_length=40)
    es_simulacion = models.BooleanField(default=True)
    factores = models.JSONField(default=list, blank=True)
    zonas = models.JSONField(default=dict, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado_en"]
        verbose_name = "registro de predicción"
        verbose_name_plural = "registros de predicción"

    def __str__(self):
        return f"{self.servicio} · {self.cliente} · {self.score:.2f}"
