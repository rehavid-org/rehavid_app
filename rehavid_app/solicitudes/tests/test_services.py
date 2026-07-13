"""Tests del flujo del portal solicitante: B2 (atender crea reserva),
B4 (fecha sugerida persistida) y B5 (regla 48h contra la fecha del servicio)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.reservas.models import Reserva
from rehavid_app.reservas.tests.factories import CiudadFactory
from rehavid_app.reservas.tests.factories import EmpresaFactory
from rehavid_app.reservas.tests.factories import EquipoFactory
from rehavid_app.reservas.tests.factories import ServicioFactory
from rehavid_app.solicitudes import services as svc
from rehavid_app.solicitudes.models import EstadoSolicitud
from rehavid_app.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

HOY = timezone.localdate


@pytest.fixture
def solicitante():
    return UserFactory(nivel=4)


@pytest.fixture
def operador():
    return UserFactory(nivel=2)


def _crear_solicitud(solicitante, servicio=None, dias_desde_hoy=10, dias_estimados=2, **kwargs):
    return svc.crear_solicitud(
        solicitante=solicitante,
        empresa_cliente=EmpresaFactory(),
        servicio=servicio or ServicioFactory(),
        ciudad=CiudadFactory(),
        personas=6,
        fecha_sugerida=HOY() + timedelta(days=dias_desde_hoy),
        dias_estimados=dias_estimados,
        profesional={"perfil": "Fisioterapeuta", "cantidad": 1},
        accesorios=[{"nombre": "Electrodos", "cantidad": 50}],
        **kwargs,
    )


# ────────────────────────────────────────────────────────────
# B4 · crear con fecha sugerida persistida
# ────────────────────────────────────────────────────────────
def test_crear_persiste_fecha_sugerida_y_accesorios(solicitante):
    solicitud = _crear_solicitud(solicitante, dias_desde_hoy=12)
    assert solicitud.fecha_sugerida == HOY() + timedelta(days=12)
    assert solicitud.codigo == f"SOL-{solicitud.pk:03d}"
    assert solicitud.accesorios_solicitados.get().nombre == "Electrodos"
    assert solicitud.prof_perfil == "Fisioterapeuta"
    assert solicitud.notificada_a == svc.NOTIFICAR_A


# ────────────────────────────────────────────────────────────
# B2 · atender crea la reserva vinculada
# ────────────────────────────────────────────────────────────
def test_atender_crea_reserva_vinculada(solicitante, operador):
    servicio = ServicioFactory()
    equipo = EquipoFactory(servicio=servicio)
    solicitud = _crear_solicitud(solicitante, servicio=servicio, dias_desde_hoy=10, dias_estimados=3)

    reserva = svc.atender_solicitud(solicitud, operador)

    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.CONFIRMADA
    assert solicitud.operador == operador
    assert solicitud.fecha_confirmada == HOY()
    assert reserva.solicitud == solicitud
    assert reserva.fecha_salida == solicitud.fecha_sugerida
    assert reserva.fecha_retorno_esp == solicitud.fecha_sugerida + timedelta(days=2)
    equipo.refresh_from_db()
    assert equipo.estado == EstadoEquipo.EN_USO


def test_atender_sin_stock_deja_pendiente(solicitante, operador):
    servicio = ServicioFactory()  # sin inventario
    solicitud = _crear_solicitud(solicitante, servicio=servicio)
    from rehavid_app.reservas.services import ReservaError  # noqa: PLC0415

    with pytest.raises(ReservaError):
        svc.atender_solicitud(solicitud, operador)
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.PENDIENTE
    assert Reserva.objects.count() == 0


def test_atender_no_pendiente_falla(solicitante, operador):
    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    solicitud = _crear_solicitud(solicitante, servicio=servicio)
    svc.atender_solicitud(solicitud, operador)
    with pytest.raises(svc.SolicitudError, match="Solo pendientes"):
        svc.atender_solicitud(solicitud, operador)


# ────────────────────────────────────────────────────────────
# B5 · regla 48h contra la fecha programada del servicio
# ────────────────────────────────────────────────────────────
def test_cancelar_confirmada_lejos_de_la_fecha_ok(solicitante, operador):
    """Servicio en 10 días → el solicitante puede cancelar aunque se haya
    confirmado ayer (el prototipo comparaba mal contra fecha_confirmada)."""
    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    solicitud = _crear_solicitud(solicitante, servicio=servicio, dias_desde_hoy=10)
    svc.atender_solicitud(solicitud, operador)
    solicitud.refresh_from_db()

    svc.cancelar_solicitud(solicitud, "cambio de planes", solicitante)
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.CANCELADA
    # la reserva vinculada también se canceló y el equipo quedó libre
    reserva = solicitud.reservas.get()
    assert reserva.cancelada


def test_cancelar_confirmada_a_menos_de_48h_bloqueada_para_nivel_4(solicitante, operador):
    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    solicitud = _crear_solicitud(solicitante, servicio=servicio, dias_desde_hoy=1)
    svc.atender_solicitud(solicitud, operador)
    solicitud.refresh_from_db()

    with pytest.raises(svc.SolicitudError, match="48 horas"):
        svc.cancelar_solicitud(solicitud, "ya no", solicitante)


def test_cancelar_a_menos_de_48h_permitida_para_operador(solicitante, operador):
    """La regla 48h solo aplica al nivel 4; el coordinador sí puede."""
    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    solicitud = _crear_solicitud(solicitante, servicio=servicio, dias_desde_hoy=1)
    svc.atender_solicitud(solicitud, operador)
    solicitud.refresh_from_db()

    svc.cancelar_solicitud(solicitud, "cliente canceló por teléfono", operador)
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.CANCELADA


def test_cancelar_pendiente_sin_regla_48h(solicitante):
    solicitud = _crear_solicitud(solicitante, dias_desde_hoy=1)
    svc.cancelar_solicitud(solicitud, "me equivoqué", solicitante)
    solicitud.refresh_from_db()
    assert solicitud.estado == EstadoSolicitud.CANCELADA


# ────────────────────────────────────────────────────────────
# O11 · edición y observaciones
# ────────────────────────────────────────────────────────────
def test_editar_solo_pendiente(solicitante, operador):
    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    solicitud = _crear_solicitud(solicitante, servicio=servicio)
    svc.editar_solicitud(solicitud, solicitante, personas=9)
    solicitud.refresh_from_db()
    assert solicitud.personas == 9
    assert solicitud.editada

    svc.atender_solicitud(solicitud, operador)
    solicitud.refresh_from_db()
    with pytest.raises(svc.SolicitudError, match="pendientes"):
        svc.editar_solicitud(solicitud, solicitante, personas=3)


def test_observacion(solicitante):
    solicitud = _crear_solicitud(solicitante)
    obs = svc.agregar_observacion(solicitud, "llevar extensión eléctrica", solicitante)
    assert obs.autor == solicitante
    assert solicitud.observaciones.count() == 1


# ────────────────────────────────────────────────────────────
# O17 · badge
# ────────────────────────────────────────────────────────────
def test_contar_pendientes(solicitante):
    _crear_solicitud(solicitante)
    _crear_solicitud(solicitante)
    assert svc.contar_pendientes() == 2
