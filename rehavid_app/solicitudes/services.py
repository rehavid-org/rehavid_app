"""Flujos del portal solicitante y la bandeja del operador (O11/O16/O17/O19).

Correcciones aplicadas al portar:
- B2 · atender una solicitud CREA la reserva en la misma transacción
- B4 · ``fecha_sugerida`` se persiste (campo obligatorio del modelo)
- B5 · la regla 48h compara contra la fecha programada del SERVICIO,
  no contra el día en que el operador confirmó.
"""

from datetime import datetime
from datetime import time
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from rehavid_app.auditoria import services as auditoria
from rehavid_app.reservas import services as reservas_service
from rehavid_app.reservas.models import Reserva

from .models import AccesorioSolicitado
from .models import EstadoSolicitud
from .models import Observacion
from .models import Solicitud

# O17 · destinatarios de la notificación de solicitud nueva
NOTIFICAR_A = ["operaciones@rehavid.com.co", "liliana.hernandez@rehavid.com.co"]

HORAS_MINIMAS_CANCELACION = 48


class SolicitudError(Exception):
    """Error de negocio con mensaje apto para mostrar al usuario."""


@transaction.atomic
def crear_solicitud(
    *,
    solicitante,
    empresa_cliente,
    servicio,
    ciudad,
    personas: int,
    fecha_sugerida,
    dias_estimados: int,
    notas: str = "",
    profesional: dict | None = None,
    accesorios: list[dict] | None = None,
) -> Solicitud:
    """Crea la solicitud desde el portal (nivel 4). B4: persiste la fecha pedida."""
    profesional = profesional or {}
    solicitud = Solicitud.objects.create(
        solicitante=solicitante,
        empresa_cliente=empresa_cliente,
        servicio=servicio,
        ciudad=ciudad,
        personas=personas,
        fecha_sugerida=fecha_sugerida,
        dias_estimados=dias_estimados,
        notas=notas,
        prof_cantidad=profesional.get("cantidad", 1),
        prof_perfil=profesional.get("perfil", ""),
        prof_nombre=profesional.get("nombre", ""),
        prof_especialidad=profesional.get("especialidad", ""),
        prof_telefono=profesional.get("telefono", ""),
        prof_correo=profesional.get("correo", ""),
        notificada_a=NOTIFICAR_A,
        notificada_en=timezone.now(),
    )
    AccesorioSolicitado.objects.bulk_create(
        AccesorioSolicitado(
            solicitud=solicitud,
            nombre=a["nombre"],
            cantidad=a.get("cantidad", 1),
        )
        for a in (accesorios or [])
        if a.get("cantidad", 1)
    )
    auditoria.registrar(
        solicitante, "crear_solicitud", "solicitudes",
        f"{solicitud.codigo} · {servicio} · {empresa_cliente}",
    )
    return solicitud


def _fecha_programada(solicitud: Solicitud):
    """B5 · fecha real del servicio: la reserva vinculada si existe, si no la sugerida."""
    reserva = solicitud.reservas.filter(cancelada=False).order_by("fecha_salida").first()
    return reserva.fecha_salida if reserva else solicitud.fecha_sugerida


def puede_cancelar_48h(solicitud: Solicitud) -> bool:
    """True si faltan al menos 48h para la fecha programada del servicio."""
    fecha = _fecha_programada(solicitud)
    limite = timezone.now() + timedelta(hours=HORAS_MINIMAS_CANCELACION)
    return timezone.make_aware(datetime.combine(fecha, time.min)) >= limite


