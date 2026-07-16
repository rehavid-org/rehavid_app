from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "portal"
urlpatterns = [
    path("", views.PortalInicioView.as_view(), name="inicio"),
    path("equipos/", views.PortalEquiposView.as_view(), name="equipos"),
    path("solicitar/", views.SolicitarView.as_view(), name="solicitar"),
    path("mis-solicitudes/", views.MisSolicitudesView.as_view(), name="mis_solicitudes"),
    path("mis-solicitudes/export/", views.export_mis_solicitudes_view, name="mis_solicitudes_export"),
    path("solicitudes/<int:pk>/editar/", require_POST(views.editar_solicitud_view), name="editar"),
    path("solicitudes/<int:pk>/cancelar/", require_POST(views.cancelar_solicitud_view), name="cancelar"),
    path("solicitudes/<int:pk>/observacion/", require_POST(views.observacion_view), name="observacion"),
]
