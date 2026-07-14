"""Módulo Administración (nivel 1): CRUD real de usuarios (B11/B13),
activar/desactivar, editor de permisos y ficha con actividad real (B12)."""

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import UpdateView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.auditoria.models import EventoAuditoria
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido

from .forms_admin import UsuarioCrearForm
from .forms_admin import UsuarioEditarForm
from .models import User


class UsuarioListView(NivelRequeridoMixin, ListView):
    nivel_maximo = 1
    model = User
    template_name = "administracion/usuarios.html"
    context_object_name = "usuarios"

    def get_queryset(self):
        qs = User.objects.select_related("empresa").order_by("nivel", "name")
        if q := self.request.GET.get("q", "").strip():
            qs = qs.filter(name__icontains=q) | qs.filter(email__icontains=q)
        if nivel := self.request.GET.get("nivel"):
            qs = qs.filter(nivel=nivel)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "modulo_activo": "admin",
            "filtros": self.request.GET,
        }


class UsuarioCreateView(NivelRequeridoMixin, CreateView):
    nivel_maximo = 1
    model = User
    form_class = UsuarioCrearForm
    template_name = "administracion/usuario_form.html"
    success_url = reverse_lazy("administracion:usuarios")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(
            self.request.user, "crear_usuario", "admin",
            f"{self.object.email} · nivel {self.object.nivel}",
        )
        messages.success(self.request, f"Usuario {self.object.email} creado")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {"modulo_activo": "admin", "titulo": "Nuevo usuario"}


class UsuarioUpdateView(NivelRequeridoMixin, UpdateView):
    nivel_maximo = 1
    model = User
    form_class = UsuarioEditarForm
    template_name = "administracion/usuario_form.html"
    success_url = reverse_lazy("administracion:usuarios")

    def form_valid(self, form):
        response = super().form_valid(form)
        auditoria.registrar(
            self.request.user, "editar_usuario", "admin",
            f"{self.object.email} · nivel {self.object.nivel} · módulos {self.object.modulos_permitidos or 'todos'}",
        )
        messages.success(self.request, f"Usuario {self.object.email} actualizado")
        return response

    def get_context_data(self, **kwargs):
        return super().get_context_data(**kwargs) | {
            "modulo_activo": "admin",
            "titulo": f"Editar {self.object.email}",
        }


class UsuarioFichaView(NivelRequeridoMixin, DetailView):
    """Ficha con actividad REAL desde auditoría (el prototipo la inventaba — B12)."""

    nivel_maximo = 1
    model = User
    template_name = "administracion/usuario_ficha.html"
    context_object_name = "usuario"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        eventos = EventoAuditoria.objects.filter(usuario=self.object)
        ctx.update(
            modulo_activo="admin",
            eventos=eventos[:25],
            eventos_total=eventos.count(),
            solicitudes_total=self.object.solicitudes.count() if hasattr(self.object, "solicitudes") else 0,
        )
        return ctx


@nivel_requerido(1)
def toggle_activo_view(request, pk):
    usuario = get_object_or_404(User, pk=pk)
    if usuario.pk == request.user.pk:
        messages.error(request, "No puede desactivar su propia cuenta")
        return redirect("administracion:usuarios")
    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=["is_active"])
    accion = "activar_usuario" if usuario.is_active else "desactivar_usuario"
    auditoria.registrar(request.user, accion, "admin", usuario.email)
    estado = "activado" if usuario.is_active else "desactivado (no podrá iniciar sesión)"
    messages.success(request, f"Usuario {usuario.email} {estado}")
    return redirect("administracion:usuarios")
