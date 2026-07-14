from django.urls import path

from . import views

app_name = "paquetes"
urlpatterns = [
    path("", views.PaqueteListView.as_view(), name="lista"),
    path("nuevo/", views.PaqueteCreateView.as_view(), name="nuevo"),
    path("<int:pk>/editar/", views.PaqueteUpdateView.as_view(), name="editar"),
    path("<int:pk>/eliminar/", views.PaqueteDeleteView.as_view(), name="eliminar"),
]
