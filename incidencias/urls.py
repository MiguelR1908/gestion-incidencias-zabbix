from django.urls import path

from . import views


app_name = "incidencias"


urlpatterns = [

    # ==========================================================
    # DASHBOARD
    # ==========================================================

    path(
        "",
        views.dashboard,
        name="dashboard",
    ),


    # ==========================================================
    # INCIDENCIAS
    # ==========================================================

    path(
        "incidencias/",
        views.incidencias_page,
        name="incidencias",
    ),

    path(
        "incidencias/sincronizar/",
        views.incidencias_sincronizar,
        name="incidencias_sincronizar",
    ),

    path(
        "incidencias/<int:incidencia_id>/detalle/",
        views.incidencia_detalle,
        name="incidencia_detalle",
    ),

    path(
        "incidencias/<int:incidencia_id>/asignar/",
        views.incidencia_asignar,
        name="incidencia_asignar",
    ),

    path(
        "incidencias/<int:incidencia_id>/iniciar-atencion/",
        views.incidencia_iniciar_atencion,
        name="incidencia_iniciar_atencion",
    ),

    path(
        "incidencias/<int:incidencia_id>/resolver/",
        views.incidencia_resolver,
        name="incidencia_resolver",
    ),

    path(
        "incidencias/<int:incidencia_id>/cerrar/",
        views.incidencia_cerrar,
        name="incidencia_cerrar",
    ),

    path(
        "incidencias/<int:incidencia_id>/reporte/",
        views.reporte_incidencia,
        name="reporte_incidencia",
    ),

    path(
        "incidencias/exportar/csv/",
        views.exportar_incidencias_csv,
        name="exportar_incidencias_csv",
    ),


    # ==========================================================
    # ASIGNACIONES
    # ==========================================================

    path(
        "asignaciones/",
        views.asignaciones_page,
        name="asignaciones",
    ),


    # ==========================================================
    # USUARIOS
    # ==========================================================

    path(
        "usuarios/",
        views.usuarios_lista,
        name="usuarios_lista",
    ),

    path(
        "usuarios/crear/",
        views.usuario_crear,
        name="usuario_crear",
    ),

    path(
        "usuarios/<int:user_id>/editar/",
        views.usuario_editar,
        name="usuario_editar",
    ),

    path(
        "usuarios/<int:user_id>/estado/",
        views.usuario_cambiar_estado,
        name="usuario_cambiar_estado",
    ),


    # ==========================================================
    # INFRAESTRUCTURA
    # ==========================================================

    path(
        "infraestructura/",
        views.infraestructura_inventario,
        name="infraestructura_inventario",
    ),


    # ==========================================================
    # UBICACIONES
    # ==========================================================

    path(
        "ubicaciones/",
        views.ubicaciones_lista,
        name="ubicaciones_lista",
    ),

    path(
        "ubicaciones/crear/",
        views.ubicacion_crear,
        name="ubicacion_crear",
    ),

    path(
        "ubicaciones/<int:ubicacion_id>/editar/",
        views.ubicacion_editar,
        name="ubicacion_editar",
    ),

    path(
        "ubicaciones/<int:ubicacion_id>/estado/",
        views.ubicacion_cambiar_estado,
        name="ubicacion_cambiar_estado",
    ),


    # ==========================================================
    # NODOS
    # ==========================================================

    path(
        "nodos/",
        views.nodos_lista,
        name="nodos_lista",
    ),

    path(
        "nodos/crear/",
        views.nodo_crear,
        name="nodo_crear",
    ),

    path(
        "nodos/<int:nodo_id>/editar/",
        views.nodo_editar,
        name="nodo_editar",
    ),

    path(
        "nodos/<int:nodo_id>/estado/",
        views.nodo_cambiar_estado,
        name="nodo_cambiar_estado",
    ),


    # ==========================================================
    # COMPONENTES
    # ==========================================================

    path(
        "componentes/",
        views.componentes_lista,
        name="componentes_lista",
    ),

    path(
        "componentes/crear/",
        views.componente_crear,
        name="componente_crear",
    ),

    path(
        "componentes/<int:componente_id>/editar/",
        views.componente_editar,
        name="componente_editar",
    ),

    path(
        "componentes/<int:componente_id>/estado/",
        views.componente_cambiar_estado,
        name="componente_cambiar_estado",
    ),


    # ==========================================================
    # ZABBIX - CONFIGURACIÓN
    # ==========================================================


    path(
        "zabbix/configuracion/",
        views.configuracion_zabbix_lista,
        name="configuracion_zabbix_lista",
    ),

    path(
        "zabbix/configuracion/crear/",
        views.configuracion_zabbix_crear,
        name="configuracion_zabbix_crear",
    ),

    path(
        "zabbix/configuracion/<int:configuracion_id>/editar/",
        views.configuracion_zabbix_editar,
        name="configuracion_zabbix_editar",
    ),

    path(
        "zabbix/configuracion/<int:configuracion_id>/probar/",
        views.configuracion_zabbix_probar,
        name="configuracion_zabbix_probar",
    ),


    # ==========================================================
    # ZABBIX - HOSTS
    # ==========================================================

    path(
        "zabbix/hosts/",
        views.zabbix_hosts_lista,
        name="zabbix_hosts_lista",
    ),

    path(
        "zabbix/hosts/sincronizar/",
        views.zabbix_hosts_sincronizar,
        name="zabbix_hosts_sincronizar",
    ),


    # ==========================================================
    # ZABBIX - ALERTAS
    # ==========================================================

    path(
        "zabbix/alertas/",
        views.zabbix_alertas_activas,
        name="zabbix_alertas_activas",
    ),

    path(
        "zabbix/alertas/sincronizar/",
        views.zabbix_alertas_sincronizar,
        name="zabbix_alertas_sincronizar",
    ),

    path(
        "alertas-sistema/",
        views.alertas_sistema_lista,
        name="alertas_sistema_lista",
    ),


    # ==========================================================
    # REPORTES
    # ==========================================================

    # ----------------------------------------------------------
    # REPORTE GENERAL DE INCIDENCIAS
    # ----------------------------------------------------------

    path(
        "reportes/incidencias/",
        views.reporte_incidencias,
        name="reporte_incidencias",
    ),

    path(
        "reportes/incidencias/pdf/",
        views.reporte_incidencias_pdf,
        name="reporte_incidencias_pdf",
    ),


    # ----------------------------------------------------------
    # RECURRENCIA POR NODO / COMPONENTE
    # ----------------------------------------------------------

    path(
        "reportes/nodos-componentes/",
        views.reporte_nodos_componentes,
        name="reporte_nodos_componentes",
    ),

    path(
        "reportes/nodos-componentes/exportar/",
        views.exportar_reporte_nodos_componentes_csv,
        name="exportar_reporte_nodos_componentes_csv",
    ),


    # ----------------------------------------------------------
    # SLA Y TIEMPOS
    # ----------------------------------------------------------

    path(
        "reportes/sla-tiempos/",
        views.reporte_sla_tiempos,
        name="reporte_sla_tiempos",
    ),

    path(
        "reportes/sla-tiempos/exportar/",
        views.exportar_reporte_sla_tiempos_csv,
        name="exportar_reporte_sla_tiempos_csv",
    ),


    # ----------------------------------------------------------
    # RENDIMIENTO POR TÉCNICO
    # ----------------------------------------------------------

    path(
        "reportes/tecnicos/",
        views.reporte_tecnicos,
        name="reporte_tecnicos",
    ),

    path(
        "reportes/tecnicos/exportar/",
        views.exportar_reporte_tecnicos_csv,
        name="exportar_reporte_tecnicos_csv",
    ),


    # ==========================================================
    # CONFIGURACIÓN SLA
    # ==========================================================

    path(
        "sla/configuracion/",
        views.sla_configuracion_lista,
        name="sla_configuracion_lista",
    ),

    path(
        "sla/configuracion/<int:sla_id>/editar/",
        views.sla_configuracion_editar,
        name="sla_configuracion_editar",
    ),


    # ==========================================================
    # NOTIFICACIONES
    # ==========================================================

    path(
        "notificaciones/",
        views.notificaciones_lista,
        name="notificaciones_lista",
    ),

    path(
        "notificaciones/nuevas/",
        views.notificaciones_nuevas,
        name="notificaciones_nuevas",
    ),

    path(
        "notificaciones/<int:notificacion_id>/abrir/",
        views.notificacion_abrir,
        name="notificacion_abrir",
    ),

    path(
        "notificaciones/marcar-todas-leidas/",
        views.notificaciones_marcar_todas_leidas,
        name="notificaciones_marcar_todas_leidas",
    ),


    # ==========================================================
    # SISTEMA
    # ==========================================================

    path(
        "login/",
        views.login_view,
        name="login",
    ),

    path(
        "logout/",
        views.logout_view,
        name="logout",
    ),

    path(
        "acceso-denegado/",
        views.acceso_denegado,
        name="acceso_denegado",
    ),


    # ==========================================================
    # 404 - SIEMPRE AL FINAL
    # ==========================================================

    path(
        "<path:ruta_invalida>/",
        views.pagina_no_encontrada,
        name="pagina_no_encontrada",
    ),
]