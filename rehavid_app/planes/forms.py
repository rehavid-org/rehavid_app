from django import forms

from .models import Plan


class FechaInput(forms.DateInput):
    input_type = "date"


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = ["area", "titulo", "descripcion", "responsable", "vence", "avance", "esperado", "estado"]
        widgets = {
            "vence": FechaInput(),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }
