from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "solicitudes"
urlpatterns = [
    path("bandeja/", views.BandejaView.as_view(), name="bandeja"),
    path("<int:pk>/atender/", require_POST(views.atender_view), name="atender"),
]
