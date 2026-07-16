from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "planes"
urlpatterns = [
    path("export/", views.export_view, name="export"),
    path("plantilla/", views.plantilla_import_view, name="plantilla"),
    path("importar/", require_POST(views.import_view), name="importar"),
    path("", views.PlanListView.as_view(), name="lista"),
    path("nuevo/", views.PlanCreateView.as_view(), name="nuevo"),
    path("<int:pk>/editar/", views.PlanUpdateView.as_view(), name="editar"),
    path("<int:pk>/eliminar/", views.PlanDeleteView.as_view(), name="eliminar"),
]
