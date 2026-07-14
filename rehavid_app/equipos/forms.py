from django import forms

from .models import Equipo


class FechaInput(forms.DateInput):
    input_type = "date"


class EquipoForm(forms.ModelForm):
    """B7 · alta manual con el modelo canónico único del inventario."""

    class Meta:
        model = Equipo
        fields = [
            "codigo",
            "servicio",
            "modelo",
            "serial",
            "ciudad_base",
            "responsable",
            "ultima_revision",
            "proxima_mantencion",
            "notas",
        ]
        widgets = {
            "ultima_revision": FechaInput(),
            "proxima_mantencion": FechaInput(),
            "notas": forms.Textarea(attrs={"rows": 2}),
        }


class MantenimientoForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Motivo del mantenimiento")


class BajaForm(forms.Form):
    motivo = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), label="Motivo de la baja definitiva")


class ListoForm(forms.Form):
    notas = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False, label="Notas de la preparación")
