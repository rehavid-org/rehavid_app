"""B12 · registro real de auditoría, llamado por las acciones de negocio."""

from .models import EventoAuditoria


def registrar(usuario, accion: str, modulo: str, detalle: str = "", request=None) -> EventoAuditoria:
    ip = None
    if request is not None:
        xff = request.META.get("HTTP_X_FORWARDED_FOR")
        ip = xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR")
    return EventoAuditoria.objects.create(
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        user_email=getattr(usuario, "email", "") or "",
        user_nombre=getattr(usuario, "name", "") or "",
        accion=accion,
        modulo=modulo,
        detalle=detalle,
        ip=ip,
    )
