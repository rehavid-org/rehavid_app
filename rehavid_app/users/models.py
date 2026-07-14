from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _


class Nivel(models.IntegerChoices):
    """Niveles de acceso Rehavid. 1 = más permisos, 4 = menos."""

    ADMIN_GLOBAL = 1, "Admin Global"
    OPERADOR = 2, "Operador"
    COORDINADOR = 3, "Coordinador Programación"
    SOLICITANTE = 4, "Solicitante"


# Menú visible por nivel (espejo de MENU_BY_LEVEL del prototipo)
MENU_BY_LEVEL: dict[int, list[str]] = {
    1: [
        "brief",
        "dashboard",
        "predictivo",
        "recos",
        "planes",
        "reservas",
        "bandeja",
        "equipos",
        "paquetes",
        "calendario",
        "alertas",
        "admin",
        "auditoria",
    ],
    2: [
        "brief",
        "dashboard",
        "predictivo",
        "recos",
        "planes",
        "reservas",
        "bandeja",
        "equipos",
        "paquetes",
        "calendario",
        "alertas",
    ],
    3: ["calendario", "equipos", "paquetes"],
    4: ["portal", "calendario", "equipos-disp", "solicitar", "mis-solicitudes"],
}

# Permisos extra granulares (checkboxes del editor de permisos)
PERMISOS_EXTRA = ["agregar_equipos", "editar_inventario", "editar_usuarios"]


class User(AbstractUser):
    """
    Default custom user model for rehavid app.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]

    nivel = models.PositiveSmallIntegerField(
        choices=Nivel.choices,
        default=Nivel.SOLICITANTE,
        db_index=True,
    )
    empresa = models.ForeignKey(
        "catalogo.Empresa",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
    )
    rol_descriptivo = models.CharField(
        max_length=120,
        blank=True,
        help_text="Cargo visible, p.ej. 'Coordinadora General'",
    )
    # None = todos los módulos de su nivel; lista = subconjunto explícito
    modulos_permitidos = models.JSONField(null=True, blank=True, default=None)
    permisos_extra = models.JSONField(default=list, blank=True)

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        return reverse("users:detail", kwargs={"username": self.username})

    @property
    def modulos(self) -> list[str]:
        """Módulos visibles: la lista explícita o el menú completo de su nivel."""
        if self.modulos_permitidos:
            return self.modulos_permitidos
        return MENU_BY_LEVEL.get(self.nivel, [])

    def puede_ver_modulo(self, modulo: str) -> bool:
        return modulo in self.modulos

    def tiene_permiso_extra(self, permiso: str) -> bool:
        return permiso in (self.permisos_extra or [])
