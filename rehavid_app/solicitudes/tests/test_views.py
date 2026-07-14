"""E2E Fase 5: solicitante crea → operador atiende → reserva creada (B2)
→ solicitante la ve confirmada. Más reglas 48h, edición y accesos."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from rehavid_app.catalogo.models import AccesorioTipo
from rehavid_app.reservas.tests.factories import CiudadFactory
from rehavid_app.reservas.tests.factories import EmpresaFactory
from rehavid_app.reservas.tests.factories import EquipoFactory
from rehavid_app.reservas.tests.factories import ServicioFactory
from rehavid_app.solicitudes.models import EstadoSolicitud
from rehavid_app.solicitudes.models import Solicitud
from rehavid_app.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HTTP_OK = 200
HTTP_REDIRECT = 302
HTTP_FORBIDDEN = 403


def hoy():
    return timezone.localdate()


@pytest.fixture
def solicitante():
    return UserFactory(username="solicitante-p", nivel=4, empresa=EmpresaFactory())


@pytest.fixture
def operador():
    return UserFactory(username="operador-p", nivel=2)


@pytest.fixture
def contexto(solicitante):
    servicio = ServicioFactory()
    return {
        "servicio": servicio,
        "equipo": EquipoFactory(servicio=servicio),
        "ciudad": CiudadFactory(),
        "acc": AccesorioTipo.objects.create(servicio=servicio, nombre="Camisetas", cantidad_default=4),
        "empresa": solicitante.empresa,
    }


def _payload(contexto, **extra):
    data = {
        "servicio": contexto["servicio"].pk,
        "ciudad": contexto["ciudad"].pk,
        "empresa_cliente": contexto["empresa"].pk,
        "personas": 5,
        "fecha_sugerida": hoy() + timedelta(days=10),
        "dias_estimados": 2,
        "notas": "Planta norte",
        "prof_cantidad": 1,
        "prof_perfil": "Fisioterapeuta",
        f"acc-{contexto['acc'].pk}": 4,
    }
    data.update(extra)
    return data


def test_e2e_solicitud_a_reserva(client, solicitante, operador, contexto):
    # 1 · el solicitante crea la solicitud (B4: fecha persistida, O16: accesorios)
    client.force_login(solicitante)
    response = client.post(reverse("portal:solicitar"), _payload(contexto))
    assert response.status_code == HTTP_REDIRECT
    solicitud = Solicitud.objects.latest("pk")
    assert solicitud.fecha_sugerida == hoy() + timedelta(days=10)
    assert solicitud.estado == EstadoSolicitud.PENDIENTE
    assert list(solicitud.accesorios_solicitados.values_list("nombre", "cantidad")) == [("Camisetas", 4)]
    assert solicitud.prof_perfil == "Fisioterapeuta"

    # 2 · el operador la ve en la bandeja y la atiende (B2)
    client.force_login(operador)
    response = client.get(reverse("solicitudes:bandeja"))
    assert solicitud.codigo in response.content.decode()
    response = client.post(reverse("solicitudes:atender", kwargs={"pk": solicitud.pk}))
    assert response.status_code == HTTP_REDIRECT
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.CONFIRMADA
    reserva = solicitud.reservas.get()
    assert not reserva.cancelada
    assert reserva.fecha_salida == solicitud.fecha_sugerida
    assert reserva.fecha_retorno_esp == solicitud.fecha_sugerida + timedelta(days=1)

    # 3 · el solicitante la ve confirmada con su reserva
    client.force_login(solicitante)
    html = client.get(reverse("portal:mis_solicitudes")).content.decode()
    assert solicitud.codigo in html
    assert reserva.codigo in html


def test_atender_sin_stock_deja_pendiente(client, solicitante, operador, contexto):
    client.force_login(solicitante)
    client.post(reverse("portal:solicitar"), _payload(contexto))
    client.post(reverse("portal:solicitar"), _payload(contexto))  # misma fecha, 1 equipo
    s1, s2 = Solicitud.objects.order_by("pk")[:2]

    client.force_login(operador)
    client.post(reverse("solicitudes:atender", kwargs={"pk": s1.pk}))
    client.post(reverse("solicitudes:atender", kwargs={"pk": s2.pk}))
    s1.refresh_from_db()
    s2.refresh_from_db()
    assert s1.estado == EstadoSolicitud.CONFIRMADA
    assert s2.estado == EstadoSolicitud.PENDIENTE  # transacción revertida
    assert not s2.reservas.exists()


def test_fecha_minima_hoy_mas_7(client, solicitante, contexto):
    client.force_login(solicitante)
    response = client.post(
        reverse("portal:solicitar"),
        _payload(contexto, fecha_sugerida=hoy() + timedelta(days=3)),
    )
    assert response.status_code == HTTP_OK  # re-render con error
    assert Solicitud.objects.count() == 0
    assert "al menos 7 días" in response.content.decode()


def test_editar_solo_pendiente(client, solicitante, operador, contexto):
    client.force_login(solicitante)
    client.post(reverse("portal:solicitar"), _payload(contexto))
    solicitud = Solicitud.objects.latest("pk")
    response = client.post(
        reverse("portal:editar", kwargs={"pk": solicitud.pk}),
        {"personas": 9, "notas": "ajuste"},
    )
    assert response.status_code == HTTP_REDIRECT
    solicitud.refresh_from_db()
    assert solicitud.personas == 9
    assert solicitud.editada


def test_cancelar_confirmada_respeta_48h(client, solicitante, operador, contexto):
    client.force_login(solicitante)
    client.post(reverse("portal:solicitar"), _payload(contexto, fecha_sugerida=hoy() + timedelta(days=8)))
    solicitud = Solicitud.objects.latest("pk")
    client.force_login(operador)
    client.post(reverse("solicitudes:atender", kwargs={"pk": solicitud.pk}))

    # A 8 días de la fecha, el solicitante todavía puede cancelar (>= 48h)
    client.force_login(solicitante)
    response = client.post(
        reverse("portal:cancelar", kwargs={"pk": solicitud.pk}),
        {"motivo": "cambio de agenda"},
    )
    assert response.status_code == HTTP_REDIRECT
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.CANCELADA
    reserva = solicitud.reservas.get()
    assert reserva.cancelada  # la reserva vinculada también se cancela


def test_no_puede_operar_solicitudes_ajenas(client, contexto, solicitante):
    otro = UserFactory(username="otro-solicitante", nivel=4, empresa=EmpresaFactory())
    client.force_login(solicitante)
    client.post(reverse("portal:solicitar"), _payload(contexto))
    solicitud = Solicitud.objects.latest("pk")

    client.force_login(otro)
    response = client.post(
        reverse("portal:cancelar", kwargs={"pk": solicitud.pk}),
        {"motivo": "x"},
    )
    assert response.status_code == HTTP_FORBIDDEN


def test_badge_api(client, solicitante, operador, contexto):
    client.force_login(solicitante)
    client.post(reverse("portal:solicitar"), _payload(contexto))

    client.force_login(operador)
    data = client.get("/api/solicitudes/badge/").json()
    assert data["pendientes"] == 1

    # nivel 4 no consulta la bandeja
    client.force_login(solicitante)
    assert client.get("/api/solicitudes/badge/").status_code == HTTP_FORBIDDEN


@pytest.mark.parametrize(
    ("url_name", "nivel", "esperado"),
    [
        ("portal:inicio", 4, HTTP_OK),
        ("portal:inicio", 2, HTTP_FORBIDDEN),
        ("portal:solicitar", 4, HTTP_OK),
        ("portal:solicitar", 3, HTTP_FORBIDDEN),
        ("portal:mis_solicitudes", 4, HTTP_OK),
        ("portal:equipos", 4, HTTP_OK),
        ("solicitudes:bandeja", 2, HTTP_OK),
        ("solicitudes:bandeja", 1, HTTP_OK),
        ("solicitudes:bandeja", 3, HTTP_FORBIDDEN),
        ("solicitudes:bandeja", 4, HTTP_FORBIDDEN),
    ],
)
def test_matriz_portal_bandeja(client, url_name, nivel, esperado):
    client.force_login(UserFactory(username=f"matriz-{url_name}-{nivel}".replace(":", "-"), nivel=nivel))
    assert client.get(reverse(url_name)).status_code == esperado
