from django.contrib import admin

from .models import Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["codigo", "area", "titulo", "responsable", "vence", "avance", "esperado", "estado"]
    list_filter = ["estado", "area"]
    search_fields = ["codigo", "titulo", "responsable"]
    readonly_fields = ["codigo"]
