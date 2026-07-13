from django.contrib import admin

from .models import EventoAuditoria


@admin.register(EventoAuditoria)
class EventoAuditoriaAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "user_email", "accion", "modulo", "detalle", "ip"]
    list_filter = ["modulo", "accion"]
    search_fields = ["user_email", "detalle"]
    readonly_fields = ["usuario", "user_email", "user_nombre", "accion", "modulo", "detalle", "timestamp", "ip"]
    date_hierarchy = "timestamp"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
