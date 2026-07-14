from rest_framework import serializers

from rehavid_app.solicitudes.models import AccesorioSolicitado
from rehavid_app.solicitudes.models import Solicitud


class AccesorioSolicitadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccesorioSolicitado
        fields = ["nombre", "cantidad"]


class SolicitudSerializer(serializers.ModelSerializer):
    servicio = serializers.StringRelatedField()
    ciudad = serializers.StringRelatedField()
    empresa_cliente = serializers.StringRelatedField()
    solicitante = serializers.StringRelatedField()
    operador = serializers.StringRelatedField()
    accesorios_solicitados = AccesorioSolicitadoSerializer(many=True, read_only=True)
    reserva_codigo = serializers.SerializerMethodField()

    class Meta:
        model = Solicitud
        fields = [
            "id",
            "codigo",
            "solicitante",
            "empresa_cliente",
            "servicio",
            "ciudad",
            "personas",
            "fecha_solicitud",
            "fecha_sugerida",
            "dias_estimados",
            "fecha_confirmada",
            "operador",
            "estado",
            "notas",
            "prof_cantidad",
            "prof_perfil",
            "accesorios_solicitados",
            "reserva_codigo",
            "creada_en",
        ]

    def get_reserva_codigo(self, obj) -> str | None:
        reserva = next((r for r in obj.reservas.all() if not r.cancelada), None)
        return reserva.codigo if reserva else None
