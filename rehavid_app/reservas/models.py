from django.conf import settings
from django.db import models

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio
from rehavid_app.equipos.models import Equipo
from rehavid_app.paquetes.models import Paquete


class EstadoReserva(models.TextChoices):
    CONFIRMADA = "confirmada", "Confirmada"
    PLANEADA = "planeada", "Planeada"


class Reserva(models.Model):
    """Reserva de equipos para un servicio en campo (núcleo, R002-R009)."""

    codigo = models.CharField("código", max_length=20, unique=True, blank=True)  # R-001
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    cliente = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name="reservas",
    )
    personas = models.PositiveIntegerField()
    contactos_efectivos = models.PositiveIntegerField(default=0)
    fecha_salida = models.DateField(db_index=True)
    fecha_retorno_esp = models.DateField("fecha retorno esperada", db_index=True)
    estado = models.CharField(
        max_length=12,
        choices=EstadoReserva.choices,
        default=EstadoReserva.CONFIRMADA,
    )
    cancelada = models.BooleanField(default=False, db_index=True)
    motivo_cancelacion = models.TextField(blank=True)
    reprogramada_desde = models.DateField(null=True, blank=True)
    # O08 · un equipo por categoría del paquete; reservas simples llevan uno
    equipos = models.ManyToManyField(
        Equipo,
        blank=True,
        related_name="reservas",
    )
    paquete = models.ForeignKey(
        Paquete,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas",
    )
    # B2 · reserva creada al atender una solicitud queda vinculada a ella
    solicitud = models.ForeignKey(
        "solicitudes.Solicitud",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservas",
    )
    riesgo = models.FloatField(default=0.0)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_salida"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"

    def __str__(self):
        return f"{self.codigo} · {self.servicio} · {self.cliente}"

    def save(self, *args, **kwargs):
        # B6 · código legible derivado del PK autoincremental (sin COUNT(1))
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.codigo:
            self.codigo = f"R-{self.pk:03d}"
            super().save(update_fields=["codigo"])

    @property
    def activa(self) -> bool:
        """Activa = no cancelada y sin retorno confirmado."""
        return not self.cancelada and not hasattr(self, "confirmacion_retorno")


class ConfirmacionRetorno(models.Model):
    """R007 · confirmación de retorno del kit (OK/INCOMPLETO/DAÑADO)."""

    class EstadoKit(models.TextChoices):
        OK = "OK", "OK"
        INCOMPLETO = "INCOMPLETO", "Incompleto"
        DANADO = "DAÑADO", "Dañado"

    reserva = models.OneToOneField(
        Reserva,
        on_delete=models.CASCADE,
        related_name="confirmacion_retorno",
    )
    fecha = models.DateField()
    estado_kit = models.CharField(
        max_length=12,
        choices=EstadoKit.choices,
        default=EstadoKit.OK,
    )
    notas = models.TextField(blank=True)
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retornos_confirmados",
    )
    requiere_preparacion = models.BooleanField(default=False)
    preparacion_completa = models.BooleanField(default=False)
    preparacion_notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "confirmación de retorno"
        verbose_name_plural = "confirmaciones de retorno"

    def __str__(self):
        return f"{self.reserva_id} · {self.estado_kit}"


class HistorialReserva(models.Model):
    """R002 · rastro de auditoría por reserva (creación, cambios, retorno)."""

    reserva = models.ForeignKey(
        Reserva,
        on_delete=models.CASCADE,
        related_name="historial",
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=40)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="acciones_reserva",
    )
    detalle = models.TextField(blank=True)

    class Meta:
        ordering = ["timestamp"]
        verbose_name = "historial de reserva"
        verbose_name_plural = "historial de reservas"

    def __str__(self):
        return f"{self.reserva_id} · {self.accion}"
