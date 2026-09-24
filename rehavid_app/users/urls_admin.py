from django.urls import path
from django.views.decorators.http import require_POST

from . import admin_views

app_name = "administracion"
urlpatterns = [
    path("arquitectura/", admin_views.ArquitecturaView.as_view(), name="arquitectura"),
    path("usuarios/export/", admin_views.export_usuarios_view, name="usuarios_export"),
    path("usuarios/", admin_views.UsuarioListView.as_view(), name="usuarios"),
    path("usuarios/nuevo/", admin_views.UsuarioCreateView.as_view(), name="usuario_nuevo"),
    path("usuarios/<int:pk>/editar/", admin_views.UsuarioUpdateView.as_view(), name="usuario_editar"),
    path("usuarios/<int:pk>/ficha/", admin_views.UsuarioFichaView.as_view(), name="usuario_ficha"),
    path("usuarios/<int:pk>/toggle/", require_POST(admin_views.toggle_activo_view), name="usuario_toggle"),
    path("empresas/export/", admin_views.export_empresas_view, name="empresas_export"),
    path("empresas/", admin_views.EmpresaListView.as_view(), name="empresas"),
    path("empresas/nuevo/", admin_views.EmpresaCreateView.as_view(), name="empresa_nueva"),
    path("empresas/<int:pk>/editar/", admin_views.EmpresaUpdateView.as_view(), name="empresa_editar"),
    path("empresas/<int:pk>/eliminar/", admin_views.EmpresaDeleteView.as_view(), name="empresa_eliminar"),
]
