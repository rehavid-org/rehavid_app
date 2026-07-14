"""API de reservas: espejo del contrato de la capa ``API`` JS del prototipo.

GET  /api/reservas/                  · listar (nivel <= 2)
POST /api/reservas/                  · crear (nivel <= 2)
GET  /api/reservas/disponibilidad/   · preview en vivo (nivel <= 4: el portal
                                       la usa para la saturación O10)
POST /api/reservas/{id}/cancelar/    · nivel <= 2
POST /api/reservas/{id}/reprogramar/ · nivel <= 2
POST /api/reservas/{id}/retorno/     · nivel <= 2
"""

from datetime import date

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rehavid_app.catalogo.models import Servicio
from rehavid_app.paquetes.models import Paquete
from rehavid_app.reservas import services
from rehavid_app.reservas.models import Reserva
from rehavid_app.reservas.services import ReservaError
from rehavid_app.users.permissions import require_nivel

from .serializers import CancelarSerializer
from .serializers import ReprogramarSerializer
from .serializers import ReservaCrearSerializer
from .serializers import ReservaSerializer
from .serializers import RetornoSerializer


class ReservaViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReservaSerializer
    queryset = (
        Reserva.objects.select_related("servicio", "cliente", "ciudad", "paquete", "confirmacion_retorno")
        .prefetch_related("equipos")
        .order_by("-fecha_salida")
    )

    def get_permissions(self):
        if self.action == "disponibilidad":
            return [require_nivel(4)()]
        return [require_nivel(2)()]

    def create(self, request):
        ser = ReservaCrearSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        paquete = d.get("paquete")
        servicio = d.get("servicio") or paquete.servicios_requeridos.first()
        try:
            reserva = services.crear_reserva(
                servicio=servicio,
                cliente=d["cliente"],
                ciudad=d["ciudad"],
                personas=d["personas"],
                fecha_salida=d["fecha_salida"],
                fecha_retorno_esp=d["fecha_retorno_esp"],
                usuario=request.user,
                paquete=paquete,
            )
        except ReservaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReservaSerializer(reserva).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def disponibilidad(self, request):
        """Preview de disponibilidad en vivo para el formulario Nueva Reserva."""
        servicio_id = request.query_params.get("servicio")
        paquete_id = request.query_params.get("paquete")
        try:
            fecha_salida = date.fromisoformat(request.query_params.get("fecha_salida", ""))
            fecha_retorno = date.fromisoformat(request.query_params.get("fecha_retorno", ""))
        except ValueError:
            return Response({"detail": "Fechas inválidas (use AAAA-MM-DD)"}, status=status.HTTP_400_BAD_REQUEST)
        if not (servicio_id or paquete_id):
            return Response(
                {"detail": "Parámetros requeridos: fecha_salida, fecha_retorno y servicio o paquete"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if paquete_id:
            paquete = get_object_or_404(Paquete, pk=paquete_id)
            v = services.verificar_disponibilidad_paquete(paquete, fecha_salida, fecha_retorno)
            detalle = [
                {"categoria": d["categoria"], "disponible": d["disponible"], "motivo": d["motivo"]}
                for d in v["detalle"]
            ]
            return Response({"disponible": v["disponible"], "motivo": v["motivo"], "detalle": detalle})
        servicio = get_object_or_404(Servicio, pk=servicio_id)
        disp = services.verificar_disponibilidad(servicio, fecha_salida, fecha_retorno)
        return Response(disp.as_dict())

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        ser = CancelarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            reserva = services.cancelar_reserva(self.get_object(), ser.validated_data["motivo"], request.user)
        except ReservaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReservaSerializer(reserva).data)

    @action(detail=True, methods=["post"])
    def reprogramar(self, request, pk=None):
        ser = ReprogramarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            reserva = services.reprogramar_reserva(
                self.get_object(), d["nueva_fecha_salida"], d["nueva_fecha_retorno"], d["motivo"], request.user,
            )
        except ReservaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReservaSerializer(reserva).data)

    @action(detail=True, methods=["post"])
    def retorno(self, request, pk=None):
        ser = RetornoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            reserva = services.confirmar_retorno(
                self.get_object(), d["estado_kit"], d["notas"], d["requiere_preparacion"], request.user,
            )
        except ReservaError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ReservaSerializer(reserva).data)
