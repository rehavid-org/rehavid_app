"""Seed idempotente con los datos reales extraídos del prototipo v13.

Carga catálogos, 14 usuarios, 10 equipos, 5 paquetes, 57 reservas,
7 solicitudes, 9 planes y la configuración de canales de alertas.

    python manage.py seed_demo
"""

import json
from datetime import date
from datetime import timedelta
from pathlib import Path

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from rehavid_app.alertas.models import ConfiguracionCanal
from rehavid_app.catalogo.models import AccesorioTipo
from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio
from rehavid_app.equipos.models import Accesorio
from rehavid_app.equipos.models import Equipo
from rehavid_app.paquetes.models import Paquete
from rehavid_app.planes.models import Plan
from rehavid_app.reservas.models import ConfirmacionRetorno
from rehavid_app.reservas.models import HistorialReserva
from rehavid_app.reservas.models import Reserva
from rehavid_app.solicitudes.models import Solicitud

User = get_user_model()

SEED_DIR = Path(settings.BASE_DIR) / "seed_data"

# Único servicio sin unidad física en inventario
SERVICIO_SIN_EQUIPO = "Tumeke"

# Clave del destino en canales.json según el canal
DESTINO_KEY = {"whatsapp": "numero", "email": "direccion", "teams": "canal"}


