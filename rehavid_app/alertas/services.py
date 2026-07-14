"""Alertas logísticas (O21): 4 detectores + envío por canal.

Detección = porte del ``/alertas/detectadas`` del prototipo. El envío por
email es real (django-anymail/SMTP según settings); WhatsApp y Teams son
stubs documentados que registran el intento en ``AlertaEnviada`` hasta que
Rehavid contrate las integraciones (WhatsApp Business API / Graph API).
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from rehavid_app.auditoria import services as auditoria
from rehavid_app.equipos.models import Equipo
from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.reservas.models import Reserva

from .models import AlertaEnviada
from .models import Canal
from .models import ConfiguracionCanal

logger = logging.getLogger(__name__)

DIAS_DESPACHO = 2
DIAS_MANTENCION = 14


def detectar_alertas() -> list[dict]:
    """Los 4 detectores del prototipo, contra la BD y con fecha real (B9)."""
    hoy = timezone.localdate()
    alertas = []

    proximas = Reserva.objects.filter(
        cancelada=False,
        fecha_salida__gte=hoy,
        fecha_salida__lte=hoy + timedelta(days=DIAS_DESPACHO),
    ).count()
    if proximas:
        alertas.append({
            "tipo": "transito_salida",
            "titulo": "Equipos por despachar",
            "cantidad": proximas,
            "icono": "🚚",
            "canal_sugerido": Canal.WHATSAPP,
            "detalle": f"{proximas} reservas inician en las próximas 48h",
        })

    vencidos = Reserva.objects.filter(
        cancelada=False,
        confirmacion_retorno__isnull=True,
        fecha_retorno_esp__lt=hoy,
    ).count()
    if vencidos:
        alertas.append({
            "tipo": "retorno_vencido",
            "titulo": "Retornos vencidos",
            "cantidad": vencidos,
            "icono": "⚠",
            "canal_sugerido": Canal.WHATSAPP,
            "detalle": f"{vencidos} equipos no han confirmado retorno",
        })

    mantenciones = Equipo.objects.filter(
        proxima_mantencion__gte=hoy,
        proxima_mantencion__lte=hoy + timedelta(days=DIAS_MANTENCION),
    ).count()
    if mantenciones:
        alertas.append({
            "tipo": "mantencion",
            "titulo": "Mantenciones próximas",
            "cantidad": mantenciones,
            "icono": "🔧",
            "canal_sugerido": Canal.EMAIL,
            "detalle": f"{mantenciones} equipos requieren mantención en 14 días",
        })

    en_preparacion = Equipo.objects.filter(estado=EstadoEquipo.EN_PREPARACION).count()
    if en_preparacion:
        alertas.append({
            "tipo": "preparacion",
            "titulo": "Equipos en preparación",
            "cantidad": en_preparacion,
            "icono": "🧺",
            "canal_sugerido": Canal.TEAMS,
            "detalle": f"{en_preparacion} equipos esperan revisión/lavado",
        })

    return alertas


# ────────────────────────────────────────────────────────────
# Envío por canal
# ────────────────────────────────────────────────────────────
def _enviar_email(destino: str, mensaje: str) -> str:
    send_mail(
        subject="[REHAVID] Alerta logística",
        message=mensaje,
        from_email=settings.ALERTAS_EMAIL_FROM,
        recipient_list=[destino],
        fail_silently=False,
    )
    return "enviado"


def _enviar_whatsapp(destino: str, mensaje: str) -> str:
    # Stub · integrar WhatsApp Business Cloud API:
    # POST https://graph.facebook.com/v19.0/{phone_id}/messages con token de Meta.
    logger.info("[stub whatsapp] a %s: %s", destino, mensaje)
    return "stub · pendiente integración WhatsApp Business API"


def _enviar_teams(destino: str, mensaje: str) -> str:
    # Stub · integrar Microsoft Graph API (channel message) o incoming webhook.
    logger.info("[stub teams] a %s: %s", destino, mensaje)
    return "stub · pendiente integración Microsoft Teams (Graph API/webhook)"


_SENDERS = {
    Canal.EMAIL: _enviar_email,
    Canal.WHATSAPP: _enviar_whatsapp,
    Canal.TEAMS: _enviar_teams,
}


class AlertaError(Exception):
    """Error de envío con mensaje para el usuario."""


def enviar_alerta(tipo: str, canal: str, mensaje: str, usuario=None) -> AlertaEnviada:
    """Dispara una alerta por el canal indicado y deja registro + auditoría."""
    config = ConfiguracionCanal.objects.filter(canal=canal).first()
    if config is None or not config.activo:
        msg = f"El canal {canal} no está activo. Configure el canal primero."
        raise AlertaError(msg)
    if not config.destino:
        msg = f"El canal {canal} no tiene destino configurado."
        raise AlertaError(msg)

    try:
        resultado = _SENDERS[canal](config.destino, mensaje)
    except KeyError as e:
        msg = f"Canal desconocido: {canal}"
        raise AlertaError(msg) from e
    except Exception as e:  # p. ej. SMTP caído
        logger.exception("Envío de alerta falló")
        resultado = f"error: {e}"

    registro = AlertaEnviada.objects.create(
        tipo=tipo,
        canal=canal,
        mensaje=mensaje,
        destino=config.destino,
        enviada_por=usuario if usuario is not None and getattr(usuario, "is_authenticated", False) else None,
        resultado=resultado,
    )
    auditoria.registrar(usuario, "enviar_alerta", "alertas", f"{tipo} → {canal} · {resultado}")
    return registro


def detectar_y_notificar() -> int:
    """Corre los detectores y notifica cada alerta por su canal sugerido
    (si está activo). Usada por la tarea beat programada."""
    enviadas = 0
    for alerta in detectar_alertas():
        canal = alerta["canal_sugerido"]
        config = ConfiguracionCanal.objects.filter(canal=canal, activo=True).exclude(destino="").first()
        if not config:
            continue
        try:
            enviar_alerta(alerta["tipo"], canal, f"{alerta['titulo']}: {alerta['detalle']}")
            enviadas += 1
        except AlertaError:
            logger.warning("No se pudo notificar %s por %s", alerta["tipo"], canal)
    return enviadas
