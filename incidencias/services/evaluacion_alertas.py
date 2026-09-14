from django.db import transaction
from django.utils import timezone

from ..models import (
    AccionHistorial,
    AlertaZabbix,
    EstadoIncidencia,
    EstadoZabbix,
    HistorialIncidencia,
    Incidencia,
    OrigenIncidencia,
    Severidad,
    SLAIncidencia,
)
from .notificaciones import crear_notificacion_sistema

# ============================================================
# REGLAS PARA CREAR INCIDENCIAS SEGÚN SEVERIDAD ZABBIX
# ============================================================
#
# Zabbix                  Sistema             Tiempo mínimo
# ------------------------------------------------------------
# Disaster                CRITICA             5 minutos
# High                    ALTA                10 minutos
# Average                 MEDIA               20 minutos
# Warning                 BAJA                60 minutos
# Information             INFORMATIVA         No crea incidencia
# Not classified          Sin clasificación   No crea incidencia
#
# Cualquier severidad que no esté en este diccionario
# no generará una incidencia automática.
# ============================================================




def evaluar_alerta_para_incidencia(alerta, usuario=None):
    """
    Evalúa una alerta sincronizada desde Zabbix y determina si debe
    convertirse automáticamente en una incidencia.

    Reglas:

    - Disaster / Crítica:
      crea incidencia después de 5 minutos.

    - High / Alta:
      crea incidencia después de 10 minutos.

    - Average / Media:
      crea incidencia después de 20 minutos.

    - Warning / Baja:
      crea incidencia después de 60 minutos.

    - Information / Informativa:
      no crea incidencia.

    - Not classified:
      no crea incidencia.

    Además:

    - La alerta debe seguir en estado PROBLEM.
    - La alerta no debe haber sido procesada.
    - No debe existir una incidencia asociada.
    - Debe tener un componente activo.
    - El componente debe estar monitoreado por Zabbix.

    Retorna un diccionario con:

    - creada
    - estado
    - motivo
    - incidencia
    - minutos_activa
    - minutos_requeridos
    """

    usuario_valido = (
        usuario
        if usuario is not None
        and getattr(usuario, "is_authenticated", False)
        else None
    )

    with transaction.atomic():

        # ------------------------------------------------------------
        # Bloquear la alerta durante la evaluación
        # ------------------------------------------------------------
        #
        # Esto evita que dos procesos simultáneos creen dos
        # incidencias para la misma alerta.
        # ------------------------------------------------------------

        alerta = (
            AlertaZabbix.objects
            .select_for_update()
            .select_related(
                "componente_red",
                "componente_red__nodo",
            )
            .get(pk=alerta.pk)
        )

        # ============================================================
        # 1. VERIFICAR SI YA EXISTE UNA INCIDENCIA
        # ============================================================

        incidencia_existente = (
            Incidencia.objects
            .filter(alerta_zabbix=alerta)
            .first()
        )

        if incidencia_existente:

            # Si existe una incidencia, aseguramos que la alerta
            # quede marcada como procesada.
            if not alerta.procesada:
                alerta.procesada = True

                if usuario_valido:
                    alerta.actualizado_por = usuario_valido

                alerta.save()

            return {
                "creada": False,
                "estado": "INCIDENCIA_EXISTENTE",
                "motivo": (
                    f"La alerta ya tiene asociada la incidencia "
                    f"{incidencia_existente.codigo}."
                ),
                "incidencia": incidencia_existente,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        # ============================================================
        # 2. VERIFICAR SI LA ALERTA YA FUE PROCESADA
        # ============================================================

        if alerta.procesada:
            return {
                "creada": False,
                "estado": "YA_PROCESADA",
                "motivo": (
                    "La alerta ya fue procesada anteriormente."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        # ============================================================
        # 3. VERIFICAR QUE LA ALERTA SIGA ACTIVA
        # ============================================================

        if alerta.estado_zabbix != EstadoZabbix.PROBLEM:
            return {
                "creada": False,
                "estado": "ALERTA_NO_ACTIVA",
                "motivo": (
                    "La alerta ya no se encuentra en estado PROBLEM."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        # ============================================================
        # 4. VALIDAR EL COMPONENTE ASOCIADO
        # ============================================================

        componente = alerta.componente_red

        if componente.nodo.codigo == "ZBX-PENDIENTE":
            return {
                "creada": False,
                "estado": "COMPONENTE_PENDIENTE_CLASIFICACION",
                "motivo": (
                    "El componente fue sincronizado desde Zabbix, "
                    "pero todavía debe ser clasificado en el inventario."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        if not componente.activo:
            return {
                "creada": False,
                "estado": "COMPONENTE_INACTIVO",
                "motivo": (
                    "El componente asociado está inactivo "
                    "en el inventario."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        if not componente.es_monitoreado_zabbix:
            return {
                "creada": False,
                "estado": "COMPONENTE_NO_MONITOREADO",
                "motivo": (
                    "El componente asociado no está configurado "
                    "como monitoreado por Zabbix."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }
        ###
        # ============================================================
        # 4.1. VERIFICAR INCIDENCIA ACTIVA EN EL MISMO COMPONENTE
        # ============================================================
        # Evita duplicar tickets si el componente ya tiene un problema
        # en curso. Registra la alerta como reincidencia en el historial.
        
        estados_activos = [
            EstadoIncidencia.DETECTADA,
            EstadoIncidencia.REGISTRADA,
            EstadoIncidencia.ASIGNADA,
            EstadoIncidencia.EN_ATENCION,
            EstadoIncidencia.RESUELTA,
        ]

        incidencia_activa = (
            Incidencia.objects
            .filter(
                componente_principal=componente,
                estado__in=estados_activos,
            )
            .first()
        )

        if incidencia_activa:
            # Si el ticket estaba en RESUELTA pero el problema persiste/reincide
            if incidencia_activa.estado == EstadoIncidencia.RESUELTA:
                incidencia_activa.estado = EstadoIncidencia.EN_ATENCION
                if usuario_valido:
                    incidencia_activa.actualizado_por = usuario_valido
                incidencia_activa.save()

            # Marcar la nueva alerta como procesada
            alerta.procesada = True
            if usuario_valido:
                alerta.actualizado_por = usuario_valido
            alerta.save()

            # Registrar la reincidencia en el historial
            HistorialIncidencia.objects.create(
                incidencia=incidencia_activa,
                usuario=usuario_valido,
                accion=AccionHistorial.REINCIDENCIA_ALERTA, # Ajustar a tu Choice (ej. REINCIDENCIA)
                estado_nuevo=incidencia_activa.estado,
                descripcion=(
                    f"Alerta reincidente o adicional recibida desde Zabbix: '{alerta.nombre_alerta}' "
                    f"(Event ID: {alerta.event_id}). Registrada en el ticket activo."
                ),
                creado_por=usuario_valido,
                actualizado_por=usuario_valido,
            )

            return {
                "creada": False,
                "estado": "REINCIDENCIA_REGISTRADA",
                "motivo": (
                    f"El componente {componente.codigo} ya posee la incidencia activa "
                    f"{incidencia_activa.codigo}. Se registró el evento como reincidencia."
                ),
                "incidencia": incidencia_activa,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }


        # ============================================================
        # 5. OBTENER CONFIGURACIÓN DE CREACIÓN AUTOMÁTICA
        # ============================================================

        sla_config = (
            SLAIncidencia.objects
            .filter(
                severidad=alerta.severidad,
                activo=True,
            )
            .first()
        )

        if not sla_config:
            return {
                "creada": False,
                "estado": "SIN_CONFIGURACION_SLA",
                "motivo": (
                    f"No existe una configuración SLA activa para la severidad "
                    f"{alerta.get_severidad_display()}."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        if not sla_config.genera_incidencia_automatica:
            return {
                "creada": False,
                "estado": "CREACION_AUTOMATICA_DESACTIVADA",
                "motivo": (
                    f"La severidad {alerta.get_severidad_display()} "
                    f"no está configurada para generar incidencias automáticas."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": None,
            }

        minutos_requeridos = (
            sla_config.tiempo_confirmacion_zabbix_min
        )
        # ============================================================
        # 6. VALIDAR LA FECHA DEL EVENTO
        # ============================================================

        if not alerta.fecha_evento:
            return {
                "creada": False,
                "estado": "SIN_FECHA_EVENTO",
                "motivo": (
                    "La alerta no tiene una fecha de evento válida."
                ),
                "incidencia": None,
                "minutos_activa": None,
                "minutos_requeridos": minutos_requeridos,
            }

        # ============================================================
        # 7. CALCULAR CUÁNTO TIEMPO LLEVA ACTIVA
        # ============================================================

        minutos_activa = (
            timezone.now() - alerta.fecha_evento
        ).total_seconds() / 60

        # Evita valores negativos por diferencias de reloj.
        minutos_activa = max(minutos_activa, 0)

        # ============================================================
        # 8. VERIFICAR SI CUMPLIÓ EL TIEMPO MÍNIMO
        # ============================================================

        if minutos_activa < minutos_requeridos:

            minutos_faltantes = (
                minutos_requeridos - minutos_activa
            )

            return {
                "creada": False,
                "estado": "ESPERANDO_CONFIRMACION",
                "motivo": (
                    f"La alerta lleva activa "
                    f"{minutos_activa:.1f} minutos. "
                    f"Debe permanecer activa al menos "
                    f"{minutos_requeridos} minutos. "
                    f"Faltan aproximadamente "
                    f"{minutos_faltantes:.1f} minutos."
                ),
                "incidencia": None,
                "minutos_activa": round(minutos_activa, 1),
                "minutos_requeridos": minutos_requeridos,
            }

        # ============================================================
        # 9. CREAR LA INCIDENCIA
        # ============================================================

        incidencia = Incidencia(
            alerta_zabbix=alerta,
            nodo_afectado=componente.nodo,
            componente_principal=componente,

            titulo=alerta.nombre_alerta,

            descripcion=(
                alerta.descripcion
                or alerta.nombre_alerta
            ),

            origen=OrigenIncidencia.ZABBIX,

            # El impacto se obtiene del componente asociado.
            tipo_afectacion=componente.impacto_por_caida,

            # La severidad interna ya fue normalizada durante
            # la sincronización desde Zabbix.
            severidad=alerta.severidad,

            estado=EstadoIncidencia.DETECTADA,

            # Se conserva como fecha de detección el momento real
            # en el que Zabbix generó el evento.
            fecha_deteccion=alerta.fecha_evento,

            registrado_por=usuario_valido,
            creado_por=usuario_valido,
            actualizado_por=usuario_valido,
        )

        incidencia.save()
        crear_notificacion_sistema(
            incidencia=incidencia,
            mensaje=(
                f"Nueva incidencia {incidencia.codigo} detectada automáticamente. "
                f"Severidad: {incidencia.get_severidad_display()}. "
                f"Nodo: {incidencia.nodo_afectado.codigo}. "
                f"Componente: {incidencia.componente_principal.codigo}."
            ),
            creado_por=usuario_valido,
        )
        # ============================================================
        # 10. MARCAR LA ALERTA COMO PROCESADA
        # ============================================================

        alerta.procesada = True

        if usuario_valido:
            alerta.actualizado_por = usuario_valido

        alerta.save()

        # ============================================================
        # 11. REGISTRAR EL HISTORIAL
        # ============================================================

        historial = HistorialIncidencia(
            incidencia=incidencia,
            usuario=usuario_valido,
            accion=AccionHistorial.CREACION,
            estado_nuevo=incidencia.estado,

            descripcion=(
                "Incidencia creada automáticamente desde una "
                "alerta de Zabbix. "
                f"Severidad: {alerta.get_severidad_display()}. "
                f"Tiempo activa: {minutos_activa:.1f} minutos. "
                f"Tiempo mínimo requerido: "
                f"{minutos_requeridos} minutos. "
                f"Componente asociado: {componente.codigo}."
            ),

            creado_por=usuario_valido,
            actualizado_por=usuario_valido,
        )

        historial.save()

        # ============================================================
        # 12. RETORNAR RESULTADO EXITOSO
        # ============================================================

        return {
            "creada": True,
            "estado": "INCIDENCIA_CREADA",
            "motivo": (
                f"Se creó automáticamente la incidencia "
                f"{incidencia.codigo}."
            ),
            "incidencia": incidencia,
            "minutos_activa": round(minutos_activa, 1),
            "minutos_requeridos": minutos_requeridos,
        }