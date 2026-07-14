from rest_framework import serializers

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio
from rehavid_app.paquetes.models import Paquete
from rehavid_app.reservas.models import ConfirmacionRetorno
from rehavid_app.reservas.models import Reserva


class ConfirmacionRetornoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfirmacionRetorno
        fields = ["fecha", "estado_kit", "notas", "requiere_preparacion", "preparacion_completa"]


class ReservaSerializer(serializers.ModelSerializer):
    servicio = serializers.StringRelatedField()
    cliente = serializers.StringRelatedField()
    ciudad = serializers.StringRelatedField()
    paquete = serializers.SlugRelatedField(slug_field="codigo", read_only=True)
    equipos = serializers.SlugRelatedField(slug_field="codigo", many=True, read_only=True)
    confirmacion_retorno = ConfirmacionRetornoSerializer(read_only=True)
    activa = serializers.BooleanField(read_only=True)

    class Meta:
        model = Reserva
        fields = [
            "id",
            "codigo",
            "servicio",
            "cliente",
            "ciudad",
            "personas",
            "fecha_salida",
            "fecha_retorno_esp",
            "estado",
            "cancelada",
            "motivo_cancelacion",
            "reprogramada_desde",
            "equipos",
            "paquete",
            "solicitud",
            "riesgo",
            "activa",
            "confirmacion_retorno",
        ]


class ReservaCrearSerializer(serializers.Serializer):
    servicio = serializers.PrimaryKeyRelatedField(queryset=Servicio.objects.filter(activo=True), required=False)
    paquete = serializers.PrimaryKeyRelatedField(queryset=Paquete.objects.filter(activo=True), required=False)
    cliente = serializers.PrimaryKeyRelatedField(queryset=Empresa.objects.all())
    ciudad = serializers.PrimaryKeyRelatedField(queryset=Ciudad.objects.all())
    personas = serializers.IntegerField(min_value=1)
    fecha_salida = serializers.DateField()
    fecha_retorno_esp = serializers.DateField()

    def validate(self, attrs):
        if not attrs.get("servicio") and not attrs.get("paquete"):
            msg = "Indique servicio o paquete"
            raise serializers.ValidationError(msg)
        return attrs


class ReprogramarSerializer(serializers.Serializer):
    nueva_fecha_salida = serializers.DateField()
    nueva_fecha_retorno = serializers.DateField()
    motivo = serializers.CharField()


class CancelarSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class RetornoSerializer(serializers.Serializer):
    estado_kit = serializers.ChoiceField(choices=ConfirmacionRetorno.EstadoKit.choices)
    notas = serializers.CharField(required=False, allow_blank=True, default="")
    requiere_preparacion = serializers.BooleanField(default=False)
