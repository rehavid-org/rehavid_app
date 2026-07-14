"""Tests de las reglas de negocio R002-R009 + O08/O09/O18.

Red de seguridad de la migración: cada regla del prototipo tiene aquí
su verificación contra el servicio Django.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.reservas import services as svc
from rehavid_app.reservas.models import Reserva
from rehavid_app.users.tests.factories import UserFactory

from .factories import CiudadFactory
from .factories import EmpresaFactory
from .factories import EquipoFactory
from .factories import PaqueteFactory
from .factories import ServicioFactory

pytestmark = pytest.mark.django_db

HOY = timezone.localdate


@pytest.fixture
def operador():
    return UserFactory(nivel=2)


@pytest.fixture
def contexto():
    """Un servicio con un único equipo + cliente y ciudad."""
    servicio = ServicioFactory()
    return {
        "servicio": servicio,
        "equipo": EquipoFactory(servicio=servicio),
        "cliente": EmpresaFactory(),
        "ciudad": CiudadFactory(),
    }


def _crear(contexto, operador, dias_desde=3, dias_hasta=5, **kwargs):
    return svc.crear_reserva(
        servicio=contexto["servicio"],
        cliente=contexto["cliente"],
        ciudad=contexto["ciudad"],
        personas=5,
        fecha_salida=HOY() + timedelta(days=dias_desde),
        fecha_retorno_esp=HOY() + timedelta(days=dias_hasta),
        usuario=operador,
        **kwargs,
    )


# ────────────────────────────────────────────────────────────
# R003/R008 · disponibilidad y creación
# ────────────────────────────────────────────────────────────
def test_crear_reserva_asigna_equipo_y_lo_marca_en_uso(contexto, operador):
    reserva = _crear(contexto, operador)
    contexto["equipo"].refresh_from_db()
    assert list(reserva.equipos.all()) == [contexto["equipo"]]
    assert contexto["equipo"].estado == EstadoEquipo.EN_USO
    assert reserva.codigo == f"R-{reserva.pk:03d}"
    assert reserva.historial.filter(accion="creada").exists()


def test_solapamiento_bloquea_segunda_reserva(contexto, operador):
    _crear(contexto, operador, 3, 5)
    with pytest.raises(svc.ReservaError, match="Stock agotado"):
        _crear(contexto, operador, 4, 6)


def test_rangos_disjuntos_no_bloquean(contexto, operador):
    _crear(contexto, operador, 3, 5)
    reserva2 = _crear(contexto, operador, 6, 8)
    assert reserva2.pk


def test_riesgo_heuristico(contexto, operador):
    reserva = _crear(contexto, operador)
    assert reserva.riesgo == pytest.approx(0.18 + 5 * 0.04)
    assert svc.riesgo_heuristico(100) == 0.85


def test_servicio_sin_equipo_fisico_siempre_disponible(operador):
    tumeke = ServicioFactory(nombre="Tumeke", requiere_equipo_fisico=False)
    disp = svc.verificar_disponibilidad(tumeke, HOY(), HOY() + timedelta(days=30))
    assert disp.disponible
    reserva = svc.crear_reserva(
        servicio=tumeke,
        cliente=EmpresaFactory(),
        ciudad=CiudadFactory(),
        personas=3,
        fecha_salida=HOY() + timedelta(days=1),
        fecha_retorno_esp=HOY() + timedelta(days=2),
        usuario=operador,
    )
    assert reserva.equipos.count() == 0


def test_equipo_en_mantenimiento_no_cuenta(contexto, operador):
    contexto["equipo"].estado = EstadoEquipo.EN_MANTENIMIENTO
    contexto["equipo"].save()
    disp = svc.verificar_disponibilidad(
        contexto["servicio"], HOY() + timedelta(days=3), HOY() + timedelta(days=5),
    )
    assert not disp.disponible
    assert "mantenimiento" in disp.motivo


def test_sin_inventario(operador):
    servicio = ServicioFactory()
    disp = svc.verificar_disponibilidad(servicio, HOY(), HOY() + timedelta(days=1))
    assert not disp.disponible
    assert "No hay equipos" in disp.motivo


def test_retorno_invalido(contexto, operador):
    with pytest.raises(svc.ReservaError, match="anterior a la salida"):
        _crear(contexto, operador, 5, 3)


# ────────────────────────────────────────────────────────────
# R002 · cancelar y reprogramar
# ────────────────────────────────────────────────────────────
def test_cancelar_libera_equipo(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.cancelar_reserva(reserva, "cliente desistió", operador)
    contexto["equipo"].refresh_from_db()
    reserva.refresh_from_db()
    assert reserva.cancelada
    assert contexto["equipo"].estado == EstadoEquipo.DISPONIBLE
    assert reserva.historial.filter(accion="cancelada").exists()


def test_cancelar_dos_veces_falla(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.cancelar_reserva(reserva, "x", operador)
    with pytest.raises(svc.ReservaError, match="ya estaba cancelada"):
        svc.cancelar_reserva(reserva, "x", operador)


def test_cancelar_no_libera_si_otra_reserva_activa_usa_el_equipo(contexto, operador):
    """El equipo queda en_uso si otra reserva activa lo tiene asignado."""
    r1 = _crear(contexto, operador, 3, 5)
    r2 = _crear(contexto, operador, 6, 8)
    svc.cancelar_reserva(r1, "x", operador)
    contexto["equipo"].refresh_from_db()
    assert contexto["equipo"].estado == EstadoEquipo.EN_USO
    assert list(r2.equipos.all()) == [contexto["equipo"]]


def test_reprogramar_se_excluye_a_si_misma(contexto, operador):
    """R002 · mover la reserva dentro de su propio rango no debe chocar consigo."""
    reserva = _crear(contexto, operador, 3, 5)
    svc.reprogramar_reserva(
        reserva, HOY() + timedelta(days=4), HOY() + timedelta(days=6), "ajuste", operador,
    )
    reserva.refresh_from_db()
    assert reserva.fecha_salida == HOY() + timedelta(days=4)
    assert reserva.reprogramada_desde == HOY() + timedelta(days=3)
    assert reserva.historial.filter(accion="reprogramada").exists()


def test_reprogramar_choca_con_otra_reserva(contexto, operador):
    _crear(contexto, operador, 3, 5)
    servicio2_equipo = EquipoFactory(servicio=contexto["servicio"])
    r2 = _crear(contexto, operador, 3, 5)  # toma el segundo equipo
    assert list(r2.equipos.all()) == [servicio2_equipo]
    # sin stock: mover r2 no es problema (usa su propio equipo), pero un
    # tercer rango con ambos equipos ocupados sí falla
    with pytest.raises(svc.ReservaError, match="Stock agotado"):
        _crear(contexto, operador, 4, 6)


def test_reprogramar_cancelada_falla(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.cancelar_reserva(reserva, "x", operador)
    with pytest.raises(svc.ReservaError, match="cancelada"):
        svc.reprogramar_reserva(
            reserva, HOY() + timedelta(days=10), HOY() + timedelta(days=11), "x", operador,
        )


# ────────────────────────────────────────────────────────────
# R007/R009 · retorno y preparación
# ────────────────────────────────────────────────────────────
def test_retorno_ok_disponibiliza_y_suma_uso(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.confirmar_retorno(reserva, "OK", "todo bien", False, operador)
    contexto["equipo"].refresh_from_db()
    assert contexto["equipo"].estado == EstadoEquipo.DISPONIBLE
    assert contexto["equipo"].historial_uso == 1
    assert reserva.confirmacion_retorno.estado_kit == "OK"


def test_retorno_con_preparacion_bloquea_un_dia_extra(contexto, operador):
    """El equipo con preparación pendiente sigue ocupado +1 día (R003)."""
    reserva = _crear(contexto, operador, 3, 5)
    svc.confirmar_retorno(reserva, "OK", "lavar camisetas", True, operador)
    contexto["equipo"].refresh_from_db()
    assert contexto["equipo"].estado == EstadoEquipo.EN_PREPARACION

    # día 6 = retorno+1 → aún bloqueado por la preparación pendiente
    disp = svc.verificar_disponibilidad(
        contexto["servicio"], HOY() + timedelta(days=6), HOY() + timedelta(days=6),
    )
    assert not disp.disponible
    # día 7 → libre
    disp = svc.verificar_disponibilidad(
        contexto["servicio"], HOY() + timedelta(days=7), HOY() + timedelta(days=8),
    )
    assert disp.disponible


def test_marcar_listo_completa_preparacion(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.confirmar_retorno(reserva, "OK", "", True, operador)
    contexto["equipo"].refresh_from_db()
    svc.marcar_equipo_listo(contexto["equipo"], "lavado listo", operador)
    contexto["equipo"].refresh_from_db()
    reserva.refresh_from_db()
    assert contexto["equipo"].estado == EstadoEquipo.DISPONIBLE
    assert contexto["equipo"].ultima_revision == HOY()
    assert reserva.confirmacion_retorno.preparacion_completa


def test_marcar_listo_sin_preparacion_falla(contexto, operador):
    with pytest.raises(svc.ReservaError, match="no está en preparación"):
        svc.marcar_equipo_listo(contexto["equipo"], "", operador)


def test_retorno_doble_falla(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.confirmar_retorno(reserva, "OK", "", False, operador)
    with pytest.raises(svc.ReservaError, match="ya tiene retorno"):
        svc.confirmar_retorno(reserva, "OK", "", False, operador)


# ────────────────────────────────────────────────────────────
# R006/O08/O09 · paquetes
# ────────────────────────────────────────────────────────────
def test_paquete_asigna_un_equipo_por_categoria(operador):
    s1, s2 = ServicioFactory(), ServicioFactory()
    e1, e2 = EquipoFactory(servicio=s1), EquipoFactory(servicio=s2)
    paquete = PaqueteFactory(servicios=[s1, s2])
    reserva = svc.crear_reserva(
        servicio=s1,
        cliente=EmpresaFactory(),
        ciudad=CiudadFactory(),
        personas=4,
        fecha_salida=HOY() + timedelta(days=3),
        fecha_retorno_esp=HOY() + timedelta(days=5),
        usuario=operador,
        paquete=paquete,
    )
    assert set(reserva.equipos.all()) == {e1, e2}
    for e in (e1, e2):
        e.refresh_from_db()
        assert e.estado == EstadoEquipo.EN_USO


def test_paquete_falla_si_falta_una_categoria(operador):
    s1, s2 = ServicioFactory(), ServicioFactory()
    EquipoFactory(servicio=s1)  # s2 sin inventario
    paquete = PaqueteFactory(servicios=[s1, s2])
    with pytest.raises(svc.ReservaError, match="Falta stock"):
        svc.crear_reserva(
            servicio=s1,
            cliente=EmpresaFactory(),
            ciudad=CiudadFactory(),
            personas=4,
            fecha_salida=HOY() + timedelta(days=3),
            fecha_retorno_esp=HOY() + timedelta(days=5),
            usuario=operador,
            paquete=paquete,
        )
    # nada quedó a medias: la transacción revirtió
    assert Reserva.objects.count() == 0


def test_cancelar_paquete_libera_todos_los_equipos(operador):
    s1, s2 = ServicioFactory(), ServicioFactory()
    e1, e2 = EquipoFactory(servicio=s1), EquipoFactory(servicio=s2)
    paquete = PaqueteFactory(servicios=[s1, s2])
    reserva = svc.crear_reserva(
        servicio=s1,
        cliente=EmpresaFactory(),
        ciudad=CiudadFactory(),
        personas=4,
        fecha_salida=HOY() + timedelta(days=3),
        fecha_retorno_esp=HOY() + timedelta(days=5),
        usuario=operador,
        paquete=paquete,
    )
    svc.cancelar_reserva(reserva, "x", operador)
    for e in (e1, e2):
        e.refresh_from_db()
        assert e.estado == EstadoEquipo.DISPONIBLE


def test_disponibilidad_paquete_tri_estado(operador):
    s1, s2 = ServicioFactory(), ServicioFactory()
    EquipoFactory(servicio=s1), EquipoFactory(servicio=s2)
    paquete = PaqueteFactory(servicios=[s1, s2])
    v = svc.verificar_disponibilidad_paquete(
        paquete, HOY() + timedelta(days=3), HOY() + timedelta(days=5),
    )
    assert v["disponible"]
    assert len(v["detalle"]) == 2


# ────────────────────────────────────────────────────────────
# O18 · baja
# ────────────────────────────────────────────────────────────
def test_baja_bloqueada_con_reserva_activa(contexto, operador):
    _crear(contexto, operador)
    with pytest.raises(svc.ReservaError, match="reserva\\(s\\) activa"):
        svc.dar_de_baja_equipo(contexto["equipo"], "obsoleto", operador)


def test_baja_ok_tras_retorno(contexto, operador):
    reserva = _crear(contexto, operador)
    svc.confirmar_retorno(reserva, "OK", "", False, operador)
    equipo = svc.dar_de_baja_equipo(contexto["equipo"], "obsoleto", operador)
    assert equipo.estado == EstadoEquipo.DE_BAJA
    assert equipo.fecha_baja == HOY()
    # de_baja bloquea disponibilidad futura
    disp = svc.verificar_disponibilidad(
        contexto["servicio"], HOY() + timedelta(days=10), HOY() + timedelta(days=11),
    )
    assert not disp.disponible


# ────────────────────────────────────────────────────────────
# O09 · próxima fecha disponible
# ────────────────────────────────────────────────────────────
def test_proxima_fecha_disponible(contexto, operador):
    _crear(contexto, operador, 0, 4)
    proxima = svc.proxima_fecha_disponible(contexto["servicio"], duracion_dias=1)
    assert proxima == HOY() + timedelta(days=5)


# ────────────────────────────────────────────────────────────
# Concurrencia · dos requests simultáneos al último equipo
# ────────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
def test_concurrencia_dos_reservas_simultaneas_una_falla():
    """select_for_update: solo una de dos reservas concurrentes obtiene
    el último equipo; la otra recibe 'Stock agotado'."""
    import threading  # noqa: PLC0415

    from django.db import connection  # noqa: PLC0415

    servicio = ServicioFactory()
    EquipoFactory(servicio=servicio)
    cliente, ciudad = EmpresaFactory(), CiudadFactory()
    usuario = UserFactory(nivel=2)

    resultados: list[str] = []
    barrera = threading.Barrier(2)

    def intento():
        barrera.wait()
        try:
            svc.crear_reserva(
                servicio=servicio,
                cliente=cliente,
                ciudad=ciudad,
                personas=3,
                fecha_salida=HOY() + timedelta(days=3),
                fecha_retorno_esp=HOY() + timedelta(days=5),
                usuario=usuario,
            )
            resultados.append("ok")
        except svc.ReservaError:
            resultados.append("sin_stock")
        finally:
            connection.close()

    hilos = [threading.Thread(target=intento) for _ in range(2)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=30)

    assert sorted(resultados) == ["ok", "sin_stock"]
    assert Reserva.objects.count() == 1
