from django.conf import settings
from rest_framework.routers import DefaultRouter
from rest_framework.routers import SimpleRouter

from rehavid_app.equipos.api.views import EquipoViewSet
from rehavid_app.paquetes.api.views import PaqueteViewSet
from rehavid_app.reservas.api.views import ReservaViewSet
from rehavid_app.users.api.views import UserViewSet

router = DefaultRouter() if settings.DEBUG else SimpleRouter()

router.register("users", UserViewSet)
router.register("reservas", ReservaViewSet, basename="reserva")
router.register("equipos", EquipoViewSet, basename="equipo")
router.register("paquetes", PaqueteViewSet, basename="paquete")


app_name = "api"
urlpatterns = router.urls
