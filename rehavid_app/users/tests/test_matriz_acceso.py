"""Matriz de acceso vista por nivel (Fase 4) — la autorización vive en el
servidor, no en botones ocultos (B1).

Para cada URL se declara el nivel máximo permitido; los niveles superiores
(número mayor) deben recibir 403 y los anónimos redirección al login.
"""

import pytest
from django.urls import reverse

from rehavid_app.reservas.tests.factories import EquipoFactory
from rehavid_app.reservas.tests.factories import PaqueteFactory
from rehavid_app.reservas.tests.factories import ServicioFactory
from rehavid_app.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HTTP_OK = 200
HTTP_FORBIDDEN = 403
HTTP_REDIRECT = 302

# (url_name, kwargs?, nivel máximo que puede entrar)
VISTAS = [
    ("reservas:lista", 2),
    ("reservas:nueva", 2),
    ("equipos:lista", 3),
    ("equipos:alta", 2),
    ("paquetes:lista", 3),
    ("paquetes:nuevo", 2),
]


@pytest.fixture
def usuarios():
    return {
        nivel: UserFactory(username=f"nivel{nivel}", nivel=nivel, password="x")
        for nivel in (1, 2, 3, 4)
    }


@pytest.mark.parametrize(("url_name", "nivel_maximo"), VISTAS)
@pytest.mark.parametrize("nivel", [1, 2, 3, 4])
def test_matriz_vistas(client, usuarios, url_name, nivel_maximo, nivel):
    client.force_login(usuarios[nivel])
    response = client.get(reverse(url_name))
    esperado = HTTP_OK if nivel <= nivel_maximo else HTTP_FORBIDDEN
    assert response.status_code == esperado, f"{url_name} nivel {nivel}"


@pytest.mark.parametrize(("url_name", "nivel_maximo"), VISTAS)
def test_anonimo_redirige_a_login(client, url_name, nivel_maximo):
    response = client.get(reverse(url_name))
    assert response.status_code == HTTP_REDIRECT
    assert "login" in response.url


@pytest.mark.parametrize("nivel", [1, 2, 3, 4])
def test_calendario_todos_los_niveles(client, usuarios, nivel):
    client.force_login(usuarios[nivel])
    assert client.get(reverse("analitica:calendario")).status_code == HTTP_OK


@pytest.mark.parametrize(("nivel", "esperado"), [(2, HTTP_OK), (3, HTTP_FORBIDDEN)])
def test_brief_solo_direccion(client, usuarios, nivel, esperado):
    """El placeholder de brief respeta los módulos del nivel."""
    client.force_login(usuarios[nivel])
    assert client.get(reverse("analitica:brief")).status_code == esperado


def test_baja_equipo_es_solo_nivel_1(client, usuarios):
    equipo = EquipoFactory()
    url = reverse("equipos:baja", kwargs={"pk": equipo.pk})
    client.force_login(usuarios[2])
    assert client.post(url, {"motivo": "x"}).status_code == HTTP_FORBIDDEN
    client.force_login(usuarios[1])
    response = client.post(url, {"motivo": "obsoleto"})
    assert response.status_code == HTTP_REDIRECT
    equipo.refresh_from_db()
    assert equipo.estado == "de_baja"


# ── API DRF ─────────────────────────────────────────────────
@pytest.mark.parametrize(
    ("nivel", "esperado"),
    [(1, HTTP_OK), (2, HTTP_OK), (3, HTTP_FORBIDDEN), (4, HTTP_FORBIDDEN)],
)
def test_api_reservas_lista(client, usuarios, nivel, esperado):
    client.force_login(usuarios[nivel])
    assert client.get("/api/reservas/").status_code == esperado


def test_api_disponibilidad_abierta_a_solicitantes(client, usuarios):
    """O10 · el portal usa la disponibilidad para el preview de saturación."""
    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    client.force_login(usuarios[4])
    response = client.get(
        "/api/reservas/disponibilidad/",
        {"servicio": servicio.pk, "fecha_salida": "2026-09-01", "fecha_retorno": "2026-09-03"},
    )
    assert response.status_code == HTTP_OK
    assert response.json()["disponible"] is True


def test_api_paquete_crud_gateado(client, usuarios):
    servicio = ServicioFactory()
    payload = {
        "codigo": "PKG-90",
        "nombre": "Paquete API",
        "descripcion": "",
        "servicios_requeridos": [servicio.pk],
        "duracion_dias": 2,
        "activo": True,
    }
    client.force_login(usuarios[3])
    assert client.post("/api/paquetes/", payload).status_code == HTTP_FORBIDDEN
    client.force_login(usuarios[2])
    assert client.post("/api/paquetes/", payload).status_code == 201


def test_api_ficha_equipo(client, usuarios):
    equipo = EquipoFactory()
    client.force_login(usuarios[3])
    data = client.get(f"/api/equipos/{equipo.pk}/ficha/").json()
    assert data["codigo"] == equipo.codigo
    assert data["reservas_activas"] == 0


def test_api_disponibilidad_paquete_detalle(client, usuarios):
    s1, s2 = ServicioFactory(), ServicioFactory()
    EquipoFactory(servicio=s1)  # s2 sin inventario
    paquete = PaqueteFactory(servicios=[s1, s2])
    client.force_login(usuarios[2])
    data = client.get(f"/api/paquetes/{paquete.pk}/disponibilidad/").json()
    assert data["disponible"] is False
    estados = {d["categoria"]: d["disponible"] for d in data["detalle"]}
    assert estados[s1.nombre] is True
    assert estados[s2.nombre] is False
