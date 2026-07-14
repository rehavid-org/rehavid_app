from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "reservas"
urlpatterns = [
    path("", views.ReservaListView.as_view(), name="lista"),
    path("nueva/", views.ReservaCreateView.as_view(), name="nueva"),
    path("<int:pk>/reprogramar/", require_POST(views.reprogramar_view), name="reprogramar"),
    path("<int:pk>/cancelar/", require_POST(views.cancelar_view), name="cancelar"),
    path("<int:pk>/retorno/", require_POST(views.retorno_view), name="retorno"),
]
