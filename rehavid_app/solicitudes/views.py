"""Portal solicitante (nivel 4) y bandeja del operador (Fase 5).
Toda mutación pasa por ``services.py``; las vistas solo orquestan."""

from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import FormView
from django.views.generic import ListView
from django.views.generic import TemplateView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.catalogo.models import AccesorioTipo
from rehavid_app.catalogo.models import Servicio
from rehavid_app.equipos.models import Equipo
from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.reservas import services as reservas_service
from rehavid_app.reservas.services import ReservaError
from rehavid_app.users.permissions import ModuloRequeridoMixin
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido
from rehavid_app.xlsx import workbook_response

from . import services
from .forms import CancelarSolicitudForm
from .forms import EditarSolicitudForm
from .forms import ObservacionForm
from .forms import SolicitudForm
from .models import EstadoSolicitud
from .models import Solicitud
from .services import SolicitudError

HORAS_URGENCIA = 12


# ────────────────────────────────────────────────────────────
# Portal del solicitante (nivel 4)
# ────────────────────────────────────────────────────────────
class PortalInicioView(ModuloRequeridoMixin, TemplateView):
    modulo = "portal"
    template_name = "portal/inicio.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        mias = Solicitud.objects.filter(solicitante=self.request.user)
        proximas = (
            mias.filter(estado=EstadoSolicitud.CONFIRMADA, fecha_sugerida__gte=timezone.localdate())
            .select_related("servicio", "ciudad")
            .order_by("fecha_sugerida")[:5]
        )
        ctx.update(
            modulo_activo="portal",
            kpi_pendientes=mias.filter(estado=EstadoSolicitud.PENDIENTE).count(),
            kpi_confirmadas=mias.filter(estado=EstadoSolicitud.CONFIRMADA).count(),
            kpi_finalizadas=mias.filter(estado=EstadoSolicitud.FINALIZADA).count(),
            kpi_total=mias.count(),
            proximas=proximas,
            ultimas=mias.select_related("servicio", "ciudad")[:5],
        )
        return ctx


class PortalEquiposView(ModuloRequeridoMixin, TemplateView):
    """Equipos disponibles read-only + próxima fecha libre por categoría."""

    modulo = "equipos-disp"
    template_name = "portal/equipos.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        categorias = []
        for servicio in Servicio.objects.filter(activo=True):
            if not servicio.requiere_equipo_fisico:
                categorias.append({
                    "servicio": servicio, "sin_stock": True, "disponibles": None,
                    "total": None, "proxima": timezone.localdate(),
                })
                continue
            equipos = Equipo.objects.filter(servicio=servicio).exclude(estado=EstadoEquipo.DE_BAJA)
            total = equipos.count()
            if not total:
                continue
            categorias.append({
                "servicio": servicio,
                "sin_stock": False,
                "disponibles": equipos.filter(estado=EstadoEquipo.DISPONIBLE).count(),
                "total": total,
                "proxima": reservas_service.proxima_fecha_disponible(servicio),
            })
        ctx.update(modulo_activo="equipos-disp", categorias=categorias)
        return ctx


class SolicitarView(ModuloRequeridoMixin, FormView):
    """O16 accesorios dinámicos · O19 profesional · O10 preview · B4 fecha."""

    modulo = "solicitar"
    form_class = SolicitudForm
    template_name = "portal/solicitar.html"
    success_url = reverse_lazy("portal:mis_solicitudes")

    def get_form_kwargs(self):
        return super().get_form_kwargs() | {"usuario": self.request.user}

    def _accesorios_elegidos(self, servicio):
        """O16 · lee inputs ``acc-<id>`` (cantidad) de los tipos del servicio."""
        elegidos = []
        for tipo in AccesorioTipo.objects.filter(servicio=servicio):
            raw = self.request.POST.get(f"acc-{tipo.pk}", "")
            try:
                cantidad = int(raw)
            except ValueError:
                continue
            if cantidad > 0:
                elegidos.append({"nombre": tipo.nombre, "cantidad": cantidad})
        return elegidos

    def form_valid(self, form):
        d = form.cleaned_data
        solicitud = services.crear_solicitud(
            solicitante=self.request.user,
            empresa_cliente=d["empresa_cliente"],
            servicio=d["servicio"],
            ciudad=d["ciudad"],
            personas=d["personas"],
            fecha_sugerida=d["fecha_sugerida"],
            dias_estimados=d["dias_estimados"],
            notas=d["notas"],
            profesional={
                "cantidad": d["prof_cantidad"],
                "perfil": d["prof_perfil"],
                "nombre": d["prof_nombre"],
                "especialidad": d["prof_especialidad"],
                "telefono": d["prof_telefono"],
                "correo": d["prof_correo"],
            },
            accesorios=self._accesorios_elegidos(d["servicio"]),
        )
        messages.success(
            self.request,
            f"Solicitud {solicitud.codigo} enviada · el equipo de operaciones la atenderá pronto",
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        accesorios_por_servicio = {}
        for tipo in AccesorioTipo.objects.select_related("servicio"):
            accesorios_por_servicio.setdefault(tipo.servicio_id, []).append({
                "id": tipo.pk,
                "nombre": tipo.nombre,
                "cantidad_default": tipo.cantidad_default,
            })
        ctx.update(
            modulo_activo="solicitar",
            accesorios_json=accesorios_por_servicio,
        )
        return ctx


class MisSolicitudesView(ModuloRequeridoMixin, ListView):
    modulo = "mis-solicitudes"
    template_name = "portal/mis_solicitudes.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        return (
            Solicitud.objects.filter(solicitante=self.request.user)
            .select_related("servicio", "ciudad", "empresa_cliente", "operador")
            .prefetch_related("accesorios_solicitados", "observaciones", "reservas")
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            modulo_activo="mis-solicitudes",
            editar_form=EditarSolicitudForm(),
            cancelar_form=CancelarSolicitudForm(),
            observacion_form=ObservacionForm(),
        )
        return ctx


