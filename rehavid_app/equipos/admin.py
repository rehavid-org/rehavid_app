from django.contrib import admin

from .models import Accesorio
from .models import Equipo


class AccesorioInline(admin.TabularInline):
    model = Accesorio
    extra = 0


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = [
        "codigo",
        "servicio",
        "modelo",
        "serial",
        "estado",
        "ciudad_base",
        "historial_uso",
        "proxima_mantencion",
    ]
    list_filter = ["estado", "servicio", "ciudad_base"]
    search_fields = ["codigo", "modelo", "serial"]
    inlines = [AccesorioInline]
