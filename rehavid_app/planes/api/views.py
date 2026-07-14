"""API de planes (contrato del prototipo: GET/POST/PUT/DELETE /planes)."""

from rest_framework import serializers
from rest_framework import viewsets

from rehavid_app.auditoria import services as auditoria
from rehavid_app.planes.models import Plan
from rehavid_app.users.permissions import require_nivel


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = ["id", "codigo", "area", "titulo", "descripcion", "responsable",
                  "vence", "avance", "esperado", "estado", "creado_en"]
        read_only_fields = ["codigo", "creado_en"]


class PlanViewSet(viewsets.ModelViewSet):
    serializer_class = PlanSerializer
    queryset = Plan.objects.all()

    def get_permissions(self):
        return [require_nivel(2)()]

    def perform_create(self, serializer):
        plan = serializer.save()
        auditoria.registrar(self.request.user, "crear_plan", "planes", plan.codigo)

    def perform_update(self, serializer):
        plan = serializer.save()
        auditoria.registrar(self.request.user, "editar_plan", "planes", plan.codigo)

    def perform_destroy(self, instance):
        auditoria.registrar(self.request.user, "eliminar_plan", "planes", instance.codigo)
        instance.delete()
