from django import forms

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio

SECTORES = ["Administrativo", "Agroindustria", "Construcción", "Logística", "Manufactura", "Salud", "Servicios"]
JORNADAS = ["Diurna fija", "Nocturna fija", "Turnos rotativos", "Mixta"]


class PrediccionForm(forms.Form):
    servicio = forms.ModelChoiceField(
        queryset=Servicio.objects.filter(activo=True),
        empty_label="— Servicio —",
    )
    ciudad = forms.ModelChoiceField(queryset=Ciudad.objects.all(), empty_label="— Ciudad —")
    cliente = forms.ModelChoiceField(queryset=Empresa.objects.all(), empty_label="— Empresa cliente —")
    personas = forms.IntegerField(min_value=1, initial=5, label="Personas a evaluar")
    sector = forms.ChoiceField(choices=[(s, s) for s in SECTORES], required=False, label="Sector industrial")
    jornada = forms.ChoiceField(choices=[(j, j) for j in JORNADAS], required=False, label="Tipo de jornada")
