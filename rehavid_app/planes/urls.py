from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

app_name = "planes"
urlpatterns = [
    # Fase 6
    path("", ModuloEnMigracionView.as_view(modulo="planes", titulo="Planes de acción"), name="lista"),
]
