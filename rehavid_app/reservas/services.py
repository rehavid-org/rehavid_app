"""Lógica de negocio de reservas (R002-R009) portada del backend FastAPI.

Correcciones aplicadas al portar:
- B6 · códigos derivados del PK (no COUNT(1))
- B8 · toda acción sobre equipos opera sobre el M2M completo del paquete
- Concurrencia · ``select_for_update`` sobre los equipos de la categoría
  serializa dos reservas simultáneas del mismo stock.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rehavid_app.auditoria import services as auditoria
from rehavid_app.catalogo.models import Servicio
from rehavid_app.equipos.models import Equipo
from rehavid_app.equipos.models import EstadoEquipo
from rehavid_app.paquetes.models import Paquete

from .models import ConfirmacionRetorno
from .models import HistorialReserva
from .models import Reserva

ESTADOS_BLOQUEADOS = (
    EstadoEquipo.EN_MANTENIMIENTO,
    EstadoEquipo.EN_TRANSITO,
    EstadoEquipo.DE_BAJA,
)


class ReservaError(Exception):
    """Error de negocio con mensaje apto para mostrar al usuario."""


@dataclass
class Disponibilidad:
    disponible: bool
    motivo: str
    equipos_libres: list[Equipo] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "disponible": self.disponible,
            "motivo": self.motivo,
            "equipos_libres": [e.codigo for e in self.equipos_libres],
        }


def riesgo_heuristico(personas: int) -> float:
    """Heurística vigente hasta que el modelo predictivo real esté activo."""
    return min(0.85, 0.18 + personas * 0.04)


# ────────────────────────────────────────────────────────────
# R003 + R008 · Disponibilidad
# ────────────────────────────────────────────────────────────
def _reserva_ocupa(reserva: Reserva, inicio: date, fin: date) -> bool:
    """Solapamiento de rango; +1 día si el retorno dejó preparación pendiente."""
    r_fin = reserva.fecha_retorno_esp
    conf = getattr(reserva, "confirmacion_retorno", None)
    if conf and conf.requiere_preparacion and not conf.preparacion_completa:
        r_fin = r_fin + timedelta(days=1)
    return inicio <= r_fin and fin >= reserva.fecha_salida


def verificar_disponibilidad(
    servicio: Servicio,
    fecha_salida: date,
    fecha_retorno: date,
    excluir_reservas: list[int] | None = None,
    para_actualizar: bool = False,
) -> Disponibilidad:
    """R003/R008 · equipos del servicio libres en el rango.

    ``para_actualizar=True`` bloquea las filas de equipos (usar dentro de
    una transacción al crear/reprogramar).
    """
    if not servicio.requiere_equipo_fisico:
        return Disponibilidad(True, f"{servicio.nombre} no requiere equipo físico")

    equipos_cat = Equipo.objects.filter(servicio=servicio)
    if para_actualizar:
        equipos_cat = equipos_cat.select_for_update()
    equipos_cat = list(equipos_cat)
    if not equipos_cat:
        return Disponibilidad(False, f'No hay equipos del tipo "{servicio.nombre}" en el inventario')

    equipos_op = [e for e in equipos_cat if e.estado not in ESTADOS_BLOQUEADOS]
    if not equipos_op:
        return Disponibilidad(
            False,
            f'Todos los equipos "{servicio.nombre}" están en mantenimiento, tránsito o de baja',
        )

    reservas_activas = (
        Reserva.objects.filter(cancelada=False, equipos__in=equipos_op)
        .exclude(pk__in=excluir_reservas or [])
        .distinct()
        .select_related("confirmacion_retorno")
        .prefetch_related("equipos")
    )
    ocupados: set[int] = set()
    for reserva in reservas_activas:
        if _reserva_ocupa(reserva, fecha_salida, fecha_retorno):
            ocupados.update(e.pk for e in reserva.equipos.all())

    libres = [e for e in equipos_op if e.pk not in ocupados]
    if not libres:
        return Disponibilidad(
            False,
            f'Stock agotado · todos los equipos "{servicio.nombre}" ({len(equipos_cat)} en total) '
            f"están reservados o en preparación en el rango {fecha_salida} → {fecha_retorno}",
        )
    return Disponibilidad(
        True,
        f"{len(libres)} de {len(equipos_cat)} equipos disponibles",
        equipos_libres=libres,
    )


def verificar_disponibilidad_paquete(
    paquete: Paquete,
    fecha_salida: date,
    fecha_retorno: date,
    excluir_reservas: list[int] | None = None,
    para_actualizar: bool = False,
) -> dict:
    """R006 · TODOS los servicios del paquete deben tener stock."""
    detalle = []
    for servicio in paquete.servicios_requeridos.all():
        disp = verificar_disponibilidad(
            servicio,
            fecha_salida,
            fecha_retorno,
            excluir_reservas=excluir_reservas,
            para_actualizar=para_actualizar,
        )
        detalle.append({"categoria": servicio.nombre, "_disp": disp, **disp.as_dict()})

    todos = all(d["disponible"] for d in detalle)
    falta = [d["categoria"] for d in detalle if not d["disponible"]]
    return {
        "disponible": todos,
        "motivo": "Todos los equipos disponibles" if todos else f"Falta stock para: {', '.join(falta)}",
        "detalle": detalle,
    }


def proxima_fecha_disponible(servicio: Servicio, duracion_dias: int = 1, horizonte_dias: int = 120) -> date | None:
    """O09 · primera fecha en la que el servicio tiene stock por ``duracion_dias``."""
    hoy = timezone.localdate()
    for delta in range(horizonte_dias):
        inicio = hoy + timedelta(days=delta)
        fin = inicio + timedelta(days=max(duracion_dias - 1, 0))
        if verificar_disponibilidad(servicio, inicio, fin).disponible:
            return inicio
    return None


# ────────────────────────────────────────────────────────────
# R003 + R008 · Crear
# ────────────────────────────────────────────────────────────
@transaction.atomic
def crear_reserva(
    *,
    servicio: Servicio,
    cliente,
    ciudad,
    personas: int,
    fecha_salida: date,
    fecha_retorno_esp: date,
    usuario,
    paquete: Paquete | None = None,
    solicitud=None,
) -> Reserva:
    """Valida stock (con lock) y crea la reserva. R008: bloquea si no hay.

    O08: un paquete asigna UN equipo libre por cada categoría requerida.
    """
    if fecha_retorno_esp < fecha_salida:
        msg = "La fecha de retorno no puede ser anterior a la salida"
        raise ReservaError(msg)

    equipos_asignados: list[Equipo] = []
    if paquete is not None:
        v = verificar_disponibilidad_paquete(
            paquete, fecha_salida, fecha_retorno_esp, para_actualizar=True,
        )
        if not v["disponible"]:
            raise ReservaError(v["motivo"])
        equipos_asignados = [
            d["_disp"].equipos_libres[0] for d in v["detalle"] if d["_disp"].equipos_libres
        ]
    else:
        disp = verificar_disponibilidad(
            servicio, fecha_salida, fecha_retorno_esp, para_actualizar=True,
        )
        if not disp.disponible:
            raise ReservaError(disp.motivo)
        if disp.equipos_libres:
            equipos_asignados = [disp.equipos_libres[0]]

    reserva = Reserva.objects.create(
        servicio=servicio,
        cliente=cliente,
        ciudad=ciudad,
        personas=personas,
        contactos_efectivos=personas,
        fecha_salida=fecha_salida,
        fecha_retorno_esp=fecha_retorno_esp,
        paquete=paquete,
        solicitud=solicitud,
        riesgo=riesgo_heuristico(personas),
    )
    reserva.equipos.set(equipos_asignados)

    detalle = f"Reserva creada · {servicio.nombre} · {cliente}"
    if paquete:
        detalle += f" · paquete {paquete.codigo} ({len(equipos_asignados)} equipos)"
    HistorialReserva.objects.create(reserva=reserva, accion="creada", usuario=usuario, detalle=detalle)

    # O08 · todos los equipos asignados pasan a en_uso
    Equipo.objects.filter(pk__in=[e.pk for e in equipos_asignados]).update(estado=EstadoEquipo.EN_USO)

    auditoria.registrar(usuario, "crear_reserva", "reservas", f"{reserva.codigo} · {detalle}")
    return reserva


# ────────────────────────────────────────────────────────────
# R002 · Cancelar
# ────────────────────────────────────────────────────────────
def _liberar_equipos(reserva: Reserva) -> None:
    """Libera los equipos de la reserva que ninguna otra reserva activa use."""
    for equipo in reserva.equipos.all():
        otras = (
            Reserva.objects.filter(equipos=equipo, cancelada=False)
            .exclude(pk=reserva.pk)
            .filter(Q(confirmacion_retorno__isnull=True))
            .exists()
        )
        if not otras and equipo.estado == EstadoEquipo.EN_USO:
            equipo.estado = EstadoEquipo.DISPONIBLE
            equipo.save(update_fields=["estado"])


@transaction.atomic
def cancelar_reserva(reserva: Reserva, motivo: str, usuario) -> Reserva:
    if reserva.cancelada:
        msg = "La reserva ya estaba cancelada"
        raise ReservaError(msg)

    reserva.cancelada = True
    reserva.motivo_cancelacion = motivo or "Cancelada por el operador"
    reserva.save(update_fields=["cancelada", "motivo_cancelacion"])
    HistorialReserva.objects.create(reserva=reserva, accion="cancelada", usuario=usuario, detalle=motivo)
    # O08 · liberar TODOS los equipos del paquete
    _liberar_equipos(reserva)
    auditoria.registrar(usuario, "cancelar_reserva", "reservas", f"{reserva.codigo} · {motivo}")
    return reserva


# ────────────────────────────────────────────────────────────
# R002 · Reprogramar
# ────────────────────────────────────────────────────────────
@transaction.atomic
def reprogramar_reserva(
    reserva: Reserva,
    nueva_fecha_salida: date,
    nueva_fecha_retorno: date,
    motivo: str,
    usuario,
) -> Reserva:
    if reserva.cancelada:
        msg = "No se puede reprogramar una reserva cancelada"
        raise ReservaError(msg)
    if nueva_fecha_retorno < nueva_fecha_salida:
        msg = "La fecha de retorno no puede ser anterior a la salida"
        raise ReservaError(msg)

    # Verificar disponibilidad excluyendo esta misma reserva
    if reserva.paquete_id:
        v = verificar_disponibilidad_paquete(
            reserva.paquete, nueva_fecha_salida, nueva_fecha_retorno,
            excluir_reservas=[reserva.pk], para_actualizar=True,
        )
        if not v["disponible"]:
            msg = f"No se puede reprogramar: {v['motivo']}"
            raise ReservaError(msg)
    else:
        disp = verificar_disponibilidad(
            reserva.servicio, nueva_fecha_salida, nueva_fecha_retorno,
            excluir_reservas=[reserva.pk], para_actualizar=True,
        )
        if not disp.disponible:
            msg = f"No se puede reprogramar: {disp.motivo}"
            raise ReservaError(msg)

    fecha_original = reserva.fecha_salida
    reserva.reprogramada_desde = fecha_original
    reserva.fecha_salida = nueva_fecha_salida
    reserva.fecha_retorno_esp = nueva_fecha_retorno
    reserva.save(update_fields=["reprogramada_desde", "fecha_salida", "fecha_retorno_esp"])
    HistorialReserva.objects.create(
        reserva=reserva,
        accion="reprogramada",
        usuario=usuario,
        detalle=f"De {fecha_original} a {nueva_fecha_salida} · {motivo}",
    )
    auditoria.registrar(usuario, "reprogramar_reserva", "reservas", f"{reserva.codigo} · {motivo}")
    return reserva


# ────────────────────────────────────────────────────────────
# R007 + R009 · Retorno
# ────────────────────────────────────────────────────────────
@transaction.atomic
def confirmar_retorno(
    reserva: Reserva,
    estado_kit: str,
    notas: str,
    requiere_preparacion: bool,  # noqa: FBT001
    usuario,
) -> Reserva:
    if reserva.cancelada:
        msg = "Reserva cancelada"
        raise ReservaError(msg)
    if hasattr(reserva, "confirmacion_retorno"):
        msg = "Esta reserva ya tiene retorno confirmado"
        raise ReservaError(msg)

    ConfirmacionRetorno.objects.create(
        reserva=reserva,
        fecha=timezone.localdate(),
        estado_kit=estado_kit,
        notas=notas,
        operador=usuario,
        requiere_preparacion=requiere_preparacion,
        preparacion_completa=not requiere_preparacion,
    )
    HistorialReserva.objects.create(
        reserva=reserva,
        accion="retorno_confirmado",
        usuario=usuario,
        detalle=f"Retorno · {estado_kit} · {'Pasa a preparación' if requiere_preparacion else 'Listo'}",
    )
    # O08/R009 · todos los equipos del paquete cambian de estado y suman uso
    nuevo_estado = EstadoEquipo.EN_PREPARACION if requiere_preparacion else EstadoEquipo.DISPONIBLE
    for equipo in reserva.equipos.all():
        equipo.estado = nuevo_estado
        equipo.historial_uso += 1
        equipo.save(update_fields=["estado", "historial_uso"])

    auditoria.registrar(usuario, "confirmar_retorno", "reservas", f"{reserva.codigo} · {estado_kit}")
    return reserva


# ────────────────────────────────────────────────────────────
# R009 · Equipo listo tras preparación
# ────────────────────────────────────────────────────────────
@transaction.atomic
def marcar_equipo_listo(equipo: Equipo, notas: str, usuario) -> Equipo:
    if equipo.estado != EstadoEquipo.EN_PREPARACION:
        msg = f"Equipo no está en preparación (estado actual: {equipo.get_estado_display()})"
        raise ReservaError(msg)
    equipo.estado = EstadoEquipo.DISPONIBLE
    equipo.ultima_revision = timezone.localdate()
    equipo.save(update_fields=["estado", "ultima_revision"])
    # Completar la preparación pendiente más reciente de este equipo
    conf = (
        ConfirmacionRetorno.objects.filter(
            reserva__equipos=equipo, requiere_preparacion=True, preparacion_completa=False,
        )
        .order_by("-fecha")
        .first()
    )
    if conf:
        conf.preparacion_completa = True
        conf.preparacion_notas = notas
        conf.save(update_fields=["preparacion_completa", "preparacion_notas"])
    auditoria.registrar(usuario, "equipo_listo", "equipos", f"{equipo.codigo} · {notas}")
    return equipo


@transaction.atomic
def enviar_a_mantenimiento(equipo: Equipo, motivo: str, usuario) -> Equipo:
    equipo.estado = EstadoEquipo.EN_MANTENIMIENTO
    equipo.motivo_mantenimiento = motivo
    equipo.save(update_fields=["estado", "motivo_mantenimiento"])
    auditoria.registrar(usuario, "equipo_mantenimiento", "equipos", f"{equipo.codigo} · {motivo}")
    return equipo


# ────────────────────────────────────────────────────────────
# O18 · Baja definitiva
# ────────────────────────────────────────────────────────────
@transaction.atomic
def dar_de_baja_equipo(equipo: Equipo, motivo: str, usuario) -> Equipo:
    """Retiro definitivo. Bloqueado si el equipo tiene reservas activas."""
    activas = Reserva.objects.filter(
        equipos=equipo, cancelada=False, confirmacion_retorno__isnull=True,
    ).count()
    if activas:
        msg = f"No se puede dar de baja · tiene {activas} reserva(s) activa(s)"
        raise ReservaError(msg)
    equipo.estado = EstadoEquipo.DE_BAJA
    equipo.motivo_baja = motivo
    equipo.fecha_baja = timezone.localdate()
    equipo.save(update_fields=["estado", "motivo_baja", "fecha_baja"])
    auditoria.registrar(usuario, "equipo_baja", "equipos", f"{equipo.codigo} · {motivo}")
    return equipo
