from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

app_name = "alertas"
urlpatterns = [
    # Fase 6
    path("", ModuloEnMigracionView.as_view(modulo="alertas", titulo="Alertas logísticas"), name="index"),
]
