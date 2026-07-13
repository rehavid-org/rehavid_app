from django.contrib import admin

from .models import Paquete


@admin.register(Paquete)
class PaqueteAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "duracion_dias", "activo"]
    list_filter = ["activo"]
    search_fields = ["codigo", "nombre"]
    filter_horizontal = ["servicios_requeridos"]
