"""Formularios de operación de reservas. La validación de negocio vive en
``services.py``; aquí solo se valida la forma de los datos."""

from django import forms

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio
from rehavid_app.paquetes.models import Paquete

from .models import ConfirmacionRetorno


class FechaInput(forms.DateInput):
    input_type = "date"


class ReservaForm(forms.Form):
    """B3 · formulario Nueva Reserva (servicio individual o paquete)."""

    TIPO_SERVICIO = "servicio"
    TIPO_PAQUETE = "paquete"

    tipo = forms.ChoiceField(
        choices=[(TIPO_SERVICIO, "Servicio individual"), (TIPO_PAQUETE, "Paquete multi-equipo")],
        initial=TIPO_SERVICIO,
        widget=forms.RadioSelect,
    )
    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.filter(activo=True),
        required=False,
        empty_label="— Seleccione servicio —",
    )
    paquete = forms.ModelChoiceField(
        queryset=Paquete.objects.filter(activo=True),
        required=False,
        empty_label="— Seleccione paquete —",
    )
    cliente = forms.ModelChoiceField(
        queryset=Empresa.objects.all(),
        empty_label="— Empresa cliente —",
    )
    ciudad = forms.ModelChoiceField(
        queryset=Ciudad.objects.all(),
        empty_label="— Ciudad —",
    )
    personas = forms.IntegerField(min_value=1, initial=1, label="Personas a evaluar")
    fecha_salida = forms.DateField(widget=FechaInput)
    fecha_retorno_esp = forms.DateField(widget=FechaInput, label="Fecha retorno esperada")

    def clean(self):
        data = super().clean()
        tipo = data.get("tipo")
        if tipo == self.TIPO_SERVICIO and not data.get("servicio"):
            self.add_error("servicio", "Seleccione el servicio a reservar")
        if tipo == self.TIPO_PAQUETE and not data.get("paquete"):
            self.add_error("paquete", "Seleccione el paquete a reservar")
        salida, retorno = data.get("fecha_salida"), data.get("fecha_retorno_esp")
        if salida and retorno and retorno < salida:
            self.add_error("fecha_retorno_esp", "El retorno no puede ser anterior a la salida")
        return data


class ReprogramarForm(forms.Form):
    nueva_fecha_salida = forms.DateField(widget=FechaInput)
    nueva_fecha_retorno = forms.DateField(widget=FechaInput)
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    def clean(self):
        data = super().clean()
        salida, retorno = data.get("nueva_fecha_salida"), data.get("nueva_fecha_retorno")
        if salida and retorno and retorno < salida:
            self.add_error("nueva_fecha_retorno", "El retorno no puede ser anterior a la salida")
        return data


class CancelarForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Motivo de cancelación")


class RetornoForm(forms.Form):
    estado_kit = forms.ChoiceField(choices=ConfirmacionRetorno.EstadoKit.choices, label="Estado del kit")
    notas = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    requiere_preparacion = forms.BooleanField(
        required=False,
        label="Requiere preparación (lavado / revisión, bloquea +1 día)",
    )
