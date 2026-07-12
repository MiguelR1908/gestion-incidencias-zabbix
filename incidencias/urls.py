from django.urls import path
from . import views

app_name = 'incidencias'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path("incidencias/", views.incidencias_page, name="incidencias"),
    path("asignaciones/", views.asignaciones_page, name="asignaciones"),
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
    # Configuración Zabbix
    path("zabbix/configuracion/", views.configuracion_zabbix_lista, name="configuracion_zabbix_lista"),
    path("zabbix/configuracion/crear/", views.configuracion_zabbix_crear, name="configuracion_zabbix_crear"),
    path("zabbix/configuracion/<int:configuracion_id>/editar/", views.configuracion_zabbix_editar, name="configuracion_zabbix_editar"),
    path("zabbix/configuracion/<int:configuracion_id>/probar/", views.configuracion_zabbix_probar, name="configuracion_zabbix_probar"),
    path("zabbix/hosts/", views.zabbix_hosts_lista, name="zabbix_hosts_lista"),
    path("zabbix/alertas/", views.zabbix_alertas_activas, name="zabbix_alertas_activas"),
    path("zabbix/alertas/sincronizar/", views.zabbix_alertas_sincronizar, name="zabbix_alertas_sincronizar"),

    path("alertas-sistema/", views.alertas_sistema_lista, name="alertas_sistema_lista"),

    path("sla-indicadores/", views.sla_indicadores_page, name="sla_indicadores"),
    path("reportes/", views.reportes_page, name="reportes"),
    path("configuracion/", views.configuracion_page, name="configuracion"),

    #SYSTEM
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path("acceso-denegado/", views.acceso_denegado, name="acceso_denegado"),
    path("<path:ruta_invalida>/", views.pagina_no_encontrada, name="pagina_no_encontrada"),
]