def _load(nombre: str):
    with (SEED_DIR / f"{nombre}.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def _parse_date(valor):
    if not valor:
        return None
    return date.fromisoformat(str(valor)[:10])


class Command(BaseCommand):
    help = "Carga los datos demo/reales del prototipo v13 (idempotente)."

    @transaction.atomic
    def handle(self, *args, **options):
        reservas = _load("reservas")
        solicitudes = _load("solicitudes")
        users = _load("users")
        equipos = _load("equipos")
        paquetes = _load("paquetes")
        planes = _load("planes")
        accesorios_srv = _load("accesorios_por_servicio")
        canales = _load("canales")

        self._seed_catalogos(reservas, solicitudes, users, equipos, accesorios_srv)
        usuarios_por_nombre = self._seed_users(users)
        self._seed_equipos(equipos)
        self._seed_paquetes(paquetes)
        self._seed_reservas(reservas, usuarios_por_nombre)
        self._seed_solicitudes(solicitudes, usuarios_por_nombre)
        self._seed_planes(planes)
        self._seed_canales(canales)

        self.stdout.write(self.style.SUCCESS(
            f"Seed completo · {Servicio.objects.count()} servicios · "
            f"{User.objects.count()} usuarios · {Equipo.objects.count()} equipos · "
            f"{Paquete.objects.count()} paquetes · {Reserva.objects.count()} reservas · "
            f"{Solicitud.objects.count()} solicitudes · {Plan.objects.count()} planes",
        ))

    # ────────────────────────────────────────────────────────
    def _seed_catalogos(self, reservas, solicitudes, users, equipos, accesorios_srv):
        servicios = set(accesorios_srv) | {r["servicio"] for r in reservas}
        servicios |= {e["categoria"] for e in equipos} | {s["servicio"] for s in solicitudes}
        for nombre in sorted(servicios):
            Servicio.objects.update_or_create(
                nombre=nombre,
                defaults={"requiere_equipo_fisico": nombre != SERVICIO_SIN_EQUIPO},
            )

        ciudades = {r["ciudad"] for r in reservas} | {s["ciudad"] for s in solicitudes}
        ciudades |= {e["ciudad_base"] for e in equipos}
        for nombre in sorted(ciudades):
            Ciudad.objects.get_or_create(nombre=nombre)

        empresas = {r["cliente"] for r in reservas} | {s["empresa_cliente"] for s in solicitudes}
        empresas |= {u["empresa"] for u in users if u.get("empresa")}
        for nombre in sorted(empresas):
            Empresa.objects.get_or_create(nombre=nombre)

        for servicio_nombre, items in accesorios_srv.items():
            servicio = Servicio.objects.get(nombre=servicio_nombre)
            for item in items:
                AccesorioTipo.objects.update_or_create(
                    servicio=servicio,
                    nombre=item["nombre"],
                    defaults={"cantidad_default": item.get("cantidad_default", 1)},
                )

    # ────────────────────────────────────────────────────────
    def _seed_users(self, users) -> dict[str, User]:
        por_nombre = {}
        for u in users:
            email = u["email"].lower()
            username = email.split("@")[0]
            empresa = Empresa.objects.filter(nombre=u.get("empresa", "")).first()
            usuario, _created = User.objects.update_or_create(
                email=email,
                defaults={
                    "username": username,
                    "name": u["nombre"],
                    "nivel": u["nivel"],
                    "empresa": empresa,
                    "rol_descriptivo": u.get("rol", ""),
                    "modulos_permitidos": u.get("modulos_permitidos"),
                    "permisos_extra": u.get("permisos_extra") or [],
                    "is_active": u.get("activo", True),
                    # Nivel 1 administra también el Django admin
                    "is_staff": u["nivel"] == 1,
                    "is_superuser": u["nivel"] == 1,
                },
            )
            usuario.set_password(u["pwd"])
            usuario.save(update_fields=["password"])
            EmailAddress.objects.update_or_create(
                user=usuario,
                email=email,
                defaults={"verified": True, "primary": True},
            )
            por_nombre[u["nombre"]] = usuario
        return por_nombre

    # ────────────────────────────────────────────────────────
    def _seed_equipos(self, equipos):
        for e in equipos:
            servicio = Servicio.objects.get(nombre=e["categoria"])
            ciudad = Ciudad.objects.get(nombre=e["ciudad_base"])
            equipo, _created = Equipo.objects.update_or_create(
                codigo=e["id"],
                defaults={
                    "servicio": servicio,
                    "modelo": e["modelo"],
                    "serial": e["serial"],
                    "estado": e.get("estado", "disponible"),
                    "responsable": e.get("responsable", ""),
                    "ciudad_base": ciudad,
                    "ultima_revision": _parse_date(e.get("ultima_revision")),
                    "proxima_mantencion": _parse_date(e.get("proxima_mantencion")),
                    "notas": e.get("notas", ""),
                    "historial_uso": e.get("historial_uso", 0),
                },
            )
            equipo.accesorios.all().delete()
            Accesorio.objects.bulk_create(
                Accesorio(
                    equipo=equipo,
                    nombre=a["nombre"],
                    cantidad=a.get("cantidad", 1),
                    completo=a.get("completo", True),
                    requiere_lavado=a.get("requiere_lavado", False),
                    consumible=a.get("consumible", False),
                )
                for a in e.get("accesorios", [])
            )

    # ────────────────────────────────────────────────────────
    def _seed_paquetes(self, paquetes):
        for p in paquetes:
            paquete, _created = Paquete.objects.update_or_create(
                codigo=p["id"],
                defaults={
                    "nombre": p["nombre"],
                    "descripcion": p.get("desc", ""),
                    "duracion_dias": p.get("duracion_dias", 1),
                    "activo": p.get("activo", True),
                },
            )
            paquete.servicios_requeridos.set(
                Servicio.objects.filter(nombre__in=p["equipos_requeridos"]),
            )

    # ────────────────────────────────────────────────────────
    def _seed_reservas(self, reservas, usuarios_por_nombre):
        for r in reservas:
            reserva, _created = Reserva.objects.update_or_create(
                codigo=r["id"],
                defaults={
                    "servicio": Servicio.objects.get(nombre=r["servicio"]),
                    "cliente": Empresa.objects.get(nombre=r["cliente"]),
                    "ciudad": Ciudad.objects.get(nombre=r["ciudad"]),
                    "personas": r["personas"],
                    "contactos_efectivos": r.get("contactos_efectivos", 0),
                    "fecha_salida": _parse_date(r["fecha_salida"]),
                    "fecha_retorno_esp": _parse_date(r["fecha_retorno_esp"]),
                    "estado": r.get("estado", "confirmada"),
                    "cancelada": r.get("cancelada", False),
                    "motivo_cancelacion": r.get("motivo_cancelacion") or "",
                    "reprogramada_desde": _parse_date(r.get("reprogramada_desde")),
                    "riesgo": r.get("riesgo", 0.0),
                },
            )
            if r.get("equipo_id"):
                equipo = Equipo.objects.filter(codigo=r["equipo_id"]).first()
                reserva.equipos.set([equipo] if equipo else [])
            conf = r.get("confirmado_retorno")
            if isinstance(conf, dict):
                ConfirmacionRetorno.objects.update_or_create(
                    reserva=reserva,
                    defaults={
                        "fecha": _parse_date(conf["fecha"]),
                        "estado_kit": conf.get("estado", "OK"),
                        "notas": conf.get("notas", ""),
                        "operador": usuarios_por_nombre.get(conf.get("operador", "")),
                        "requiere_preparacion": conf.get("requiere_preparacion", False),
                        "preparacion_completa": conf.get("preparacion_completa", False),
                    },
                )
            if not reserva.historial.exists():
                HistorialReserva.objects.create(
                    reserva=reserva,
                    accion="creada",
                    detalle=f"Reserva importada del prototipo · {r['servicio']} · {r['cliente']}",
                )

    # ────────────────────────────────────────────────────────
    def _seed_solicitudes(self, solicitudes, usuarios_por_nombre):
        for s in solicitudes:
            solicitante = User.objects.filter(email=s["solicitante_email"].lower()).first()
            if solicitante is None:
                self.stdout.write(self.style.WARNING(
                    f"Solicitud {s['id']}: solicitante {s['solicitante_email']} no existe, omitida",
                ))
                continue
            fecha_solicitud = _parse_date(s["fecha_solicitud"])
            # B4 · el prototipo perdía la fecha pedida; para el histórico usamos
            # la confirmada o solicitud+7 como mejor aproximación
            fecha_sugerida = _parse_date(s.get("fecha_confirmada")) or (
                fecha_solicitud + timedelta(days=7)
            )
            solicitud, _created = Solicitud.objects.update_or_create(
                codigo=s["id"],
                defaults={
                    "solicitante": solicitante,
                    "empresa_cliente": Empresa.objects.get(nombre=s["empresa_cliente"]),
                    "servicio": Servicio.objects.get(nombre=s["servicio"]),
                    "ciudad": Ciudad.objects.get(nombre=s["ciudad"]),
                    "personas": s["personas"],
                    "fecha_sugerida": fecha_sugerida,
                    "fecha_confirmada": _parse_date(s.get("fecha_confirmada")),
                    "operador": usuarios_por_nombre.get(s.get("operador") or ""),
                    "estado": s.get("estado", "pendiente"),
                    "prof_perfil": "Profesional en ergonomía",
                },
            )
            # auto_now_add ignora el valor en el create: forzar la fecha real
            Solicitud.objects.filter(pk=solicitud.pk).update(fecha_solicitud=fecha_solicitud)

    # ────────────────────────────────────────────────────────
    def _seed_planes(self, planes):
        for p in planes:
            Plan.objects.update_or_create(
                codigo=p["id"],
                defaults={
                    "area": p.get("app", ""),
                    "titulo": p["titulo"],
                    "descripcion": p.get("desc", ""),
                    "responsable": p.get("responsable", ""),
                    "vence": _parse_date(p["vence"]),
                    "avance": p.get("avance", 0),
                    "esperado": p.get("esperado", 0),
                    "estado": p.get("estado", "open"),
                },
            )

    # ────────────────────────────────────────────────────────
    def _seed_canales(self, canales):
        for canal, cfg in canales.items():
            ConfiguracionCanal.objects.update_or_create(
                canal=canal,
                defaults={
                    "activo": cfg.get("activo", False),
                    "label": cfg.get("label", ""),
                    "destino": cfg.get(DESTINO_KEY.get(canal, "destino"), ""),
                },
            )
