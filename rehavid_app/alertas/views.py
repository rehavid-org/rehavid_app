"""Vistas de alertas logísticas (O21): detecciones, envío y canales (B10)."""

from django.contrib import messages
from django.shortcuts import redirect
from django.views.generic import TemplateView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.users.permissions import ModuloRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido

from . import services
from .models import AlertaEnviada
from .models import Canal
from .models import ConfiguracionCanal
from .services import AlertaError


class AlertasView(ModuloRequeridoMixin, TemplateView):
    modulo = "alertas"
    template_name = "alertas/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        canales = {c.canal: c for c in ConfiguracionCanal.objects.all()}
        ctx.update(
            modulo_activo="alertas",
            alertas=services.detectar_alertas(),
            canales=[
                {
                    "canal": valor,
                    "label": etiqueta,
                    "config": canales.get(valor),
                }
                for valor, etiqueta in Canal.choices
            ],
            historial=AlertaEnviada.objects.select_related("enviada_por")[:15],
        )
        return ctx


@nivel_requerido(2)
def enviar_view(request):
    tipo = request.POST.get("tipo", "")
    canal = request.POST.get("canal", "")
    mensaje = request.POST.get("mensaje", "")
    if not (tipo and canal and mensaje):
        messages.error(request, "Faltan datos de la alerta a enviar")
        return redirect("alertas:index")
    try:
        registro = services.enviar_alerta(tipo, canal, mensaje, request.user)
        if registro.resultado.startswith("error"):
            messages.error(request, f"El canal reportó un problema: {registro.resultado}")
        elif registro.resultado.startswith("stub"):
            messages.warning(request, f"Intento registrado · {registro.resultado}")
        else:
            messages.success(request, f"Alerta enviada por {registro.get_canal_display()} a {registro.destino}")
    except AlertaError as e:
        messages.error(request, str(e))
    return redirect("alertas:index")


@nivel_requerido(1)  # solo Admin Global modifica canales
def guardar_canales_view(request):
    for valor, _etiqueta in Canal.choices:
        ConfiguracionCanal.objects.update_or_create(
            canal=valor,
            defaults={
                "activo": f"activo-{valor}" in request.POST,
                "destino": request.POST.get(f"destino-{valor}", "").strip(),
            },
        )
    auditoria.registrar(request.user, "configurar_canales", "alertas", "canales actualizados")
    messages.success(request, "Configuración de canales guardada")
    return redirect("alertas:index")
