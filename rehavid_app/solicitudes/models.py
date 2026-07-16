from django.conf import settings
from django.db import models
from django.utils import timezone

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio


class EstadoSolicitud(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    CONFIRMADA = "confirmada", "Confirmada"
    FINALIZADA = "finalizada", "Finalizada"
    CANCELADA = "cancelada", "Cancelada"


class Solicitud(models.Model):
    """Solicitud de servicio creada desde el portal solicitante (nivel 4)."""

    codigo = models.CharField("código", max_length=20, unique=True, blank=True)  # SOL-001
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    empresa_cliente = models.ForeignKey(
        Empresa,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    servicio = models.ForeignKey(
        Servicio,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    ciudad = models.ForeignKey(
        Ciudad,
        on_delete=models.PROTECT,
        related_name="solicitudes",
    )
    personas = models.PositiveIntegerField()
    fecha_solicitud = models.DateField(auto_now_add=True)
    # B4 · la fecha que el cliente pidió para el servicio; antes se descartaba
    fecha_sugerida = models.DateField()
    dias_estimados = models.PositiveIntegerField(default=1)
    fecha_confirmada = models.DateField(null=True, blank=True)
    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_atendidas",
    )
    estado = models.CharField(
        max_length=12,
        choices=EstadoSolicitud.choices,
        default=EstadoSolicitud.PENDIENTE,
        db_index=True,
    )
    notas = models.TextField(blank=True)

    # O19 · profesional requerido
    prof_cantidad = models.PositiveIntegerField("profesionales requeridos", default=1)
    prof_perfil = models.CharField("perfil del profesional", max_length=120)
    prof_nombre = models.CharField("nombre del profesional", max_length=120, blank=True)
    prof_especialidad = models.CharField(max_length=120, blank=True)
    prof_telefono = models.CharField(max_length=30, blank=True)
    prof_correo = models.EmailField(blank=True)

    # Cancelación
    motivo_cancelacion = models.TextField(blank=True)
    cancelada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_canceladas",
    )
    fecha_cancelacion = models.DateField(null=True, blank=True)

    # Edición
    editada = models.BooleanField(default=False)
    editada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="solicitudes_editadas",
    )

    # O17 · notificación a operadores
    notificada_a = models.JSONField(default=list, blank=True)
    notificada_en = models.DateTimeField(null=True, blank=True)

    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada_en"]
        verbose_name = "solicitud"
        verbose_name_plural = "solicitudes"

    def __str__(self):
        return f"{self.codigo} · {self.empresa_cliente} · {self.servicio}"

    def save(self, *args, **kwargs):
        # B6 · código legible derivado del PK autoincremental (sin COUNT(1))
        creating = self.pk is None
        super().save(*args, **kwargs)
        if creating and not self.codigo:
            self.codigo = f"SOL-{self.pk:03d}"
            super().save(update_fields=["codigo"])

    def estado_visual(self) -> str:
        """Matiz de presentación: una solicitud confirmada cuya reserva vinculada
        está en su ventana de ejecución se muestra como "en_curso". No es un
        estado persistido — la máquina de estados real sigue siendo la de
        ``EstadoSolicitud`` (B2/B5); esto solo mejora lo que ve el usuario."""
        if self.estado == EstadoSolicitud.CONFIRMADA:
            hoy = timezone.localdate()
            reserva = self.reservas.filter(cancelada=False).first()
            if (
                reserva is not None
                and reserva.fecha_salida <= hoy <= reserva.fecha_retorno_esp
                and not hasattr(reserva, "confirmacion_retorno")
            ):
                return "en_curso"
        return self.estado

    def estado_visual_display(self) -> str:
        if self.estado_visual() == "en_curso":
            return "En curso"
        return self.get_estado_display()


class AccesorioSolicitado(models.Model):
    """O16 · accesorio pedido dentro de la solicitud."""

    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name="accesorios_solicitados",
    )
    nombre = models.CharField(max_length=120)
    cantidad = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]
        verbose_name = "accesorio solicitado"
        verbose_name_plural = "accesorios solicitados"

    def __str__(self):
        return f"{self.nombre} ×{self.cantidad}"  # noqa: RUF001


class Observacion(models.Model):
    """O11 · observación del solicitante sobre una solicitud confirmada."""

    solicitud = models.ForeignKey(
        Solicitud,
        on_delete=models.CASCADE,
        related_name="observaciones",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="observaciones_solicitud",
    )
    texto = models.TextField()

    class Meta:
        ordering = ["fecha"]
        verbose_name = "observación"
        verbose_name_plural = "observaciones"

    def __str__(self):
        return f"{self.solicitud_id} · {self.texto[:40]}"
