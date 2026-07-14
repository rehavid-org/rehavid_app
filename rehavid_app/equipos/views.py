"""Vistas del inventario de equipos (Fase 4). Mutaciones vía
``reservas/services.py`` (listo/mantenimiento/baja) y auditoría."""

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import ListView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.catalogo.models import Servicio
from rehavid_app.reservas import services as reservas_service
from rehavid_app.reservas.services import ReservaError
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido

from .forms import BajaForm
from .forms import EquipoForm
from .forms import ListoForm
from .forms import MantenimientoForm
from .models import Equipo
from .models import EstadoEquipo


class EquipoListView(NivelRequeridoMixin, ListView):
    nivel_maximo = 3
    model = Equipo
    template_name = "equipos/lista.html"
    context_object_name = "equipos"

    def get_queryset(self):
        qs = Equipo.objects.select_related("servicio", "ciudad_base").prefetch_related("accesorios")
        p = self.request.GET
        if q := p.get("q", "").strip():
            qs = qs.filter(codigo__icontains=q) | qs.filter(serial__icontains=q) | qs.filter(modelo__icontains=q)
        if servicio := p.get("servicio"):
            qs = qs.filter(servicio_id=servicio)
        if estado := p.get("estado"):
            qs = qs.filter(estado=estado)
        return qs.distinct().order_by("codigo")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        inventario = Equipo.objects.exclude(estado=EstadoEquipo.DE_BAJA)
        ctx.update(
            modulo_activo="equipos",
            # O02 · KPI disponibles/total en vivo
            kpi_total=inventario.count(),
            kpi_disponibles=inventario.filter(estado=EstadoEquipo.DISPONIBLE).count(),
            kpi_en_uso=inventario.filter(estado=EstadoEquipo.EN_USO).count(),
            kpi_preparacion=inventario.filter(estado=EstadoEquipo.EN_PREPARACION).count(),
            # O07 · Tumeke y demás servicios sin unidad física, como tarjeta especial
            servicios_sin_stock=Servicio.objects.filter(requiere_equipo_fisico=False, activo=True),
            servicios=Servicio.objects.filter(activo=True, requiere_equipo_fisico=True),
            estados=EstadoEquipo.choices,
            filtros=self.request.GET,
            listo_form=ListoForm(),
            mantenimiento_form=MantenimientoForm(),
            baja_form=BajaForm(),
        )
        return ctx


class EquipoCreateView(NivelRequeridoMixin, CreateView):
    """B7 · alta con el modelo canónico; aparece en inventario y disponibilidad."""

    nivel_maximo = 2
    model = Equipo
    form_class = EquipoForm
    template_name = "equipos/alta.html"
    success_url = reverse_lazy("equipos:lista")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(
            self.request.user, "crear_equipo", "equipos",
            f"{self.object.codigo} · {self.object.modelo} · serial {self.object.serial}",
        )
        messages.success(self.request, f"Equipo {self.object.codigo} agregado al inventario")
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modulo_activo"] = "equipos"
        return ctx


@nivel_requerido(2)
def listo_view(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    form = ListoForm(request.POST)
    notas = form.cleaned_data["notas"] if form.is_valid() else ""
    try:
        reservas_service.marcar_equipo_listo(equipo, notas, request.user)
        messages.success(request, f"{equipo.codigo} listo y disponible")
    except ReservaError as e:
        messages.error(request, str(e))
    return redirect("equipos:lista")


@nivel_requerido(2)
def mantenimiento_view(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    form = MantenimientoForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indique el motivo del mantenimiento")
        return redirect("equipos:lista")
    reservas_service.enviar_a_mantenimiento(equipo, form.cleaned_data["motivo"], request.user)
    messages.success(request, f"{equipo.codigo} enviado a mantenimiento")
    return redirect("equipos:lista")


@nivel_requerido(1)  # O18 · baja definitiva solo Admin Global
def baja_view(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    form = BajaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indique el motivo de la baja")
        return redirect("equipos:lista")
    try:
        reservas_service.dar_de_baja_equipo(equipo, form.cleaned_data["motivo"], request.user)
        messages.success(request, f"{equipo.codigo} dado de baja definitivamente")
    except ReservaError as e:
        messages.error(request, str(e))
    return redirect("equipos:lista")
