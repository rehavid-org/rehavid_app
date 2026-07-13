from django.db import models

from rehavid_app.catalogo.models import Servicio


class Paquete(models.Model):
    """Combo multi-equipo (R006/O08): reserva un equipo por cada servicio requerido."""

    codigo = models.CharField("código", max_length=20, unique=True)  # PKG-01
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    servicios_requeridos = models.ManyToManyField(
        Servicio,
        related_name="paquetes",
    )
    duracion_dias = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "paquete"
        verbose_name_plural = "paquetes"

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"
