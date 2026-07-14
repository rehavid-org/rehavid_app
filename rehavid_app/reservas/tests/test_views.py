"""Flujo de operación por las vistas (Fase 4): crear → reprogramar →
retorno → listo, y cancelación, contra los servicios reales."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.reservas.models import Reserva
from rehavid_app.users.tests.factories import UserFactory

from .factories import CiudadFactory
from .factories import EmpresaFactory
from .factories import EquipoFactory
from .factories import PaqueteFactory
from .factories import ServicioFactory

pytestmark = pytest.mark.django_db

HTTP_REDIRECT = 302


def hoy():
    return timezone.localdate()


@pytest.fixture
def operador():
    return UserFactory(username="op-vistas", nivel=2)


@pytest.fixture
def base(operador, client):
    client.force_login(operador)
    servicio = ServicioFactory()
    equipo = EquipoFactory(servicio=servicio)
    return {
        "client": client,
        "servicio": servicio,
        "equipo": equipo,
        "cliente": EmpresaFactory(),
        "ciudad": CiudadFactory(),
    }


def _crear(base, **extra):
    data = {
        "tipo": "servicio",
        "servicio": base["servicio"].pk,
        "cliente": base["cliente"].pk,
        "ciudad": base["ciudad"].pk,
        "personas": 3,
        "fecha_salida": hoy() + timedelta(days=5),
        "fecha_retorno_esp": hoy() + timedelta(days=7),
    }
    data.update(extra)
    return base["client"].post(reverse("reservas:nueva"), data)


def test_crear_reserva_desde_vista(base):
    response = _crear(base)
    assert response.status_code == HTTP_REDIRECT
    reserva = Reserva.objects.latest("pk")
    assert list(reserva.equipos.all()) == [base["equipo"]]
    base["equipo"].refresh_from_db()
    assert base["equipo"].estado == EstadoEquipo.EN_USO


def test_crear_reserva_paquete_desde_vista(base):
    s2 = ServicioFactory()
    EquipoFactory(servicio=s2)
    paquete = PaqueteFactory(servicios=[base["servicio"], s2])
    response = _crear(base, tipo="paquete", paquete=paquete.pk, servicio="")
    assert response.status_code == HTTP_REDIRECT
    reserva = Reserva.objects.latest("pk")
    assert reserva.paquete == paquete
    assert reserva.equipos.count() == 2


def test_stock_agotado_reexhibe_formulario_con_error(base):
    _crear(base)
    response = _crear(base)  # mismo rango, único equipo ya tomado
    assert response.status_code == 200
    assert "Stock agotado" in response.content.decode()


def test_flujo_reprogramar_retorno_listo(base):
    _crear(base)
    reserva = Reserva.objects.latest("pk")
    client = base["client"]

    response = client.post(
        reverse("reservas:reprogramar", kwargs={"pk": reserva.pk}),
        {
            "nueva_fecha_salida": hoy() + timedelta(days=10),
            "nueva_fecha_retorno": hoy() + timedelta(days=12),
            "motivo": "Cliente pide mover",
        },
    )
    assert response.status_code == HTTP_REDIRECT
    reserva.refresh_from_db()
    assert reserva.fecha_salida == hoy() + timedelta(days=10)

    response = client.post(
        reverse("reservas:retorno", kwargs={"pk": reserva.pk}),
        {"estado_kit": "OK", "notas": "", "requiere_preparacion": "on"},
    )
    assert response.status_code == HTTP_REDIRECT
    base["equipo"].refresh_from_db()
    assert base["equipo"].estado == EstadoEquipo.EN_PREPARACION

    response = client.post(
        reverse("equipos:listo", kwargs={"pk": base["equipo"].pk}),
        {"notas": "lavado ok"},
    )
    assert response.status_code == HTTP_REDIRECT
    base["equipo"].refresh_from_db()
    assert base["equipo"].estado == EstadoEquipo.DISPONIBLE


def test_cancelar_libera_equipo(base):
    _crear(base)
    reserva = Reserva.objects.latest("pk")
    response = base["client"].post(
        reverse("reservas:cancelar", kwargs={"pk": reserva.pk}),
        {"motivo": "Cliente canceló"},
    )
    assert response.status_code == HTTP_REDIRECT
    reserva.refresh_from_db()
    assert reserva.cancelada
    base["equipo"].refresh_from_db()
    assert base["equipo"].estado == EstadoEquipo.DISPONIBLE


def test_lista_filtra_por_estado(base):
    _crear(base)
    reserva = Reserva.objects.latest("pk")
    base["client"].post(reverse("reservas:cancelar", kwargs={"pk": reserva.pk}), {"motivo": "x"})
    response = base["client"].get(reverse("reservas:lista"), {"estado": "canceladas"})
    assert reserva.codigo in response.content.decode()
    response = base["client"].get(reverse("reservas:lista"), {"estado": "activas"})
    assert reserva.codigo not in response.content.decode()
