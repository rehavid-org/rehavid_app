from django.contrib import admin

from .models import PrediccionRegistro


@admin.register(PrediccionRegistro)
class PrediccionRegistroAdmin(admin.ModelAdmin):
    list_display = ["creado_en", "usuario", "servicio", "cliente", "personas", "score", "es_simulacion", "modelo_version"]
    list_filter = ["es_simulacion", "servicio"]
    readonly_fields = ["creado_en"]
