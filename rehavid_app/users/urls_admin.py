from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

app_name = "administracion"
urlpatterns = [
    # Fase 6
    path(
        "usuarios/",
        ModuloEnMigracionView.as_view(modulo="admin", titulo="Administración de usuarios"),
        name="usuarios",
    ),
]
