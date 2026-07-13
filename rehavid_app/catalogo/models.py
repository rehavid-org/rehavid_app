from django.db import models


class Servicio(models.Model):
    """Categoría de servicio/equipo de medición (Xsens, EMG, Tobii, …).

    Tumeke se modela con ``requiere_equipo_fisico=False``: siempre está
    disponible porque es software, no una unidad física del inventario.
    """

    nombre = models.CharField(max_length=60, unique=True)
    descripcion = models.TextField(blank=True)
    requiere_equipo_fisico = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "servicio"
        verbose_name_plural = "servicios"

    def __str__(self):
        return self.nombre


class Ciudad(models.Model):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "ciudad"
        verbose_name_plural = "ciudades"

    def __str__(self):
        return self.nombre


class Empresa(models.Model):
    """Empresa cliente o empleadora (ARL SURA, JD TASS, Rehavid S.A.S., …)."""

    nombre = models.CharField(max_length=120, unique=True)
    sector = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ["nombre"]
        verbose_name = "empresa"
        verbose_name_plural = "empresas"

    def __str__(self):
        return self.nombre


class AccesorioTipo(models.Model):
    """O16 · accesorio típico ofrecido al solicitar un servicio."""

    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.CASCADE,
        related_name="accesorios_tipicos",
    )
    nombre = models.CharField(max_length=120)
    cantidad_default = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["servicio", "nombre"]
        unique_together = [("servicio", "nombre")]
        verbose_name = "accesorio típico"
        verbose_name_plural = "accesorios típicos"

    def __str__(self):
        return f"{self.servicio} · {self.nombre}"
