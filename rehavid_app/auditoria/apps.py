from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AuditoriaConfig(AppConfig):
    name = "rehavid_app.auditoria"
    verbose_name = _("Auditoría")
