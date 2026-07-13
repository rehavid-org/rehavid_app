import pytest
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory
from django.views.generic import View

from rehavid_app.users.models import MENU_BY_LEVEL
from rehavid_app.users.models import User
from rehavid_app.users.permissions import NivelRequeridoMixin
from rehavid_app.users.permissions import nivel_requerido
from rehavid_app.users.permissions import require_nivel
from rehavid_app.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


class VistaNivel2(NivelRequeridoMixin, View):
    nivel_maximo = 2

    def get(self, request):
        return HttpResponse("ok")


@nivel_requerido(1)
def vista_solo_admin(request):
    return HttpResponse("ok")


def _user(nivel: int) -> User:
    return UserFactory(nivel=nivel)


@pytest.mark.parametrize(("nivel", "permitido"), [(1, True), (2, True), (3, False), (4, False)])
def test_mixin_nivel_maximo_2(rf: RequestFactory, nivel: int, permitido: bool):
    request = rf.get("/x/")
    request.user = _user(nivel)
    if permitido:
        assert VistaNivel2.as_view()(request).status_code == 200
    else:
        with pytest.raises(PermissionDenied):
            VistaNivel2.as_view()(request)


@pytest.mark.parametrize(("nivel", "permitido"), [(1, True), (2, False), (4, False)])
def test_decorador_nivel_1(rf: RequestFactory, nivel: int, permitido: bool):
    request = rf.get("/x/")
    request.user = _user(nivel)
    if permitido:
        assert vista_solo_admin(request).status_code == 200
    else:
        with pytest.raises(PermissionDenied):
            vista_solo_admin(request)


@pytest.mark.parametrize(("nivel", "permitido"), [(1, True), (2, True), (3, True), (4, False)])
def test_drf_require_nivel_3(rf: RequestFactory, nivel: int, permitido: bool):
    permiso = require_nivel(3)()
    request = rf.get("/x/")
    request.user = _user(nivel)
    assert permiso.has_permission(request, None) is permitido


def test_modulos_por_defecto_segun_nivel():
    assert _user(3).modulos == MENU_BY_LEVEL[3]
    assert "admin" in _user(1).modulos
    assert "admin" not in _user(2).modulos


def test_modulos_explicitos_ganan():
    user = UserFactory(nivel=3, modulos_permitidos=["calendario"])
    assert user.modulos == ["calendario"]
    assert user.puede_ver_modulo("calendario")
    assert not user.puede_ver_modulo("equipos")


def test_permisos_extra():
    user = UserFactory(nivel=3, permisos_extra=["agregar_equipos"])
    assert user.tiene_permiso_extra("agregar_equipos")
    assert not user.tiene_permiso_extra("editar_usuarios")
