from datetime import datetime

from django.utils import timezone

from ..models import (
    AlertaZabbix,
    ComponenteRed,
    LogIntegracionZabbix,
)
from ..zabbix_api import ZabbixClient
from .evaluacion_alertas import (
    evaluar_alerta_para_incidencia,
)


def obtener_usuario_valido(usuario):
    """
    Devuelve el usuario autenticado o None.

    Permite utilizar el servicio desde:
    - El botón del GUI.
    - Un management command.
    - Una tarea programada.
    """

    if (
        usuario is not None
        and getattr(usuario, "is_authenticated", False)
    ):
        return usuario

    return None


def obtener_valor_choice(modelo, campo, preferidos):
    """
    Devuelve el primer valor compatible con los choices
    configurados en el modelo.
    """

    field = modelo._meta.get_field(campo)
    choices = getattr(field, "choices", None)

    if not choices:
        return preferidos[0]

    valores_validos = [
        valor
        for valor, etiqueta in choices
    ]

    for preferido in preferidos:
        if preferido in valores_validos:
            return preferido

    return valores_validos[0]


def crear_cliente_zabbix(configuracion):
    """
    Construye el cliente API con la configuración Zabbix activa.
    """

    return ZabbixClient(
        url_api=configuracion.url_api,
        usuario=configuracion.usuario,
        password=configuracion.password,
        token_api=configuracion.token_api,
        usar_token=configuracion.usar_token,
    )


