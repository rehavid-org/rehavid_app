"""API de equipos: listar/crear, ficha (O04) y acciones listo/mantenimiento/baja."""

from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rehavid_app.auditoria import services as auditoria
from rehavid_app.equipos.models import Equipo
from rehavid_app.reservas import services as reservas_service
from rehavid_app.reservas.models import Reserva
from rehavid_app.reservas.services import ReservaError
from rehavid_app.users.permissions import require_nivel

from .serializers import EquipoSerializer
from .serializers import MotivoSerializer
from .serializers import NotasSerializer

NIVEL_POR_ACCION = {
    "list": 3,
    "retrieve": 3,
    "ficha": 3,
    "create": 2,
    "listo": 2,
    "mantenimiento": 2,
    "baja": 1,  # O18 · solo Admin Global
}


class EquipoViewSet(
    viewsets.mixins.CreateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    serializer_class = EquipoSerializer
    queryset = Equipo.objects.select_related("servicio", "ciudad_base").prefetch_related("accesorios")

    def get_permissions(self):
        return [require_nivel(NIVEL_POR_ACCION.get(self.action, 2))()]

    def perform_create(self, serializer):
        equipo = serializer.save()
        auditoria.registrar(
            self.request.user, "crear_equipo", "equipos",
            f"{equipo.codigo} · {equipo.modelo} · serial {equipo.serial}",
        )

    @action(detail=True, methods=["get"])
    def ficha(self, request, pk=None):
        """O04 · ficha con métricas, próxima reserva y accesorios."""
        equipo = self.get_object()
        activas = Reserva.objects.filter(equipos=equipo, cancelada=False, confirmacion_retorno__isnull=True)
        proxima = activas.order_by("fecha_salida").first()
        data = EquipoSerializer(equipo).data
        data.update(
            reservas_activas=activas.count(),
            reservas_historicas=Reserva.objects.filter(equipos=equipo).count(),
            proxima_reserva=(
                f"{proxima.codigo} · {proxima.cliente} · {proxima.fecha_salida:%d %b %Y}" if proxima else None
            ),
            servicio=equipo.servicio.nombre,
            ciudad_base=equipo.ciudad_base.nombre,
        )
        return Response(data)

    @action(detail=True, methods=["post"])
    def listo(self, request, pk=None):
        ser = NotasSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            equipo = reservas_service.marcar_equipo_listo(self.get_object(), ser.validated_data["notas"], request.user)
        except ReservaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EquipoSerializer(equipo).data)

    @action(detail=True, methods=["post"])
    def mantenimiento(self, request, pk=None):
        ser = MotivoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        equipo = reservas_service.enviar_a_mantenimiento(self.get_object(), ser.validated_data["motivo"], request.user)
        return Response(EquipoSerializer(equipo).data)

    @action(detail=True, methods=["post"])
    def baja(self, request, pk=None):
        ser = MotivoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            equipo = reservas_service.dar_de_baja_equipo(self.get_object(), ser.validated_data["motivo"], request.user)
        except ReservaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EquipoSerializer(equipo).data)
