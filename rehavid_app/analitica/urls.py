from django.urls import path
from django.views.decorators.http import require_POST

from . import views

app_name = "analitica"
urlpatterns = [
    path("calendario/", views.CalendarioView.as_view(), name="calendario"),
    path("brief/", views.BriefView.as_view(), name="brief"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("recomendaciones/", views.RecosView.as_view(), name="recos"),
    path(
        "recomendaciones/<str:finding_id>/crear-plan/",
        require_POST(views.crear_plan_desde_finding_view),
        name="crear_plan",
    ),
]
