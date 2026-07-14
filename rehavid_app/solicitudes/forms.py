"""Formularios del portal solicitante (O11/O16/O19) y la bandeja."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio

DIAS_MINIMOS_ANTICIPACION = 7


class FechaInput(forms.DateInput):
    input_type = "date"


class SolicitudForm(forms.Form):
    """Formulario del portal (nivel 4). B4: la fecha pedida SÍ se persiste."""

    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.filter(activo=True),
        empty_label="— Servicio requerido —",
    )
    ciudad = forms.ModelChoiceField(queryset=Ciudad.objects.all(), empty_label="— Ciudad del estudio —")
    empresa_cliente = forms.ModelChoiceField(queryset=Empresa.objects.all(), label="Empresa")
    personas = forms.IntegerField(min_value=1, initial=1, label="Personas a evaluar")
    fecha_sugerida = forms.DateField(widget=FechaInput, label="Fecha sugerida del servicio")
    dias_estimados = forms.IntegerField(min_value=1, initial=1, label="Días estimados")
    notas = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)

    # O19 · profesional requerido
    prof_cantidad = forms.IntegerField(min_value=1, initial=1, label="Profesionales requeridos")
    prof_perfil = forms.CharField(max_length=120, label="Perfil del profesional")
    prof_nombre = forms.CharField(max_length=120, required=False, label="Nombre (si ya lo conoce)")
    prof_especialidad = forms.CharField(max_length=120, required=False, label="Especialidad")
    prof_telefono = forms.CharField(max_length=30, required=False, label="Teléfono de contacto")
    prof_correo = forms.EmailField(required=False, label="Correo de contacto")

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None and usuario.empresa_id:
            self.fields["empresa_cliente"].initial = usuario.empresa_id
        minimo = timezone.localdate() + timedelta(days=DIAS_MINIMOS_ANTICIPACION)
        self.fields["fecha_sugerida"].widget.attrs["min"] = minimo.isoformat()

    def clean_fecha_sugerida(self):
        fecha = self.cleaned_data["fecha_sugerida"]
        minimo = timezone.localdate() + timedelta(days=DIAS_MINIMOS_ANTICIPACION)
        if fecha < minimo:
            msg = f"La fecha debe ser al menos {DIAS_MINIMOS_ANTICIPACION} días después de hoy ({minimo})"
            raise forms.ValidationError(msg)
        return fecha


class EditarSolicitudForm(forms.Form):
    personas = forms.IntegerField(min_value=1)
    notas = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)


class CancelarSolicitudForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Motivo de la cancelación")


class ObservacionForm(forms.Form):
    texto = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Observación")
