"""Predictivo MSK: vista con gauge + factores + diagrama corporal (B16)."""

import json

from django.views.generic import FormView

from rehavid_app.users.permissions import ModuloRequeridoMixin

from . import services
from .forms import PrediccionForm
from .models import PrediccionRegistro


class PredictivoView(ModuloRequeridoMixin, FormView):
    modulo = "predictivo"
    form_class = PrediccionForm
    template_name = "predictivo/index.html"

    def form_valid(self, form):
        d = form.cleaned_data
        resultado = services.obtener_prediccion(
            {
                "servicio": d["servicio"].nombre,
                "ciudad": d["ciudad"].nombre,
                "cliente": d["cliente"].nombre,
                "personas": d["personas"],
                "sector": d["sector"],
                "jornada": d["jornada"],
            },
            usuario=self.request.user,
        )
        return self.render_to_response(self.get_context_data(form=form, resultado=resultado))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        resultado = kwargs.get("resultado")
        distribucion = services.distribucion_riesgo()
        diagrama = services.diagrama_corporal_poblacional()
        trayectoria = services.trayectoria_por_cliente()
        ctx.update(
            modulo_activo="predictivo",
            resultado=resultado,
            resultado_json=json.dumps(resultado) if resultado else "null",
            historial=PrediccionRegistro.objects.select_related("usuario")[:10],
            distribucion_riesgo=distribucion,
            distribucion_riesgo_json=json.dumps(distribucion),
            diagrama_corporal=diagrama,
            diagrama_corporal_json=json.dumps(diagrama),
            trayectoria=trayectoria,
            trayectoria_json=json.dumps(trayectoria),
        )
        return ctx
