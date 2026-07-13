from django.contrib import admin

from .models import AccesorioTipo
from .models import Ciudad
from .models import Empresa
from .models import Servicio


class AccesorioTipoInline(admin.TabularInline):
    model = AccesorioTipo
    extra = 0


@admin.register(Servicio)
class ServicioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "requiere_equipo_fisico", "activo"]
    list_filter = ["requiere_equipo_fisico", "activo"]
    search_fields = ["nombre"]
    inlines = [AccesorioTipoInline]


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ["nombre"]
    search_fields = ["nombre"]


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "sector"]
    search_fields = ["nombre"]
