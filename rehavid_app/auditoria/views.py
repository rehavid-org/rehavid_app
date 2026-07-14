"""Vista de auditoría (nivel 1): log global con filtros + export Excel."""

from django.views.generic import ListView

from rehavid_app.users.models import User
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido
from rehavid_app.xlsx import workbook_response

from . import services
from .models import EventoAuditoria


def filtrar_eventos(params):
    qs = EventoAuditoria.objects.select_related("usuario")
    if usuario := params.get("usuario"):
        qs = qs.filter(usuario_id=usuario)
    if modulo := params.get("modulo"):
        qs = qs.filter(modulo=modulo)
    if q := params.get("q", "").strip():
        qs = qs.filter(detalle__icontains=q) | qs.filter(accion__icontains=q)
    if desde := params.get("desde"):
        qs = qs.filter(timestamp__date__gte=desde)
    if hasta := params.get("hasta"):
        qs = qs.filter(timestamp__date__lte=hasta)
    return qs.distinct()


class AuditoriaListView(NivelRequeridoMixin, ListView):
    nivel_maximo = 1
    template_name = "auditoria/lista.html"
    context_object_name = "eventos"
    paginate_by = 50

    def get_queryset(self):
        return filtrar_eventos(self.request.GET)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "modulo_activo": "auditoria",
            "filtros": self.request.GET,
            "usuarios": User.objects.order_by("name"),
            "modulos": (
                EventoAuditoria.objects.values_list("modulo", flat=True).distinct().order_by("modulo")
            ),
        }


@nivel_requerido(1)
def export_view(request):
    filas = [
        [
            e.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            e.user_email,
            e.user_nombre,
            e.accion,
            e.modulo,
            e.detalle,
            e.ip or "",
        ]
        for e in filtrar_eventos(request.GET)[:5000]
    ]
    services.registrar(request.user, "export_auditoria", "auditoria", f"{len(filas)} filas")
    return workbook_response(
        "auditoria_rehavid.xlsx",
        "Auditoría",
        ["Fecha", "Correo", "Usuario", "Acción", "Módulo", "Detalle", "IP"],
        filas,
    )
