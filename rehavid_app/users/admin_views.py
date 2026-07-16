"""Módulo Administración (nivel 1): CRUD real de usuarios (B11/B13),
activar/desactivar, editor de permisos y ficha con actividad real (B12)."""

from collections import Counter
from datetime import timedelta

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView
from django.views.generic import DetailView
from django.views.generic import ListView
from django.views.generic import TemplateView
from django.views.generic import UpdateView

from rehavid_app.auditoria import services as auditoria
from rehavid_app.auditoria.models import EventoAuditoria
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido
from rehavid_app.xlsx import workbook_response

from .forms_admin import UsuarioCrearForm
from .forms_admin import UsuarioEditarForm
from .models import User

ARQUITECTURA_STACK = [
    ("Cloud", "Azure West Europe"),
    ("Hosting", "Azure App Service · Linux container"),
    ("Identidad", "Microsoft Entra ID (ex Azure AD)"),
    ("Base de datos", "PostgreSQL 16 (Azure Database for PostgreSQL)"),
    ("Archivos", "Azure Blob Storage"),
    ("Backend", "Python 3.14 · Django 6.0"),
    ("Modelos ML", "scikit-learn · Azure ML Workspace"),
    ("Observabilidad", "Application Insights + Log Analytics"),
    ("CI / CD", "GitHub Actions"),
    ("Protección código", "Imagen no-root, sin lógica sensible expuesta al frontend"),
]


class ArquitecturaView(NivelRequeridoMixin, TemplateView):
    """Documentación/roadmap interno (no es un dashboard de negocio): stack
    Azure planeado, árbol de apps del ecosistema y spec del módulo común
    "Planes de acción". Las apps "planeadas" (Salud ocupacional, Comercial)
    son roadmap y no existen en el código, así que no hay dato real que
    mostrar ahí; la rama de "Rehavid · Operaciones" (que sí existe) muestra
    conteos reales en vez de ser solo una etiqueta."""

    nivel_maximo = 1
    template_name = "administracion/arquitectura.html"

    def get_context_data(self, **kwargs):
        from rehavid_app.planes.models import Plan  # noqa: PLC0415
        from rehavid_app.predictivo.models import PrediccionRegistro  # noqa: PLC0415
        from rehavid_app.reservas.models import Reserva  # noqa: PLC0415

        return super().get_context_data(**kwargs) | {
            "modulo_activo": "arquitectura",
            "stack": ARQUITECTURA_STACK,
            "conteos_operaciones": {
                "reservas": Reserva.objects.filter(cancelada=False).count(),
                "predicciones": PrediccionRegistro.objects.count(),
                "planes": Plan.objects.count(),
            },
        }


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
            "kpis": self._kpis(),
            "usuarios_por_empresa": self._usuarios_por_empresa(),
            "actividad_30_dias": self._actividad_30_dias(),
        }

    @staticmethod
    def _kpis():
        """Banner de acceso: en el prototipo origen estos 4 KPIs eran texto fijo
        y ni siquiera cuadraban con los propios datos mock; acá salen de la BD."""
        desde_7d = timezone.localdate() - timedelta(days=7)
        return {
            "usuarios_activos": User.objects.filter(is_active=True).count(),
            "usuarios_total": User.objects.count(),
            "empresas": User.objects.values("empresa").distinct().count(),
            "administradores": User.objects.filter(nivel=1).count(),
            "acciones_7_dias": EventoAuditoria.objects.filter(timestamp__date__gte=desde_7d).count(),
        }

    @staticmethod
    def _usuarios_por_empresa():
        nombres = (n or "Sin empresa" for n in User.objects.values_list("empresa__nombre", flat=True))
        conteo = Counter(nombres)
        return {"empresas": list(conteo.keys()), "conteos": list(conteo.values())}

    @staticmethod
    def _actividad_30_dias():
        """Actividad real (no sintética) desde EventoAuditoria de los últimos 30 días."""
        desde = timezone.localdate() - timedelta(days=29)
        eventos = EventoAuditoria.objects.filter(timestamp__date__gte=desde).values_list(
            "timestamp", "accion",
        )
        por_dia = {desde + timedelta(days=i): {"logins": 0, "creaciones": 0, "exportes": 0} for i in range(30)}
        for ts, accion in eventos:
            dia = por_dia.get(timezone.localtime(ts).date())
            if dia is None:
                continue
            if accion == "login":
                dia["logins"] += 1
            elif "export" in accion:
                dia["exportes"] += 1
            elif accion.startswith("crear_"):
                dia["creaciones"] += 1
        dias = sorted(por_dia)
        return {
            "dias": [d.strftime("%d-%m") for d in dias],
            "logins": [por_dia[d]["logins"] for d in dias],
            "creaciones": [por_dia[d]["creaciones"] for d in dias],
            "exportes": [por_dia[d]["exportes"] for d in dias],
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


@nivel_requerido(1)
def export_usuarios_view(request):
    filas = [
        [
            u.email, u.name, u.get_nivel_display(), u.empresa.nombre if u.empresa else "",
            u.rol_descriptivo, "Sí" if u.is_active else "No",
            timezone.localtime(u.last_login).strftime("%Y-%m-%d %H:%M:%S") if u.last_login else "",
        ]
        for u in User.objects.select_related("empresa").order_by("nivel", "name")
    ]
    auditoria.registrar(request.user, "export_usuarios", "admin", f"{len(filas)} filas")
    return workbook_response(
        "usuarios_rehavid.xlsx",
        "Usuarios",
        ["Correo", "Nombre", "Nivel", "Empresa", "Rol", "Activo", "Último acceso"],
        filas,
    )
