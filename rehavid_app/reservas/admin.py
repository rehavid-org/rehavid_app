from django.contrib import admin

from .models import ConfirmacionRetorno
from .models import HistorialReserva
from .models import Reserva


class HistorialInline(admin.TabularInline):
    model = HistorialReserva
    extra = 0
    readonly_fields = ["timestamp", "accion", "usuario", "detalle"]
    can_delete = False


class ConfirmacionRetornoInline(admin.StackedInline):
    model = ConfirmacionRetorno
    extra = 0


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = [
        "codigo",
        "servicio",
        "cliente",
        "ciudad",
        "fecha_salida",
        "fecha_retorno_esp",
        "estado",
        "cancelada",
        "riesgo",
    ]
    list_filter = ["estado", "cancelada", "servicio", "ciudad"]
    search_fields = ["codigo", "cliente__nombre"]
    filter_horizontal = ["equipos"]
    inlines = [ConfirmacionRetornoInline, HistorialInline]
    readonly_fields = ["codigo", "creada_en"]
    date_hierarchy = "fecha_salida"
