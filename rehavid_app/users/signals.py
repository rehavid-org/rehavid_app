"""B12 · registra cada login real en auditoría (alimenta la actividad agregada)."""

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    from rehavid_app.auditoria import services as auditoria  # noqa: PLC0415

    auditoria.registrar(user, "login", "auth", request=request)
