"""Vistas de operación de reservas (Fase 4). Delgadas: toda mutación pasa
por ``services.py``. Autorización en servidor con nivel <= 2 (corrige B1)."""

from typing import TYPE_CHECKING

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import FormView
from django.views.generic import ListView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Servicio
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido
from rehavid_app.xlsx import workbook_response

from . import services
from .forms import CancelarForm
from .forms import ReprogramarForm
from .forms import ReservaForm
from .forms import RetornoForm
from .models import Reserva
from .services import ReservaError

if TYPE_CHECKING:
    from rehavid_app.paquetes.models import Paquete


def filtrar_reservas(params):
    """Filtros compartidos por la lista y el export Excel."""
    qs = (
        Reserva.objects.select_related(
            "servicio", "cliente", "ciudad", "paquete", "confirmacion_retorno",
        )
        .prefetch_related("equipos")
        .order_by("-fecha_salida")
    )
    if q := params.get("q", "").strip():
        qs = qs.filter(codigo__icontains=q) | qs.filter(cliente__nombre__icontains=q)
    if servicio := params.get("servicio"):
        qs = qs.filter(servicio_id=servicio)
    if ciudad := params.get("ciudad"):
        qs = qs.filter(ciudad_id=ciudad)
    estado = params.get("estado", "")
    if estado == "activas":
        qs = qs.filter(cancelada=False, confirmacion_retorno__isnull=True)
    elif estado == "canceladas":
        qs = qs.filter(cancelada=True)
    elif estado == "retornadas":
        qs = qs.filter(confirmacion_retorno__isnull=False)
    if desde := params.get("desde"):
        qs = qs.filter(fecha_salida__gte=desde)
    if hasta := params.get("hasta"):
        qs = qs.filter(fecha_salida__lte=hasta)
    return qs.distinct()


class ReservaListView(NivelRequeridoMixin, ListView):
    nivel_maximo = 2
    model = Reserva
    template_name = "reservas/lista.html"
    context_object_name = "reservas"
    paginate_by = 25

    def get_queryset(self):
        return filtrar_reservas(self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            modulo_activo="reservas",
            servicios=Servicio.objects.filter(activo=True),
            ciudades=Ciudad.objects.all(),
            filtros=self.request.GET,
            reprogramar_form=ReprogramarForm(),
            cancelar_form=CancelarForm(),
            retorno_form=RetornoForm(),
        )
        return ctx


class ReservaCreateView(NivelRequeridoMixin, FormView):
    """B3 · Nueva Reserva con preview de disponibilidad en vivo (API)."""

    nivel_maximo = 2
    form_class = ReservaForm
    template_name = "reservas/nueva.html"
    success_url = reverse_lazy("reservas:lista")

    def form_valid(self, form):
        d = form.cleaned_data
        paquete: Paquete | None = d["paquete"] if d["tipo"] == ReservaForm.TIPO_PAQUETE else None
        servicio = d["servicio"] if paquete is None else paquete.servicios_requeridos.first()
        try:
            reserva = services.crear_reserva(
                servicio=servicio,
                cliente=d["cliente"],
                ciudad=d["ciudad"],
                personas=d["personas"],
                fecha_salida=d["fecha_salida"],
                fecha_retorno_esp=d["fecha_retorno_esp"],
                usuario=self.request.user,
                paquete=paquete,
            )
        except ReservaError as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Reserva {reserva.codigo} creada · {reserva.equipos.count()} equipo(s) asignado(s)",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["modulo_activo"] = "reservas"
        return ctx


@nivel_requerido(2)
def export_view(request):
    """B14 · export server-side con el schema del modelo real (sin columnas fantasma)."""
    filas = [
        [
            r.codigo,
            r.servicio.nombre,
            r.cliente.nombre,
            r.ciudad.nombre,
            r.personas,
            r.fecha_salida,
            r.fecha_retorno_esp,
            "cancelada" if r.cancelada else ("retornada" if getattr(r, "confirmacion_retorno", None) else "activa"),
            ", ".join(e.codigo for e in r.equipos.all()),
            r.paquete.codigo if r.paquete else "",
            round(r.riesgo, 2),
        ]
        for r in filtrar_reservas(request.GET)
    ]
    auditoria.registrar(request.user, "export_reservas", "reservas", f"{len(filas)} filas")
    return workbook_response(
        "reservas_rehavid.xlsx",
        "Reservas",
        ["Código", "Servicio", "Cliente", "Ciudad", "Personas", "Salida", "Retorno esp.",
         "Estado", "Equipos", "Paquete", "Riesgo"],
        filas,
    )


@nivel_requerido(2)
def reprogramar_view(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    form = ReprogramarForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Datos inválidos para reprogramar: {form.errors.as_text()}")
        return redirect("reservas:lista")
    try:
        services.reprogramar_reserva(
            reserva,
            form.cleaned_data["nueva_fecha_salida"],
            form.cleaned_data["nueva_fecha_retorno"],
            form.cleaned_data["motivo"],
            request.user,
        )
        messages.success(request, f"Reserva {reserva.codigo} reprogramada")
    except ReservaError as e:
        messages.error(request, str(e))
    return redirect("reservas:lista")


@nivel_requerido(2)
def cancelar_view(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    form = CancelarForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indique el motivo de cancelación")
        return redirect("reservas:lista")
    try:
        services.cancelar_reserva(reserva, form.cleaned_data["motivo"], request.user)
        messages.success(request, f"Reserva {reserva.codigo} cancelada · equipos liberados")
    except ReservaError as e:
        messages.error(request, str(e))
    return redirect("reservas:lista")


@nivel_requerido(2)
def retorno_view(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    form = RetornoForm(request.POST)
    if not form.is_valid():
        messages.error(request, f"Datos inválidos para el retorno: {form.errors.as_text()}")
        return redirect("reservas:lista")
    try:
        services.confirmar_retorno(
            reserva,
            form.cleaned_data["estado_kit"],
            form.cleaned_data["notas"],
            form.cleaned_data["requiere_preparacion"],
            request.user,
        )
        destino = "pasa a preparación" if form.cleaned_data["requiere_preparacion"] else "equipos disponibles"
        messages.success(request, f"Retorno de {reserva.codigo} confirmado · {destino}")
    except ReservaError as e:
        messages.error(request, str(e))
    return redirect("reservas:lista")
