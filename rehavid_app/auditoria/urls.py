from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

app_name = "auditoria"
urlpatterns = [
    # Fase 6
    path("", ModuloEnMigracionView.as_view(modulo="auditoria", titulo="Auditoría"), name="lista"),
]
