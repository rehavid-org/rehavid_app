"""Paquetes multi-equipo: tarjetas tri-estado (O09) + CRUD nivel <= 2 (O20/B11)."""

from datetime import timedelta

from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import ListView
from django.views.generic import UpdateView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.reservas import services as reservas_service
from rehavid_app.users.permissions import NivelRequeridoMixin

from .forms import PaqueteForm
from .models import Paquete


def estado_paquete(paquete: Paquete) -> dict:
    """O09 · tri-estado hoy→hoy+duración: disponible / parcial / agotado."""
    hoy = timezone.localdate()
    fin = hoy + timedelta(days=max(paquete.duracion_dias - 1, 0))
    v = reservas_service.verificar_disponibilidad_paquete(paquete, hoy, fin)
    libres = sum(1 for d in v["detalle"] if d["disponible"])
    total = len(v["detalle"])
    if v["disponible"]:
        estado = "disponible"
    elif libres:
        estado = "parcial"
    else:
        estado = "agotado"

    proxima = None
    if estado != "disponible":
        # Estimación: la fecha en que la última categoría faltante vuelve a tener stock
        fechas = [
            reservas_service.proxima_fecha_disponible(servicio, paquete.duracion_dias)
            for servicio, d in zip(paquete.servicios_requeridos.all(), v["detalle"], strict=False)
            if not d["disponible"]
        ]
        fechas = [f for f in fechas if f]
        proxima = max(fechas) if fechas else None

    return {
        "paquete": paquete,
        "estado": estado,
        "motivo": v["motivo"],
        "detalle": v["detalle"],
        "libres": libres,
        "total": total,
        "proxima": proxima,
    }


class PaqueteListView(NivelRequeridoMixin, ListView):
    nivel_maximo = 3
    model = Paquete
    template_name = "paquetes/lista.html"
    context_object_name = "paquetes"

    def get_queryset(self):
        return Paquete.objects.filter(activo=True).prefetch_related("servicios_requeridos")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modulo_activo"] = "paquetes"
        ctx["tarjetas"] = [estado_paquete(p) for p in ctx["paquetes"]]
        return ctx


class PaqueteCreateView(NivelRequeridoMixin, CreateView):
    nivel_maximo = 2
    model = Paquete
    form_class = PaqueteForm
    template_name = "paquetes/form.html"
    success_url = reverse_lazy("paquetes:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(self.request.user, "crear_paquete", "paquetes", self.object.codigo)
        messages.success(self.request, f"Paquete {self.object.codigo} creado")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"modulo_activo": "paquetes", "titulo": "Nuevo paquete"}


class PaqueteUpdateView(NivelRequeridoMixin, UpdateView):
    nivel_maximo = 2
    model = Paquete
    form_class = PaqueteForm
    template_name = "paquetes/form.html"
    success_url = reverse_lazy("paquetes:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(self.request.user, "editar_paquete", "paquetes", self.object.codigo)
        messages.success(self.request, f"Paquete {self.object.codigo} actualizado")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "modulo_activo": "paquetes",
            "titulo": f"Editar {self.object.codigo}",
        }


class PaqueteDeleteView(NivelRequeridoMixin, DeleteView):
    nivel_maximo = 2
    model = Paquete
    template_name = "paquetes/eliminar.html"
    success_url = reverse_lazy("paquetes:lista")

    def form_valid(self, form):
        codigo = self.object.codigo
        if self.object.reservas.exists():
            # Con historial de reservas no se borra: se desactiva
            self.object.activo = False
            self.object.save(update_fields=["activo"])
            auditoria.registrar(self.request.user, "desactivar_paquete", "paquetes", codigo)
            messages.success(self.request, f"Paquete {codigo} desactivado (tiene reservas históricas)")
            return HttpResponseRedirect(self.get_success_url())
        auditoria.registrar(self.request.user, "eliminar_paquete", "paquetes", codigo)
        messages.success(self.request, f"Paquete {codigo} eliminado")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"modulo_activo": "paquetes"}
