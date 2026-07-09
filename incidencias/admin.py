from django.contrib import admin

from .models import (
    PerfilUsuario,
    Ubicacion,
    Nodo,
    ComponenteRed,
    CategoriaIncidencia,
    SLAIncidencia,
    AlertaZabbix,
    Incidencia,
    IncidenciaComponenteAfectado,
    AsignacionIncidencia,
    NotificacionIncidencia,
    HistorialIncidencia,
    ComentarioIncidencia,
    EvidenciaIncidencia,
    LogIntegracionZabbix,
    ConfiguracionZabbix,
)


# =====================================================
# PERFIL USUARIO
# =====================================================

@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "rol",
        "telefono",
        "cargo",
        "area",
        "disponible",
        "activo",
    )
    list_filter = ("rol", "disponible", "activo")
    search_fields = (
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "telefono",
        "cargo",
        "area",
    )


# =====================================================
# UBICACION
# =====================================================

@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "departamento",
        "provincia",
        "distrito",
        "activo",
    )
    list_filter = ("departamento", "provincia", "distrito", "activo")
    search_fields = (
        "nombre",
        "departamento",
        "provincia",
        "distrito",
        "direccion_referencia",
    )


# =====================================================
# NODO
# =====================================================

@admin.register(Nodo)
class NodoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "ubicacion",
        "estado",
        "criticidad",
        "clientes_estimados",
        "activo",
    )
    list_filter = ("estado", "criticidad", "activo", "ubicacion")
    search_fields = (
        "codigo",
        "nombre",
        "descripcion",
        "direccion_referencia",
        "ubicacion__nombre",
    )


# =====================================================
# COMPONENTE RED
# =====================================================

@admin.register(ComponenteRed)
class ComponenteRedAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nombre",
        "nodo",
        "tipo",
        "funcion",
        "ip_gestion",
        "host_id_zabbix",
        "estado_operativo",
        "criticidad",
        "impacto_por_caida",
        "activo",
    )
    list_filter = (
        "tipo",
        "funcion",
        "estado_operativo",
        "criticidad",
        "impacto_por_caida",
        "es_monitoreado_zabbix",
        "activo",
        "nodo",
    )
    search_fields = (
        "codigo",
        "nombre",
        "ip_gestion",
        "mac_address",
        "fabricante",
        "modelo",
        "numero_serie",
        "host_id_zabbix",
        "nodo__codigo",
        "nodo__nombre",
    )


# =====================================================
# CATEGORIA INCIDENCIA
# =====================================================

@admin.register(CategoriaIncidencia)
class CategoriaIncidenciaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "descripcion")


# =====================================================
# SLA INCIDENCIA
# =====================================================

@admin.register(SLAIncidencia)
class SLAIncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "severidad",
        "nombre",
        "tiempo_max_registro_min",
        "tiempo_max_asignacion_min",
        "tiempo_max_inicio_atencion_min",
        "tiempo_max_resolucion_min",
        "activo",
    )
    list_filter = ("severidad", "activo")
    search_fields = ("nombre", "descripcion")


# =====================================================
# ALERTA ZABBIX
# =====================================================

@admin.register(AlertaZabbix)
class AlertaZabbixAdmin(admin.ModelAdmin):
    list_display = (
        "event_id",
        "nombre_alerta",
        "componente_red",
        "host_id",
        "severidad",
        "estado_zabbix",
        "fecha_evento",
        "fecha_recuperacion",
        "procesada",
    )
    list_filter = (
        "severidad",
        "estado_zabbix",
        "procesada",
        "acknowledged",
        "fecha_evento",
    )
    search_fields = (
        "event_id",
        "trigger_id",
        "problem_id",
        "host_id",
        "nombre_alerta",
        "componente_red__codigo",
        "componente_red__nombre",
    )
    readonly_fields = (
        "creado_en",
        "actualizado_en",
    )


# =====================================================
# INCIDENCIA
# =====================================================

class IncidenciaComponenteAfectadoInline(admin.TabularInline):
    model = IncidenciaComponenteAfectado
    extra = 0


class AsignacionIncidenciaInline(admin.TabularInline):
    model = AsignacionIncidencia
    extra = 0
    fk_name = "incidencia"


class ComentarioIncidenciaInline(admin.TabularInline):
    model = ComentarioIncidencia
    extra = 0


class EvidenciaIncidenciaInline(admin.TabularInline):
    model = EvidenciaIncidencia
    extra = 0


