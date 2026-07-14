from rest_framework import serializers

from rehavid_app.equipos.models import Accesorio
from rehavid_app.equipos.models import Equipo


class AccesorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accesorio
        fields = ["nombre", "cantidad", "completo", "requiere_lavado", "consumible"]


class EquipoSerializer(serializers.ModelSerializer):
    servicio_nombre = serializers.CharField(source="servicio.nombre", read_only=True)
    ciudad_nombre = serializers.CharField(source="ciudad_base.nombre", read_only=True)
    estado_display = serializers.CharField(source="get_estado_display", read_only=True)
    accesorios = AccesorioSerializer(many=True, read_only=True)

    class Meta:
        model = Equipo
        fields = [
            "id",
            "codigo",
            "servicio",
            "servicio_nombre",
            "modelo",
            "serial",
            "estado",
            "estado_display",
            "responsable",
            "ciudad_base",
            "ciudad_nombre",
            "ultima_revision",
            "proxima_mantencion",
            "notas",
            "historial_uso",
            "accesorios",
        ]


class MotivoSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class NotasSerializer(serializers.Serializer):
    notas = serializers.CharField(required=False, allow_blank=True, default="")