@nivel_requerido(4)
def export_mis_solicitudes_view(request):
    """Export a Excel de las solicitudes propias del solicitante (nivel 4)."""
    filas = [
        [
            s.codigo, s.fecha_solicitud, s.servicio.nombre, s.ciudad.nombre,
            s.personas, s.fecha_confirmada, s.operador.name if s.operador else "",
            s.estado_visual_display(),
        ]
        for s in Solicitud.objects.filter(solicitante=request.user).select_related("servicio", "ciudad", "operador")
    ]
    auditoria.registrar(request.user, "export_mis_solicitudes", "solicitudes", f"{len(filas)} filas")
    return workbook_response(
        "mis_solicitudes_rehavid.xlsx",
        "Mis solicitudes",
        ["Código", "Fecha solicitud", "Servicio", "Ciudad", "Personas", "Fecha confirmada", "Operador", "Estado"],
        filas,
    )


def _solicitud_propia_o_operador(request, pk) -> Solicitud:
    solicitud = get_object_or_404(Solicitud, pk=pk)
    if request.user.nivel > 2 and solicitud.solicitante_id != request.user.pk:  # noqa: PLR2004
        from django.core.exceptions import PermissionDenied  # noqa: PLC0415

        msg = "Solo puede operar sus propias solicitudes"
        raise PermissionDenied(msg)
    return solicitud


@nivel_requerido(4)
def editar_solicitud_view(request, pk):
    solicitud = _solicitud_propia_o_operador(request, pk)
    form = EditarSolicitudForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Datos inválidos para editar la solicitud")
        return redirect("portal:mis_solicitudes")
    try:
        services.editar_solicitud(
            solicitud, request.user,
            personas=form.cleaned_data["personas"],
            notas=form.cleaned_data["notas"],
        )
        messages.success(request, f"Solicitud {solicitud.codigo} actualizada")
    except SolicitudError as e:
        messages.error(request, str(e))
    return redirect("portal:mis_solicitudes")


@nivel_requerido(4)
def cancelar_solicitud_view(request, pk):
    solicitud = _solicitud_propia_o_operador(request, pk)
    form = CancelarSolicitudForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Indique el motivo de la cancelación")
        return redirect("portal:mis_solicitudes")
    try:
        services.cancelar_solicitud(solicitud, form.cleaned_data["motivo"], request.user)
        messages.success(request, f"Solicitud {solicitud.codigo} cancelada")
    except SolicitudError as e:
        messages.error(request, str(e))
    destino = "portal:mis_solicitudes" if request.user.nivel == 4 else "solicitudes:bandeja"  # noqa: PLR2004
    return redirect(destino)


@nivel_requerido(4)
def observacion_view(request, pk):
    solicitud = _solicitud_propia_o_operador(request, pk)
    form = ObservacionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Escriba la observación")
        return redirect("portal:mis_solicitudes")
    services.agregar_observacion(solicitud, form.cleaned_data["texto"], request.user)
    messages.success(request, f"Observación agregada a {solicitud.codigo}")
    destino = "portal:mis_solicitudes" if request.user.nivel == 4 else "solicitudes:bandeja"  # noqa: PLR2004
    return redirect(destino)


# ────────────────────────────────────────────────────────────
# Bandeja del operador (O17) · Atender crea la reserva (B2)
# ────────────────────────────────────────────────────────────
class BandejaView(NivelRequeridoMixin, ListView):
    nivel_maximo = 2
    template_name = "solicitudes/bandeja.html"
    context_object_name = "solicitudes"

    def get_queryset(self):
        qs = Solicitud.objects.select_related("servicio", "ciudad", "empresa_cliente", "solicitante")
        estado = self.request.GET.get("estado", "pendientes")
        if estado == "pendientes":
            qs = qs.filter(estado=EstadoSolicitud.PENDIENTE).order_by("creada_en")
        elif estado != "todas":
            qs = qs.filter(estado=estado)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        limite_urgencia = timezone.now() - timedelta(hours=HORAS_URGENCIA)
        for s in ctx["solicitudes"]:
            s.urgente = s.estado == EstadoSolicitud.PENDIENTE and s.creada_en <= limite_urgencia
        ctx.update(
            modulo_activo="bandeja",
            pendientes=services.contar_pendientes(),
            filtros=self.request.GET,
            estados=EstadoSolicitud.choices,
        )
        return ctx


@nivel_requerido(2)
def atender_view(request, pk):
    """B2 · atender = validar stock + crear la Reserva vinculada + confirmar."""
    solicitud = get_object_or_404(Solicitud, pk=pk)
    try:
        reserva = services.atender_solicitud(solicitud, request.user)
        messages.success(
            request,
            f"Solicitud {solicitud.codigo} atendida · reserva {reserva.codigo} creada "
            f"({reserva.equipos.count()} equipo(s) asignado(s))",
        )
    except (SolicitudError, ReservaError) as e:
        messages.error(request, f"{solicitud.codigo}: {e}")
    return redirect("solicitudes:bandeja")