@admin.register(Incidencia)
class IncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "titulo",
        "origen",
        "estado",
        "severidad",
        "prioridad",
        "nodo_afectado",
        "componente_principal",
        "tecnico_asignado",
        "fecha_registro",
        "fecha_resolucion",
        "cumple_sla_resolucion",
    )
    list_filter = (
        "origen",
        "estado",
        "severidad",
        "prioridad",
        "tipo_afectacion",
        "cumple_sla_registro",
        "cumple_sla_asignacion",
        "cumple_sla_inicio_atencion",
        "cumple_sla_resolucion",
        "fecha_registro",
    )
    search_fields = (
        "codigo",
        "ticket_externo",
        "titulo",
        "descripcion",
        "solucion",
        "causa_raiz",
        "nodo_afectado__codigo",
        "nodo_afectado__nombre",
        "componente_principal__codigo",
        "componente_principal__nombre",
    )
    readonly_fields = (
        "codigo",
        "cumple_sla_registro",
        "cumple_sla_asignacion",
        "cumple_sla_inicio_atencion",
        "cumple_sla_resolucion",
        "creado_en",
        "actualizado_en",
    )
    inlines = [
        IncidenciaComponenteAfectadoInline,
        AsignacionIncidenciaInline,
        ComentarioIncidenciaInline,
        EvidenciaIncidenciaInline,
    ]


# =====================================================
# INCIDENCIA COMPONENTE AFECTADO
# =====================================================

@admin.register(IncidenciaComponenteAfectado)
class IncidenciaComponenteAfectadoAdmin(admin.ModelAdmin):
    list_display = (
        "incidencia",
        "componente_red",
        "tipo_impacto",
    )
    list_filter = ("tipo_impacto",)
    search_fields = (
        "incidencia__codigo",
        "componente_red__codigo",
        "componente_red__nombre",
    )


# =====================================================
# ASIGNACION INCIDENCIA
# =====================================================

@admin.register(AsignacionIncidencia)
class AsignacionIncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "incidencia",
        "tecnico",
        "asignado_por",
        "fecha_asignacion",
        "activo",
    )
    list_filter = ("activo", "fecha_asignacion")
    search_fields = (
        "incidencia__codigo",
        "incidencia__titulo",
        "tecnico__username",
        "tecnico__first_name",
        "tecnico__last_name",
        "asignado_por__username",
    )


# =====================================================
# NOTIFICACION INCIDENCIA
# =====================================================

@admin.register(NotificacionIncidencia)
class NotificacionIncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "incidencia",
        "usuario_destino",
        "medio",
        "estado",
        "fecha_envio",
    )
    list_filter = ("medio", "estado", "fecha_envio")
    search_fields = (
        "incidencia__codigo",
        "destinatario",
        "mensaje",
        "usuario_destino__username",
    )


# =====================================================
# HISTORIAL INCIDENCIA
# =====================================================

@admin.register(HistorialIncidencia)
class HistorialIncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "incidencia",
        "usuario",
        "accion",
        "estado_anterior",
        "estado_nuevo",
        "fecha_evento",
    )
    list_filter = (
        "accion",
        "estado_anterior",
        "estado_nuevo",
        "fecha_evento",
    )
    search_fields = (
        "incidencia__codigo",
        "usuario__username",
        "descripcion",
        "campo_modificado",
    )
    readonly_fields = (
        "creado_en",
        "actualizado_en",
    )


# =====================================================
# COMENTARIO INCIDENCIA
# =====================================================

@admin.register(ComentarioIncidencia)
class ComentarioIncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "incidencia",
        "usuario",
        "tipo_comentario",
        "creado_en",
    )
    list_filter = ("tipo_comentario", "creado_en")
    search_fields = (
        "incidencia__codigo",
        "usuario__username",
        "comentario",
    )


# =====================================================
# EVIDENCIA INCIDENCIA
# =====================================================

@admin.register(EvidenciaIncidencia)
class EvidenciaIncidenciaAdmin(admin.ModelAdmin):
    list_display = (
        "incidencia",
        "usuario",
        "archivo",
        "creado_en",
    )
    list_filter = ("creado_en",)
    search_fields = (
        "incidencia__codigo",
        "usuario__username",
        "descripcion",
    )


# =====================================================
# LOG INTEGRACION ZABBIX
# =====================================================

@admin.register(LogIntegracionZabbix)
class LogIntegracionZabbixAdmin(admin.ModelAdmin):
    list_display = (
        "proceso",
        "estado",
        "total_alertas",
        "total_procesadas",
        "total_errores",
        "fecha_inicio",
        "fecha_fin",
    )
    list_filter = (
        "proceso",
        "estado",
        "fecha_inicio",
    )
    search_fields = (
        "proceso",
        "estado",
        "mensaje",
    )
    readonly_fields = (
        "duracion_segundos",
        "creado_en",
        "actualizado_en",
    )

@admin.register(ConfiguracionZabbix)
class ConfiguracionZabbixAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "url_api",
        "usar_token",
        "conexion_exitosa",
        "ultima_prueba_conexion",
        "activo",
    )

    list_filter = (
        "usar_token",
        "conexion_exitosa",
        "activo",
    )

    search_fields = (
        "nombre",
        "url_api",
        "usuario",
    )