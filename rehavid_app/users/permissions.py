"""Autorización por nivel Rehavid (1 Admin Global … 4 Solicitante).

Equivalente Django del ``require_nivel`` del backend FastAPI, aplicado
en servidor (no solo ocultando botones — corrige B1). Un usuario pasa el
chequeo cuando su nivel es <= al nivel máximo exigido.
"""

from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def _tiene_nivel(user, max_nivel: int) -> bool:
    return user.is_authenticated and user.nivel <= max_nivel


def nivel_requerido(max_nivel: int):
    """Decorador para vistas de función: exige nivel <= max_nivel."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.contrib.auth.views import redirect_to_login  # noqa: PLC0415

                return redirect_to_login(request.get_full_path())
            if not _tiene_nivel(request.user, max_nivel):
                msg = f"Se requiere nivel {max_nivel} o superior"
                raise PermissionDenied(msg)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


class NivelRequeridoMixin(LoginRequiredMixin):
    """Mixin para CBV: ``nivel_maximo = 2`` permite niveles 1 y 2."""

    nivel_maximo = 4

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not _tiene_nivel(request.user, self.nivel_maximo):
            msg = f"Se requiere nivel {self.nivel_maximo} o superior · usted es nivel {request.user.nivel}"
            raise PermissionDenied(msg)
        return super().dispatch(request, *args, **kwargs)


class ModuloRequeridoMixin(LoginRequiredMixin):
    """Mixin para CBV: exige que el módulo esté en ``user.modulos``."""

    modulo = ""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and self.modulo and not request.user.puede_ver_modulo(self.modulo):
            msg = f"No tiene acceso al módulo '{self.modulo}'"
            raise PermissionDenied(msg)
        return super().dispatch(request, *args, **kwargs)


def require_nivel(max_nivel: int) -> type[BasePermission]:
    """Factory de permiso DRF: ``permission_classes = [require_nivel(2)]``."""

    class _NivelPermission(BasePermission):
        message = f"Se requiere nivel {max_nivel} o superior"

        def has_permission(self, request, view):
            return _tiene_nivel(request.user, max_nivel)

    _NivelPermission.__name__ = f"Nivel{max_nivel}Permission"
    return _NivelPermission
