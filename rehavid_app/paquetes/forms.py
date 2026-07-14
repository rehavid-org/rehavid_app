from django import forms

from rehavid_app.catalogo.models import Servicio

from .models import Paquete


class PaqueteForm(forms.ModelForm):
    servicios_requeridos = forms.ModelMultipleChoiceField(
        queryset=Servicio.objects.filter(activo=True),
        widget=forms.CheckboxSelectMultiple,
        label="Categorías incluidas (un equipo por cada una)",
    )

    class Meta:
        model = Paquete
        fields = ["codigo", "nombre", "descripcion", "servicios_requeridos", "duracion_dias", "activo"]
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 2})}
