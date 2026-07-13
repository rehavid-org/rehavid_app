from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class PlanesConfig(AppConfig):
    name = "rehavid_app.planes"
    verbose_name = _("Planes de acción")
