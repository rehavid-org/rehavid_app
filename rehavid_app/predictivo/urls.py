from django.urls import path

from rehavid_app.users.views import ModuloEnMigracionView

app_name = "predictivo"
urlpatterns = [
    # Fase 6
    path("", ModuloEnMigracionView.as_view(modulo="predictivo", titulo="Predictivo MSK"), name="index"),
]
