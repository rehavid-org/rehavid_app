from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "alertas"
urlpatterns = [
    path("", views.AlertasView.as_view(), name="index"),
    path("enviar/", require_POST(views.enviar_view), name="enviar"),
    path("canales/", require_POST(views.guardar_canales_view), name="canales"),
]
