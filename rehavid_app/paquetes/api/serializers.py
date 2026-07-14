from rest_framework import serializers

from rehavid_app.catalogo.models import Servicio
from rehavid_app.paquetes.models import Paquete


class PaqueteSerializer(serializers.ModelSerializer):
    servicios_requeridos = serializers.PrimaryKeyRelatedField(
        queryset=Servicio.objects.filter(activo=True),
        many=True,
    )
    servicios_nombres = serializers.SlugRelatedField(
        source="servicios_requeridos",
        slug_field="nombre",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Paquete
        fields = [
            "id",
            "codigo",
            "nombre",
            "descripcion",
            "servicios_requeridos",
            "servicios_nombres",
            "duracion_dias",
            "activo",
        ]
