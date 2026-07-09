from django.urls import path
from . import views

app_name = 'incidencias'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    #Usuarios
    path("usuarios/", views.usuarios_lista, name="usuarios_lista"),
    path("usuarios/crear/", views.usuario_crear, name="usuario_crear"),
    path("usuarios/<int:user_id>/editar/", views.usuario_editar, name="usuario_editar"),
    path("usuarios/<int:user_id>/estado/", views.usuario_cambiar_estado, name="usuario_cambiar_estado"),
    
    # Infraestructura
    path("infraestructura/", views.infraestructura_inventario, name="infraestructura_inventario"),
    # Ubicaciones
    path("ubicaciones/", views.ubicaciones_lista, name="ubicaciones_lista"),
    path("ubicaciones/crear/", views.ubicacion_crear, name="ubicacion_crear"),
    path("ubicaciones/<int:ubicacion_id>/editar/", views.ubicacion_editar, name="ubicacion_editar"),
    path("ubicaciones/<int:ubicacion_id>/estado/", views.ubicacion_cambiar_estado, name="ubicacion_cambiar_estado"),


    # Nodos
    path("nodos/", views.nodos_lista, name="nodos_lista"),
    path("nodos/crear/", views.nodo_crear, name="nodo_crear"),
    path("nodos/<int:nodo_id>/editar/", views.nodo_editar, name="nodo_editar"),
    path("nodos/<int:nodo_id>/estado/", views.nodo_cambiar_estado, name="nodo_cambiar_estado"),

    # Componentes de red
    path("componentes/", views.componentes_lista, name="componentes_lista"),
    path("componentes/crear/", views.componente_crear, name="componente_crear"),
    path("componentes/<int:componente_id>/editar/", views.componente_editar, name="componente_editar"),
    path("componentes/<int:componente_id>/estado/", views.componente_cambiar_estado, name="componente_cambiar_estado"),
    



    path("sla-indicadores/", views.sla_indicadores_page, name="sla_indicadores"),
    path("reportes/", views.reportes_page, name="reportes"),
    path("configuracion/", views.configuracion_page, name="configuracion"),


    #SYSTEM
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path("acceso-denegado/", views.acceso_denegado, name="acceso_denegado"),
    path("<path:ruta_invalida>/", views.pagina_no_encontrada, name="pagina_no_encontrada"),
]