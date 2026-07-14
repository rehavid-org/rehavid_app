from django.urls import path

from . import views

app_name = "auditoria"
urlpatterns = [
    path("", views.AuditoriaListView.as_view(), name="lista"),
    path("export/", views.export_view, name="export"),
]
