"""POST /api/predictivo/score/ · contrato del prototipo."""

from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from rehavid_app.users.permissions import require_nivel

from . import services


class ScoreRequestSerializer(serializers.Serializer):
    servicio = serializers.CharField()
    ciudad = serializers.CharField()
    cliente = serializers.CharField()
    personas = serializers.IntegerField(min_value=1)
    sector = serializers.CharField(required=False, allow_blank=True, default="")
    jornada = serializers.CharField(required=False, allow_blank=True, default="")


class ScoreView(APIView):
    permission_classes = [require_nivel(2)]

    def post(self, request):
        ser = ScoreRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response(services.obtener_prediccion(ser.validated_data, usuario=request.user))