@transaction.atomic
def cancelar_solicitud(solicitud: Solicitud, motivo: str, usuario) -> Solicitud:
    """O11 · cancela la solicitud propia; nivel 4 respeta la regla de 48h (B5)."""
    if solicitud.estado == EstadoSolicitud.CANCELADA:
        msg = "Ya estaba cancelada"
        raise SolicitudError(msg)
    if solicitud.estado == EstadoSolicitud.FINALIZADA:
        msg = "Solicitudes finalizadas no se pueden cancelar"
        raise SolicitudError(msg)

    if (
        solicitud.estado == EstadoSolicitud.CONFIRMADA
        and usuario.nivel == 4
        and not puede_cancelar_48h(solicitud)
    ):
        msg = "No se puede cancelar · faltan menos de 48 horas para el servicio. Contacte al coordinador."
        raise SolicitudError(msg)

    solicitud.estado = EstadoSolicitud.CANCELADA
    solicitud.motivo_cancelacion = motivo
    solicitud.cancelada_por = usuario
    solicitud.fecha_cancelacion = timezone.localdate()
    solicitud.save(update_fields=["estado", "motivo_cancelacion", "cancelada_por", "fecha_cancelacion"])

    # Si la solicitud ya tenía reserva creada, se cancela también
    for reserva in solicitud.reservas.filter(cancelada=False):
        reservas_service.cancelar_reserva(
            reserva, f"Solicitud {solicitud.codigo} cancelada · {motivo}", usuario,
        )

    auditoria.registrar(usuario, "cancelar_solicitud", "solicitudes", f"{solicitud.codigo} · {motivo}")
    return solicitud


@transaction.atomic
def editar_solicitud(solicitud: Solicitud, usuario, personas=None, notas=None) -> Solicitud:
    """O11 · solo solicitudes pendientes admiten edición."""
    if solicitud.estado != EstadoSolicitud.PENDIENTE:
        msg = "Solo se pueden editar solicitudes pendientes"
        raise SolicitudError(msg)
    if personas is not None:
        solicitud.personas = personas
    if notas is not None:
        solicitud.notas = notas
    solicitud.editada = True
    solicitud.editada_por = usuario
    solicitud.save()
    auditoria.registrar(usuario, "editar_solicitud", "solicitudes", solicitud.codigo)
    return solicitud


def agregar_observacion(solicitud: Solicitud, texto: str, usuario) -> Observacion:
    """O11 · observación sobre una solicitud (típicamente confirmada)."""
    obs = Observacion.objects.create(solicitud=solicitud, autor=usuario, texto=texto)
    auditoria.registrar(usuario, "observacion_solicitud", "solicitudes", f"{solicitud.codigo} · {texto[:60]}")
    return obs


# ────────────────────────────────────────────────────────────
# B2 · Atender = confirmar + CREAR LA RESERVA (transaccional)
# ────────────────────────────────────────────────────────────
@transaction.atomic
def atender_solicitud(solicitud: Solicitud, operador) -> Reserva:
    """El operador atiende una pendiente: valida stock, crea la Reserva
    vinculada y confirma la solicitud. Si no hay stock, ReservaError y
    la solicitud queda pendiente (la transacción revierte)."""
    if solicitud.estado != EstadoSolicitud.PENDIENTE:
        msg = f"Estado actual: {solicitud.get_estado_display()}. Solo pendientes son atendibles."
        raise SolicitudError(msg)

    fecha_salida = solicitud.fecha_sugerida
    fecha_retorno = fecha_salida + timedelta(days=max(solicitud.dias_estimados - 1, 0))

    reserva = reservas_service.crear_reserva(
        servicio=solicitud.servicio,
        cliente=solicitud.empresa_cliente,
        ciudad=solicitud.ciudad,
        personas=solicitud.personas,
        fecha_salida=fecha_salida,
        fecha_retorno_esp=fecha_retorno,
        usuario=operador,
        solicitud=solicitud,
    )

    solicitud.estado = EstadoSolicitud.CONFIRMADA
    solicitud.operador = operador
    solicitud.fecha_confirmada = timezone.localdate()
    solicitud.save(update_fields=["estado", "operador", "fecha_confirmada"])

    auditoria.registrar(
        operador, "atender_solicitud", "solicitudes",
        f"{solicitud.codigo} → {reserva.codigo}",
    )
    return reserva


def contar_pendientes() -> int:
    """O17 · badge del menú del operador."""
    return Solicitud.objects.filter(estado=EstadoSolicitud.PENDIENTE).count()
