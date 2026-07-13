from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from rehavid_app.catalogo.models import Ciudad
from rehavid_app.catalogo.models import Empresa
from rehavid_app.catalogo.models import Servicio
from rehavid_app.equipos.models import Equipo
from rehavid_app.paquetes.models import Paquete
from rehavid_app.reservas.models import Reserva


class ServicioFactory(DjangoModelFactory):
    class Meta:
        model = Servicio
        django_get_or_create = ["nombre"]

    nombre = factory.Sequence(lambda n: f"Servicio-{n}")
    requiere_equipo_fisico = True


class CiudadFactory(DjangoModelFactory):
    class Meta:
        model = Ciudad
        django_get_or_create = ["nombre"]

    nombre = factory.Sequence(lambda n: f"Ciudad-{n}")


class EmpresaFactory(DjangoModelFactory):
    class Meta:
        model = Empresa
        django_get_or_create = ["nombre"]

    nombre = factory.Sequence(lambda n: f"Empresa-{n}")


class EquipoFactory(DjangoModelFactory):
    class Meta:
        model = Equipo

    codigo = factory.Sequence(lambda n: f"EQ-{n:03d}")
    servicio = factory.SubFactory(ServicioFactory)
    modelo = "Modelo demo"
    serial = factory.Sequence(lambda n: f"SER-{n:05d}")
    ciudad_base = factory.SubFactory(CiudadFactory)


class PaqueteFactory(DjangoModelFactory):
    class Meta:
        model = Paquete
        skip_postgeneration_save = True

    codigo = factory.Sequence(lambda n: f"PKG-T{n:02d}")
    nombre = factory.Sequence(lambda n: f"Paquete {n}")
    duracion_dias = 2

    @factory.post_generation
    def servicios(self, create, extracted, **kwargs):
        if create and extracted:
            self.servicios_requeridos.set(extracted)


class ReservaFactory(DjangoModelFactory):
    class Meta:
        model = Reserva

    servicio = factory.SubFactory(ServicioFactory)
    cliente = factory.SubFactory(EmpresaFactory)
    ciudad = factory.SubFactory(CiudadFactory)
    personas = 5
    fecha_salida = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=3))
    fecha_retorno_esp = factory.LazyFunction(lambda: timezone.localdate() + timedelta(days=5))
