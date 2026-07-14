"""Vistas de analítica. Fase 4: calendario 12 meses server-rendered.
Brief/dashboard/recomendaciones llegan en Fase 6."""

import calendar
from datetime import date
from datetime import timedelta

from django.utils import timezone
from django.views.generic import TemplateView

from rehavid_app.catalogo.models import Servicio
from rehavid_app.reservas.models import Reserva
from rehavid_app.users.permissions import ModuloRequeridoMixin

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
