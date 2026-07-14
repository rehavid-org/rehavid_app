"""Vistas de analítica: calendario, brief ejecutivo, dashboard y
motor de recomendaciones (todo calculado de la BD — B15)."""

import calendar
from datetime import date
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Servicio
from rehavid_app.reservas.models import Reserva
from rehavid_app.users.permissions import ModuloRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido

from . import services

DIAS_SEMANA = ["L", "M", "X", "J", "V", "S", "D"]
MESES_ANIO = 12
DENSIDAD_TOPE = 3  # 3+ reservas/día = intensidad máxima de la escala


def _meses_desde(inicio: date, cantidad: int = MESES_ANIO):
    anio, mes = inicio.year, inicio.month
    for _ in range(cantidad):
        yield anio, mes
        mes += 1
        if mes > MESES_ANIO:
            mes, anio = 1, anio + 1


def _filtros_analitica(request) -> dict:
    p = request.GET
    return {
        "desde": p.get("desde") or None,
        "hasta": p.get("hasta") or None,
        "servicio": p.get("servicio") or None,
        "ciudad": p.get("ciudad") or None,
    }


class BriefView(ModuloRequeridoMixin, TemplateView):
    """Brief ejecutivo: KPIs de BD + top findings + próximas salidas."""

    modulo = "brief"
    template_name = "analitica/brief.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        findings = services.analizar()
        ctx.update(
            modulo_activo="brief",
            kpis=services.kpis(),
            findings=findings[:5],
            findings_total=len(findings),
            proximas_salidas=(
                Reserva.objects.filter(cancelada=False, fecha_salida__gte=hoy)
                .select_related("servicio", "cliente", "ciudad")
                .order_by("fecha_salida")[:8]
            ),
            retornos_proximos=(
                Reserva.objects.filter(
                    cancelada=False, confirmacion_retorno__isnull=True,
                    fecha_retorno_esp__gte=hoy, fecha_retorno_esp__lte=hoy + timedelta(days=7),
                )
                .select_related("servicio", "cliente")
                .order_by("fecha_retorno_esp")[:8]
            ),
        )
        return ctx


class DashboardView(ModuloRequeridoMixin, TemplateView):
    """Dashboard con filtros; los charts ECharts se alimentan del endpoint JSON."""

    modulo = "dashboard"
    template_name = "analitica/dashboard.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filtros = _filtros_analitica(self.request)
        ctx.update(
            modulo_activo="dashboard",
            kpis=services.kpis(**filtros),
            servicios=Servicio.objects.filter(activo=True),
            ciudades=Ciudad.objects.all(),
            filtros=self.request.GET,
        )
        return ctx


class RecosView(ModuloRequeridoMixin, TemplateView):
    """Motor de recomendaciones: los 11 detectores + convertir finding→plan."""

    modulo = "recos"
    template_name = "analitica/recos.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        findings = services.analizar()
        areas = sorted({f.area for f in findings})
        if area := self.request.GET.get("area"):
            findings = [f for f in findings if f.area == area]
        ctx.update(
            modulo_activo="recos",
            findings=findings,
            areas=areas,
            filtros=self.request.GET,
        )
        return ctx


@nivel_requerido(2)
def crear_plan_desde_finding_view(request, finding_id):
    try:
        plan = services.crear_plan_desde_finding(finding_id, request.user)
        messages.success(request, f"Plan {plan.codigo} creado desde la recomendación")
        return redirect("planes:lista")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("analitica:recos")


class CalendarioView(ModuloRequeridoMixin, TemplateView):
    """Rejilla de 12 meses con densidad de reservas por día + detalle por día."""

    modulo = "calendario"
    template_name = "analitica/calendario.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        hoy = timezone.localdate()
        inicio = hoy.replace(day=1)
        meses = list(_meses_desde(inicio))
        fin_anio, fin_mes = meses[-1]
        fin = date(fin_anio, fin_mes, calendar.monthrange(fin_anio, fin_mes)[1])

        reservas = (
            Reserva.objects.filter(
                cancelada=False,
                fecha_salida__lte=fin,
                fecha_retorno_esp__gte=inicio,
            )
            .select_related("servicio", "cliente", "ciudad")
        )
        if servicio := self.request.GET.get("servicio"):
            reservas = reservas.filter(servicio_id=servicio)

        # Densidad por día (una reserva ocupa salida→retorno completo)
        densidad: dict[date, list[Reserva]] = {}
        for r in reservas:
            dia = max(r.fecha_salida, inicio)
            tope = min(r.fecha_retorno_esp, fin)
            while dia <= tope:
                densidad.setdefault(dia, []).append(r)
                dia += timedelta(days=1)

        dia_sel = None
        if raw := self.request.GET.get("dia"):
            try:
                dia_sel = date.fromisoformat(raw)
            except ValueError:
                dia_sel = None

        cal = calendar.Calendar(firstweekday=0)  # lunes
        meses_render = []
        for anio, mes in meses:
            semanas = []
            for semana in cal.monthdayscalendar(anio, mes):
                fila = []
                for num in semana:
                    if num == 0:
                        fila.append(None)
                        continue
                    d = date(anio, mes, num)
                    n = len(densidad.get(d, []))
                    clase = "d3" if n >= DENSIDAD_TOPE else f"d{n}" if n else ""
                    fila.append({"fecha": d, "n": n, "clase": clase})
                semanas.append(fila)
            meses_render.append({
                "nombre": date(anio, mes, 1),
                "semanas": semanas,
            })

        ctx.update(
            modulo_activo="calendario",
            meses=meses_render,
            dias_semana=DIAS_SEMANA,
            hoy=hoy,
            dia_sel=dia_sel,
            reservas_dia=sorted(densidad.get(dia_sel, []), key=lambda r: r.codigo) if dia_sel else [],
            servicios=Servicio.objects.filter(activo=True),
            filtros=self.request.GET,
        )
        return ctx
