"""API de solicitudes: bandeja del operador + badge O17 + atender (B2)."""

from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rehavid_app.reservas.api.serializers import ReservaSerializer
from rehavid_app.reservas.services import ReservaError
from rehavid_app.solicitudes import services
from rehavid_app.solicitudes.models import Solicitud
from rehavid_app.solicitudes.services import SolicitudError
from rehavid_app.users.permissions import require_nivel

from .serializers import SolicitudSerializer


class SolicitudViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = SolicitudSerializer
    queryset = (
        Solicitud.objects.select_related("servicio", "ciudad", "empresa_cliente", "solicitante", "operador")
        .prefetch_related("accesorios_solicitados", "reservas")
    )

    def get_permissions(self):
        return [require_nivel(2)()]

    def get_queryset(self):
        qs = super().get_queryset()
        if estado := self.request.query_params.get("estado"):
            qs = qs.filter(estado=estado)
        return qs

    @action(detail=False, methods=["get"])
    def badge(self, request):
        """O17 · contador de pendientes para el badge del menú."""
        return Response({"pendientes": services.contar_pendientes()})

    @action(detail=True, methods=["post"])
    def atender(self, request, pk=None):
        """B2 · valida stock, crea la Reserva vinculada y confirma."""
        try:
            reserva = services.atender_solicitud(self.get_object(), request.user)
        except (SolicitudError, ReservaError) as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReservaSerializer(reserva).data, status=status.HTTP_201_CREATED)
