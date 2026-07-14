"""Formularios del módulo Administración (nivel 1) — B11/B13."""

from django import forms
from django.contrib.auth.forms import UserCreationForm

from rehavid_app.catalogo.models import Empresa

from .menu import MODULOS
from .models import PERMISOS_EXTRA
from .models import Nivel
from .models import User

CHOICES_MODULOS = [(clave, registro[0]) for clave, registro in MODULOS.items()]
CHOICES_PERMISOS = [(p, p.replace("_", " ").capitalize()) for p in PERMISOS_EXTRA]


class UsuarioCrearForm(UserCreationForm):
    """Alta real de usuarios (el prototipo tenía un stub) con hash Argon2."""

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ["username", "email", "name", "nivel", "empresa", "rol_descriptivo"]

    email = forms.EmailField(required=True)
    nivel = forms.TypedChoiceField(choices=Nivel.choices, coerce=int, initial=Nivel.SOLICITANTE)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False, empty_label="— Sin empresa —")


class UsuarioEditarForm(forms.ModelForm):
    """Edición + editor de permisos por módulo y permisos extra."""

    nivel = forms.TypedChoiceField(choices=Nivel.choices, coerce=int)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False, empty_label="— Sin empresa —")
    modulos_permitidos = forms.MultipleChoiceField(
        choices=CHOICES_MODULOS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Módulos permitidos (vacío = todos los de su nivel)",
    )
    permisos_extra = forms.MultipleChoiceField(
        choices=CHOICES_PERMISOS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permisos extra",
    )

    class Meta:
        model = User
        fields = ["name", "email", "nivel", "empresa", "rol_descriptivo", "modulos_permitidos", "permisos_extra"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.initial["modulos_permitidos"] = self.instance.modulos_permitidos or []
            self.initial["permisos_extra"] = self.instance.permisos_extra or []

    def clean_modulos_permitidos(self):
        # Lista vacía = sin restricción explícita → None (todos los del nivel)
        return list(self.cleaned_data["modulos_permitidos"]) or None

    def clean_permisos_extra(self):
        return list(self.cleaned_data["permisos_extra"])
