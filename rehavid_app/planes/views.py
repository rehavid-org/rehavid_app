"""CRUD de planes de acción (B11). Nivel <= 2; lectura para quien tenga el módulo."""

from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import DeleteView
from django.views.generic import ListView
from django.views.generic import UpdateView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.users.permissions import ModuloRequeridoMixin
from rehavid_app.users.permissions import NivelRequeridoMixin

from .forms import PlanForm
from .models import Plan


class PlanListView(ModuloRequeridoMixin, ListView):
    modulo = "planes"
    model = Plan
    template_name = "planes/lista.html"
    context_object_name = "planes"

    def get_queryset(self):
        qs = Plan.objects.all()
        if estado := self.request.GET.get("estado"):
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            modulo_activo="planes",
            filtros=self.request.GET,
            estados=Plan.Estado.choices,
            kpi_abiertos=Plan.objects.filter(estado=Plan.Estado.ABIERTO).count(),
            kpi_riesgo=Plan.objects.filter(estado=Plan.Estado.EN_RIESGO).count(),
            kpi_completados=Plan.objects.filter(estado=Plan.Estado.COMPLETADO).count(),
        )
        return ctx


class PlanCreateView(NivelRequeridoMixin, CreateView):
    nivel_maximo = 2
    model = Plan
    form_class = PlanForm
    template_name = "planes/form.html"
    success_url = reverse_lazy("planes:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(self.request.user, "crear_plan", "planes", self.object.codigo)
        messages.success(self.request, f"Plan {self.object.codigo} creado")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"modulo_activo": "planes", "titulo": "Nuevo plan de acción"}


class PlanUpdateView(NivelRequeridoMixin, UpdateView):
    nivel_maximo = 2
    model = Plan
    form_class = PlanForm
    template_name = "planes/form.html"
    success_url = reverse_lazy("planes:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(self.request.user, "editar_plan", "planes", self.object.codigo)
        messages.success(self.request, f"Plan {self.object.codigo} actualizado")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "modulo_activo": "planes",
            "titulo": f"Editar {self.object.codigo}",
        }


class PlanDeleteView(NivelRequeridoMixin, DeleteView):
    nivel_maximo = 2
    model = Plan
    template_name = "planes/eliminar.html"
    success_url = reverse_lazy("planes:lista")

    def form_valid(self, form):
        codigo = self.object.codigo
        auditoria.registrar(self.request.user, "eliminar_plan", "planes", codigo)
        messages.success(self.request, f"Plan {codigo} eliminado")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"modulo_activo": "planes"}
