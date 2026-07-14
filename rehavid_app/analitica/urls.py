from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

from . import views

app_name = "analitica"
urlpatterns = [
    path("calendario/", views.CalendarioView.as_view(), name="calendario"),
    # Fase 6
    path("brief/", ModuloEnMigracionView.as_view(modulo="brief", titulo="Brief ejecutivo"), name="brief"),
    path("dashboard/", ModuloEnMigracionView.as_view(modulo="dashboard", titulo="Dashboard"), name="dashboard"),
    path("recomendaciones/", ModuloEnMigracionView.as_view(modulo="recos", titulo="Recomendaciones"), name="recos"),
]
