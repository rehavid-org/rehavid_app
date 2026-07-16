"""Registro central del menú lateral (espejo del sidebar del prototipo).

Cada módulo de ``MENU_BY_LEVEL`` apunta aquí a su etiqueta, url y sección.
El context processor ``sidebar_menu`` arma la lista visible para el usuario
autenticado a partir de ``user.modulos`` (que ya aplica nivel + subconjunto
explícito de ``modulos_permitidos``).
"""

from dataclasses import dataclass

from django.urls import NoReverseMatch
from django.urls import reverse


@dataclass(frozen=True)
class ItemMenu:
    modulo: str
    etiqueta: str
    url: str
    seccion: str
    activo: bool


# modulo → (etiqueta, url_name, sección del sidebar)
MODULOS: dict[str, tuple[str, str, str]] = {
    "brief": ("Resumen ejecutivo", "analitica:brief", "Dirección"),
    "dashboard": ("Dashboard", "analitica:dashboard", "Dirección"),
    "predictivo": ("Predictivo MSK", "predictivo:index", "Dirección"),
    "recos": ("Recomendaciones", "analitica:recos", "Dirección"),
    "planes": ("Planes de acción", "planes:lista", "Dirección"),
    "reservas": ("Reservas", "reservas:lista", "Operación"),
    "bandeja": ("Bandeja de solicitudes", "solicitudes:bandeja", "Operación"),
    "equipos": ("Equipos", "equipos:lista", "Operación"),
    "paquetes": ("Paquetes", "paquetes:lista", "Operación"),
    "calendario": ("Calendario", "analitica:calendario", "Operación"),
    "alertas": ("Alertas logísticas", "alertas:index", "Operación"),
    "admin": ("Administración", "administracion:usuarios", "Sistema"),
    "auditoria": ("Auditoría", "auditoria:lista", "Sistema"),
    "arquitectura": ("Arquitectura macro-app", "administracion:arquitectura", "Sistema"),
    "portal": ("Inicio", "portal:inicio", "Portal"),
    "equipos-disp": ("Equipos disponibles", "portal:equipos", "Portal"),
    "solicitar": ("Solicitar servicio", "portal:solicitar", "Portal"),
    "mis-solicitudes": ("Mis solicitudes", "portal:mis_solicitudes", "Portal"),
}


def items_para(user) -> list[ItemMenu]:
    items = []
    for modulo in user.modulos:
        registro = MODULOS.get(modulo)
        if not registro:
            continue
        etiqueta, url_name, seccion = registro
        try:
            url = reverse(url_name)
        except NoReverseMatch:
            continue
        items.append(ItemMenu(modulo, etiqueta, url, seccion, activo=True))
    return items


def sidebar_menu(request):
    """Context processor: menú del sidebar para el usuario autenticado."""
    if not request.user.is_authenticated:
        return {"menu_items": []}
    return {"menu_items": items_para(request.user)}
