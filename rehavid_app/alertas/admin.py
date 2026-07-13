from django.contrib import admin

from .models import AlertaEnviada
from .models import ConfiguracionCanal


@admin.register(ConfiguracionCanal)
class ConfiguracionCanalAdmin(admin.ModelAdmin):
    list_display = ["canal", "activo", "destino"]
    list_editable = ["activo", "destino"]


@admin.register(AlertaEnviada)
class AlertaEnviadaAdmin(admin.ModelAdmin):
    list_display = ["tipo", "canal", "destino", "enviada_por", "timestamp", "resultado"]
    list_filter = ["tipo", "canal"]
    readonly_fields = ["timestamp"]
