from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "equipos"
urlpatterns = [
    path("", views.EquipoListView.as_view(), name="lista"),
    path("alta/", views.EquipoCreateView.as_view(), name="alta"),
    path("<int:pk>/listo/", require_POST(views.listo_view), name="listo"),
    path("<int:pk>/mantenimiento/", require_POST(views.mantenimiento_view), name="mantenimiento"),
    path("<int:pk>/baja/", require_POST(views.baja_view), name="baja"),
]
