from django.contrib import admin

from .models import AccesorioSolicitado
from .models import Observacion
from .models import Solicitud


class AccesorioSolicitadoInline(admin.TabularInline):
    model = AccesorioSolicitado
    extra = 0


class ObservacionInline(admin.TabularInline):
    model = Observacion
    extra = 0
    readonly_fields = ["fecha"]


@admin.register(Solicitud)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = [
        "codigo",
        "solicitante",
        "empresa_cliente",
        "servicio",
        "ciudad",
        "fecha_sugerida",
        "estado",
        "operador",
    ]
    list_filter = ["estado", "servicio", "ciudad"]
    search_fields = ["codigo", "solicitante__email", "empresa_cliente__nombre"]
    inlines = [AccesorioSolicitadoInline, ObservacionInline]
    readonly_fields = ["codigo", "fecha_solicitud", "creada_en"]
