from django.db import models

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Servicio


class EstadoEquipo(models.TextChoices):
    DISPONIBLE = "disponible", "Disponible"
    EN_USO = "en_uso", "En uso"
    EN_PREPARACION = "en_preparacion", "En preparación"
    EN_REVISION = "en_revision", "En revisión"
    EN_MANTENIMIENTO = "en_mantenimiento", "En mantenimiento"
    EN_TRANSITO = "en_transito", "En tránsito"
    DE_BAJA = "de_baja", "De baja"


class Equipo(models.Model):
    """Unidad física del inventario, trackeada por serial (R005).

    Modelo canónico único (corrige B7): el alta manual, el import Excel y
    el seed crean exactamente este shape.
    """

    codigo = models.CharField("código", max_length=20, unique=True)  # XS-01
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="equipos",
        help_text="Categoría del equipo (Xsens, EMG, …)",
    )
    modelo = models.CharField(max_length=120)
    serial = models.CharField(max_length=60, unique=True)
    estado = models.CharField(
        max_length=20,
        choices=EstadoEquipo.choices,
        default=EstadoEquipo.DISPONIBLE,
        db_index=True,
    )
    responsable = models.CharField(max_length=120, blank=True)
    ciudad_base = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name="equipos",
    )
    ultima_revision = models.DateField(null=True, blank=True)
    proxima_mantencion = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)
    historial_uso = models.PositiveIntegerField(default=0)
    motivo_mantenimiento = models.TextField(blank=True)
    # O18 · baja definitiva
    motivo_baja = models.TextField(blank=True)
    fecha_baja = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "equipo"
        verbose_name_plural = "equipos"

    def __str__(self):
        return f"{self.codigo} · {self.modelo}"

    @property
    def operativo(self) -> bool:
        """Estados que permiten considerar el equipo para reservas (R009/O18)."""
        return self.estado not in {
            EstadoEquipo.EN_MANTENIMIENTO,
            EstadoEquipo.EN_TRANSITO,
            EstadoEquipo.DE_BAJA,
        }


class Accesorio(models.Model):
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name="accesorios",
    )
    nombre = models.CharField(max_length=120)
    cantidad = models.PositiveIntegerField(default=1)
    completo = models.BooleanField(default=True)
    requiere_lavado = models.BooleanField(default=False)
    consumible = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]
        verbose_name = "accesorio"
        verbose_name_plural = "accesorios"

    def __str__(self):
        return f"{self.nombre} ×{self.cantidad}"
