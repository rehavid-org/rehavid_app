from django.urls import path

from . import views

app_name = "predictivo"
urlpatterns = [
    path("", views.PredictivoView.as_view(), name="index"),
]
