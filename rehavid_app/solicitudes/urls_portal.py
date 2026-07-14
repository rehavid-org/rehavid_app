from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

app_name = "portal"
urlpatterns = [
    # Fase 5
    path("", ModuloEnMigracionView.as_view(modulo="portal", titulo="Portal del solicitante"), name="inicio"),
    path(
        "equipos/",
        ModuloEnMigracionView.as_view(modulo="equipos-disp", titulo="Equipos disponibles"),
        name="equipos",
    ),
    path(
        "solicitar/",
        ModuloEnMigracionView.as_view(modulo="solicitar", titulo="Solicitar servicio"),
        name="solicitar",
    ),
    path(
        "mis-solicitudes/",
        ModuloEnMigracionView.as_view(modulo="mis-solicitudes", titulo="Mis solicitudes"),
        name="mis_solicitudes",
    ),
]
