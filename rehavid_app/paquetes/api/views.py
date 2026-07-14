"""API de paquetes: CRUD (nivel <= 2, O20) + disponibilidad tri-estado (O09)."""

from datetime import date
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from rehavid_app.auditoria import services as auditoria
from rehavid_app.paquetes.models import Paquete
from rehavid_app.reservas import services as reservas_service
from rehavid_app.users.permissions import require_nivel

from .serializers import PaqueteSerializer

ACCIONES_LECTURA = {"list", "retrieve", "disponibilidad"}


class PaqueteViewSet(viewsets.ModelViewSet):
    serializer_class = PaqueteSerializer
    queryset = Paquete.objects.prefetch_related("servicios_requeridos")

    def get_permissions(self):
        nivel = 3 if self.action in ACCIONES_LECTURA else 2
        return [require_nivel(nivel)()]

    def perform_create(self, serializer):
        paquete = serializer.save()
        auditoria.registrar(self.request.user, "crear_paquete", "paquetes", paquete.codigo)

    def perform_update(self, serializer):
        paquete = serializer.save()
        auditoria.registrar(self.request.user, "editar_paquete", "paquetes", paquete.codigo)

    def perform_destroy(self, instance):
        if instance.reservas.exists():
            instance.activo = False
            instance.save(update_fields=["activo"])
            auditoria.registrar(self.request.user, "desactivar_paquete", "paquetes", instance.codigo)
            return
        auditoria.registrar(self.request.user, "eliminar_paquete", "paquetes", instance.codigo)
        instance.delete()

    @action(detail=True, methods=["get"])
    def disponibilidad(self, request, pk=None):
        paquete = self.get_object()
        try:
            salida = date.fromisoformat(request.query_params.get("fecha_salida", "")) if request.query_params.get(
                "fecha_salida") else timezone.localdate()
            retorno = date.fromisoformat(request.query_params.get("fecha_retorno", "")) if request.query_params.get(
                "fecha_retorno") else salida + timedelta(days=max(paquete.duracion_dias - 1, 0))
        except ValueError:
            return Response({"detail": "Fechas inválidas (use AAAA-MM-DD)"}, status=status.HTTP_400_BAD_REQUEST)
        v = reservas_service.verificar_disponibilidad_paquete(paquete, salida, retorno)
        detalle = [
            {"categoria": d["categoria"], "disponible": d["disponible"], "motivo": d["motivo"]}
            for d in v["detalle"]
        ]
        return Response({"disponible": v["disponible"], "motivo": v["motivo"], "detalle": detalle})
