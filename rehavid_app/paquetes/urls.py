from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "paquetes"
urlpatterns = [
    path("export/", views.export_view, name="export"),
    path("plantilla/", views.plantilla_import_view, name="plantilla"),
    path("importar/", require_POST(views.import_view), name="importar"),
    path("", views.PaqueteListView.as_view(), name="lista"),
    path("nuevo/", views.PaqueteCreateView.as_view(), name="nuevo"),
    path("<int:pk>/editar/", views.PaqueteUpdateView.as_view(), name="editar"),
    path("<int:pk>/eliminar/", views.PaqueteDeleteView.as_view(), name="eliminar"),
]