def sincronizar_alertas_zabbix(
    configuracion,
    usuario=None,
):
    """
    Consulta problemas activos desde Zabbix.

    Por cada problema:

    1. Obtiene el host asociado.
    2. Busca el componente local por host_id_zabbix.
    3. Crea o actualiza AlertaZabbix usando event_id.
    4. Evalúa severidad y tiempo activo.
    5. Crea una incidencia cuando corresponde.
    6. Registra el resultado de la integración.

    Retorna un diccionario que puede ser utilizado tanto por
    el GUI como por el management command.
    """

    usuario_valido = obtener_usuario_valido(usuario)
    fecha_inicio = timezone.now()

    total_alertas = 0
    total_creadas = 0
    total_actualizadas = 0
    total_sin_componente = 0
    total_incidencias_creadas = 0
    total_esperando = 0
    total_no_aplican = 0
    total_errores = 0

    errores = []
    evaluaciones = []

    # ============================================================
    # VALORES COMPATIBLES CON LOS CHOICES DEL LOG
    # ============================================================

    proceso_log = obtener_valor_choice(
        LogIntegracionZabbix,
        "proceso",
        [
            "SINCRONIZACION_ALERTAS",
            "CONSULTA_ALERTAS",
            "SINCRONIZACION_ZABBIX",
            "SINCRONIZACION",
            "ALERTAS_ZABBIX",
        ],
    )

    estado_exitoso = obtener_valor_choice(
        LogIntegracionZabbix,
        "estado",
        [
            "EXITOSO",
            "EXITO",
            "OK",
            "COMPLETADO",
        ],
    )

    estado_error = obtener_valor_choice(
        LogIntegracionZabbix,
        "estado",
        [
            "ERROR",
            "FALLIDO",
            "FAILED",
        ],
    )

    try:
        # ========================================================
        # 1. CONSULTAR PROBLEMAS ACTIVOS
        # ========================================================

        cliente = crear_cliente_zabbix(configuracion)
        problemas = cliente.obtener_problemas_activos()

        total_alertas = len(problemas)

        # ========================================================
        # 2. PROCESAR CADA PROBLEMA
        # ========================================================

        for problema in problemas:
            try:
                event_id = str(
                    problema.get("eventid") or ""
                ).strip()

                trigger_id = str(
                    problema.get("objectid") or ""
                ).strip()

                nombre_alerta = (
                    problema.get("name")
                    or "Alerta Zabbix"
                )

                severidad_zabbix = str(
                    problema.get("severity", "0")
                )

                acknowledged = (
                    str(
                        problema.get(
                            "acknowledged",
                            "0",
                        )
                    )
                    == "1"
                )

                clock = problema.get("clock")
                hosts = problema.get("hosts") or []
                tags = problema.get("tags") or []

                # ------------------------------------------------
                # Validar event_id
                # ------------------------------------------------

                if not event_id:
                    total_errores += 1

                    error = {
                        "estado": "SIN_EVENT_ID",
                        "problema": nombre_alerta,
                        "error": (
                            "El problema recibido desde Zabbix "
                            "no contiene eventid."
                        ),
                    }

                    errores.append(error)
                    evaluaciones.append(error)

                    continue

                # ------------------------------------------------
                # Obtener host_id
                # ------------------------------------------------

                host_id = ""

                if hosts:
                    host_id = str(
                        hosts[0].get("hostid") or ""
                    ).strip()

                if not host_id:
                    total_sin_componente += 1

                    evaluaciones.append({
                        "event_id": event_id,
                        "estado": "SIN_HOST_ID",
                        "problema": nombre_alerta,
                        "motivo": (
                            "Zabbix no devolvió un host_id "
                            "para este problema."
                        ),
                    })

                    continue

                # ------------------------------------------------
                # Buscar componente local
                # ------------------------------------------------

                componente = (
                    ComponenteRed.objects
                    .select_related("nodo")
                    .filter(
                        host_id_zabbix=host_id,
                        activo=True,
                    )
                    .first()
                )

                if componente is None:
                    total_sin_componente += 1

                    evaluaciones.append({
                        "event_id": event_id,
                        "host_id": host_id,
                        "estado": "SIN_COMPONENTE",
                        "problema": nombre_alerta,
                        "motivo": (
                            "No existe un componente activo "
                            "asociado al host_id de Zabbix."
                        ),
                    })

                    continue

                # ------------------------------------------------
                # Convertir fecha Unix de Zabbix
                # ------------------------------------------------

                if clock:
                    fecha_evento = datetime.fromtimestamp(
                        int(clock),
                        tz=timezone.get_current_timezone(),
                    )
                else:
                    fecha_evento = timezone.now()

                # =================================================
                # 3. MAPEAR SEVERIDAD ZABBIX → SISTEMA
                # =================================================

                mapa_severidad = {
                    "0": [
                        "NO_CLASIFICADA",
                        "NOT_CLASSIFIED",
                    ],
                    "1": [
                        "INFORMATIVA",
                        "INFORMACION",
                        "INFORMATION",
                        "INFO",
                    ],
                    "2": [
                        "BAJA",
                        "WARNING",
                        "ADVERTENCIA",
                    ],
                    "3": [
                        "MEDIA",
                        "AVERAGE",
                        "PROMEDIO",
                    ],
                    "4": [
                        "ALTA",
                        "HIGH",
                    ],
                    "5": [
                        "CRITICA",
                        "CRITICAL",
                        "DISASTER",
                        "DESASTRE",
                    ],
                }

                severidad = obtener_valor_choice(
                    AlertaZabbix,
                    "severidad",
                    mapa_severidad.get(
                        severidad_zabbix,
                        [
                            "NO_CLASIFICADA",
                            "NOT_CLASSIFIED",
                        ],
                    ),
                )

                estado_zabbix = obtener_valor_choice(
                    AlertaZabbix,
                    "estado_zabbix",
                    [
                        "PROBLEM",
                        "ACTIVO",
                        "ABIERTA",
                        "OPEN",
                        "ACTIVE",
                    ],
                )

                # =================================================
                # 4. CREAR O ACTUALIZAR ALERTA LOCAL
                # =================================================

                defaults = {
                    "componente_red": componente,
                    "trigger_id": trigger_id or None,
                    "problem_id": event_id,
                    "host_id": host_id,
                    "nombre_alerta": nombre_alerta,
                    "descripcion": nombre_alerta,
                    "severidad": severidad,
                    "estado_zabbix": estado_zabbix,
                    "fecha_evento": fecha_evento,
                    "acknowledged": acknowledged,
                    "datos_json": problema,
                    "tags_json": tags,
                    "actualizado_por": usuario_valido,
                }

                alerta, creada = (
                    AlertaZabbix.objects.update_or_create(
                        event_id=event_id,
                        defaults=defaults,
                    )
                )

                if creada:
                    total_creadas += 1

                    if usuario_valido:
                        alerta.creado_por = usuario_valido
                        alerta.save(
                            update_fields=[
                                "creado_por",
                            ]
                        )

                else:
                    total_actualizadas += 1

                # =================================================
                # 5. EVALUAR CREACIÓN DE INCIDENCIA
                # =================================================

                resultado = evaluar_alerta_para_incidencia(
                    alerta=alerta,
                    usuario=usuario_valido,
                )

                estado_evaluacion = resultado.get(
                    "estado"
                )

                if resultado.get("creada"):
                    total_incidencias_creadas += 1

                elif (
                    estado_evaluacion
                    == "ESPERANDO_CONFIRMACION"
                ):
                    total_esperando += 1

                else:
                    total_no_aplican += 1

                incidencia = resultado.get("incidencia")

                evaluaciones.append({
                    "event_id": event_id,
                    "host_id": host_id,
                    "componente": componente.codigo,
                    "alerta_creada": creada,
                    "estado_evaluacion": (
                        estado_evaluacion
                    ),
                    "motivo": resultado.get("motivo"),
                    "incidencia": (
                        incidencia.codigo
                        if incidencia
                        else None
                    ),
                    "minutos_activa": resultado.get(
                        "minutos_activa"
                    ),
                    "minutos_requeridos": resultado.get(
                        "minutos_requeridos"
                    ),
                })

            except Exception as exc:
                total_errores += 1

                error = {
                    "event_id": problema.get("eventid"),
                    "problema": problema.get("name"),
                    "estado": "ERROR",
                    "error": str(exc),
                }

                errores.append(error)
                evaluaciones.append(error)

        # ========================================================
        # 6. CONSTRUIR RESUMEN
        # ========================================================

        mensaje = (
            "Sincronización finalizada. "
            f"Consultadas: {total_alertas}. "
            f"Nuevas: {total_creadas}. "
            f"Actualizadas: {total_actualizadas}. "
            f"Sin componente: {total_sin_componente}. "
            f"Incidencias creadas: "
            f"{total_incidencias_creadas}. "
            f"Esperando tiempo mínimo: "
            f"{total_esperando}. "
            f"No aplican: {total_no_aplican}. "
            f"Errores: {total_errores}."
        )

        estado_log = (
            estado_error
            if total_errores > 0
            else estado_exitoso
        )

        # ========================================================
        # 7. REGISTRAR LOG
        # ========================================================

        LogIntegracionZabbix.objects.create(
            proceso=proceso_log,
            estado=estado_log,
            mensaje=mensaje,
            total_alertas=total_alertas,
            total_procesadas=(
                total_creadas
                + total_actualizadas
            ),
            total_errores=total_errores,
            fecha_inicio=fecha_inicio,
            fecha_fin=timezone.now(),
            detalle_json={
                "total_alertas": total_alertas,
                "total_creadas": total_creadas,
                "total_actualizadas": (
                    total_actualizadas
                ),
                "total_sin_componente": (
                    total_sin_componente
                ),
                "total_incidencias_creadas": (
                    total_incidencias_creadas
                ),
                "total_esperando": total_esperando,
                "total_no_aplican": total_no_aplican,
                "total_errores": total_errores,
                "evaluaciones": evaluaciones,
            },
            creado_por=usuario_valido,
            actualizado_por=usuario_valido,
        )

        # ========================================================
        # 8. RETORNAR RESULTADO
        # ========================================================

        return {
            "ok": total_errores == 0,
            "mensaje": mensaje,
            "consultadas": total_alertas,
            "creadas": total_creadas,
            "actualizadas": total_actualizadas,
            "sin_componente": total_sin_componente,
            "incidencias_creadas": (
                total_incidencias_creadas
            ),
            "esperando": total_esperando,
            "no_aplican": total_no_aplican,
            "errores": errores,
        }

    except Exception as exc:
        # ========================================================
        # ERROR GENERAL DE LA INTEGRACIÓN
        # ========================================================

        mensaje = (
            "Error general durante la sincronización "
            f"de alertas: {exc}"
        )

        try:
            LogIntegracionZabbix.objects.create(
                proceso=proceso_log,
                estado=estado_error,
                mensaje=mensaje,
                total_alertas=total_alertas,
                total_procesadas=0,
                total_errores=1,
                fecha_inicio=fecha_inicio,
                fecha_fin=timezone.now(),
                detalle_json={
                    "error": str(exc),
                },
                creado_por=usuario_valido,
                actualizado_por=usuario_valido,
            )

        except Exception:
            # Evita ocultar el error original si también
            # fallara el registro del log.
            pass

        raise RuntimeError(mensaje) from exc