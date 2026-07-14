from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from django.views import defaults as default_views
from django.views.generic import RedirectView
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.views import SpectacularSwaggerView
from rest_framework.authtoken.views import obtain_auth_token

from config.views import health
from rehavid_app.analitica.api.views import DashboardDataView
from rehavid_app.analitica.api.views import RecomendacionesView
from rehavid_app.predictivo.api import ScoreView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="users:redirect"), name="home"),
    path("health/", health, name="health"),
    path(
        "about/",
        TemplateView.as_view(template_name="pages/about.html"),
        name="about",
    ),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("rehavid_app.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Módulos REHAVID
    path("reservas/", include("rehavid_app.reservas.urls", namespace="reservas")),
    path("equipos/", include("rehavid_app.equipos.urls", namespace="equipos")),
    path("paquetes/", include("rehavid_app.paquetes.urls", namespace="paquetes")),
    path("analitica/", include("rehavid_app.analitica.urls", namespace="analitica")),
    path("predictivo/", include("rehavid_app.predictivo.urls", namespace="predictivo")),
    path("planes/", include("rehavid_app.planes.urls", namespace="planes")),
    path("alertas/", include("rehavid_app.alertas.urls", namespace="alertas")),
    path("auditoria/", include("rehavid_app.auditoria.urls", namespace="auditoria")),
    path("administracion/", include("rehavid_app.users.urls_admin", namespace="administracion")),
    path("portal/", include("rehavid_app.solicitudes.urls_portal", namespace="portal")),
    path("solicitudes/", include("rehavid_app.solicitudes.urls", namespace="solicitudes")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
]

# API URLS
urlpatterns += [
    # API base url
    path("api/", include("config.api_router")),
    path("api/analitica/dashboard/", DashboardDataView.as_view(), name="api-analitica-dashboard"),
    path("api/analitica/recomendaciones/", RecomendacionesView.as_view(), name="api-analitica-recos"),
    path("api/predictivo/score/", ScoreView.as_view(), name="api-predictivo-score"),
    # DRF auth token
    path("api/auth-token/", obtain_auth_token, name="obtain_auth_token"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="api-schema"),
        name="api-docs",
    ),
]

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [
            path("__debug__/", include(debug_toolbar.urls)),
            *urlpatterns,
        ]
