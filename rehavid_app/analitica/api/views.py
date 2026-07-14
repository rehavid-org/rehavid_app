"""Endpoints JSON de analítica (alimentan los charts ECharts)."""

from rest_framework.response import Response
from rest_framework.views import APIView

from rehavid_app.analitica import services
from rehavid_app.users.permissions import require_nivel


def _filtros(request) -> dict:
    p = request.query_params
    return {
        "desde": p.get("desde") or None,
        "hasta": p.get("hasta") or None,
        "servicio": p.get("servicio") or None,
        "ciudad": p.get("ciudad") or None,
    }


class DashboardDataView(APIView):
    permission_classes = [require_nivel(2)]

    def get(self, request):
        filtros = _filtros(request)
        return Response({
            "kpis": services.kpis(**filtros),
            "series": services.series_dashboard(**filtros),
        })


class RecomendacionesView(APIView):
    permission_classes = [require_nivel(2)]

    def get(self, request):
        return Response({"findings": [f.as_dict() for f in services.analizar()]})
