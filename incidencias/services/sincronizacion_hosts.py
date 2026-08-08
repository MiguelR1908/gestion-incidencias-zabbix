from django.db import transaction
from django.utils import timezone

from ..models import (
    ComponenteRed,
    ConfiguracionZabbix,
    Criticidad,
    EstadoGeneral,
    EstadoLogIntegracion,
    EstadoOperativo,
    FuncionComponenteRed,
    ImpactoPorCaida,
    LogIntegracionZabbix,
    Nodo,
    ProcesoZabbix,
    TipoComponenteRed,
    Ubicacion,
)
from ..zabbix_api import ZabbixClient


CODIGO_NODO_PENDIENTE = "ZBX-PENDIENTE"
NOMBRE_NODO_PENDIENTE = "Pendiente de clasificación Zabbix"


def obtener_usuario_valido(usuario):
    """
    Devuelve el usuario autenticado o None.
    """

    if (
        usuario is not None
        and getattr(usuario, "is_authenticated", False)
    ):
        return usuario

    return None


def obtener_nodo_pendiente(usuario=None):
    """
    Crea o recupera la ubicación y el nodo temporal donde se
    registran los hosts nuevos provenientes de Zabbix.
    """

    usuario_valido = obtener_usuario_valido(usuario)

    ubicacion = (
        Ubicacion.objects
        .filter(nombre=NOMBRE_NODO_PENDIENTE)
        .order_by("id")
        .first()
    )

    if ubicacion is None:
        ubicacion = Ubicacion.objects.create(
            nombre=NOMBRE_NODO_PENDIENTE,
            departamento="Junín",
            provincia="Huancayo",
            descripcion=(
                "Ubicación temporal para hosts sincronizados desde "
                "Zabbix que aún no fueron clasificados."
            ),
            activo=True,
            creado_por=usuario_valido,
            actualizado_por=usuario_valido,
        )

    nodo, creado = Nodo.objects.get_or_create(
        codigo=CODIGO_NODO_PENDIENTE,
        defaults={
            "ubicacion": ubicacion,
            "nombre": NOMBRE_NODO_PENDIENTE,
            "descripcion": (
                "Nodo temporal para componentes importados "
                "automáticamente desde Zabbix."
            ),
            "estado": EstadoGeneral.ACTIVO,
            "criticidad": Criticidad.MEDIA,
            "clientes_estimados": 0,
            "activo": True,
            "creado_por": usuario_valido,
            "actualizado_por": usuario_valido,
        },
    )

    if not creado:
        cambios = False

        if not nodo.activo:
            nodo.activo = True
            cambios = True

        if nodo.ubicacion_id != ubicacion.id:
            nodo.ubicacion = ubicacion
            cambios = True

        if usuario_valido:
            nodo.actualizado_por = usuario_valido
            cambios = True

        if cambios:
            nodo.save()

    return nodo


def obtener_interfaz_principal(host):
    """
    Obtiene la interfaz principal del host.

    Prioridad:
    1. Interfaz marcada como main.
    2. Primera interfaz disponible.
    """

    interfaces = host.get("interfaces") or []

    if not interfaces:
        return None

    for interfaz in interfaces:
        if str(interfaz.get("main")) == "1":
            return interfaz

    return interfaces[0]


def obtener_ip_interfaz(interfaz):
    """
    Retorna la IP cuando la interfaz utiliza dirección IP.

    Si utiliza DNS, retorna None porque ip_gestion solo admite IP.
    """

    if not interfaz:
        return None

    usa_ip = str(interfaz.get("useip")) == "1"
    ip = (interfaz.get("ip") or "").strip()

    if usa_ip and ip:
        return ip

    return None


def obtener_ip_disponible(ip, componente=None):
    """
    Evita errores por la restricción unique=True de ip_gestion.

    Si la IP ya pertenece a otro componente, se conserva en el JSON
    técnico, pero no se coloca en ip_gestion.
    """

    if not ip:
        return None

    consulta = ComponenteRed.objects.filter(ip_gestion=ip)

    if componente is not None:
        consulta = consulta.exclude(pk=componente.pk)

    if consulta.exists():
        return None

    return ip


def construir_datos_tecnicos(host, interfaz, pendiente):
    """
    Construye el JSON técnico proveniente de Zabbix.
    """

    grupos = [
        {
            "groupid": grupo.get("groupid"),
            "name": grupo.get("name"),
        }
        for grupo in host.get("hostgroups", [])
    ]

    templates = [
        {
            "templateid": template.get("templateid"),
            "host": template.get("host"),
            "name": template.get("name"),
        }
        for template in host.get("parentTemplates", [])
    ]

    tags = [
        {
            "tag": tag.get("tag"),
            "value": tag.get("value"),
        }
        for tag in host.get("tags", [])
    ]

    return {
        "origen": "ZABBIX",
        "clasificacion_pendiente": pendiente,
        "ultima_sincronizacion": timezone.now().isoformat(),
        "host_zabbix": {
            "hostid": host.get("hostid"),
            "host": host.get("host"),
            "name": host.get("name"),
            "status": host.get("status"),
            "monitoreado": str(host.get("status")) == "0",
        },
        "interfaz_principal": interfaz or {},
        "interfaces": host.get("interfaces", []),
        "grupos": grupos,
        "templates": templates,
        "tags": tags,
    }


def crear_cliente_zabbix(configuracion):
    """
    Construye el cliente API utilizando la configuración activa.
    """

    return ZabbixClient(
        url_api=configuracion.url_api,
        usuario=configuracion.usuario,
        password=configuracion.password,
        token_api=configuracion.token_api,
        usar_token=configuracion.usar_token,
    )


def sincronizar_hosts_zabbix(configuracion, usuario=None):
    """
    Sincroniza automáticamente los hosts de Zabbix con ComponenteRed.

    Host nuevo:
    - Se crea en el nodo ZBX-PENDIENTE.
    - Tipo OTRO.
    - Función OTRO.
    - Impacto COMPONENTE.
    - Criticidad MEDIA.

    Host existente:
    - Actualiza nombre, IP y datos técnicos.
    - No sobrescribe nodo, tipo, función, impacto ni criticidad.

    Host que desaparece de Zabbix:
    - No se elimina.
    - Se marca es_monitoreado_zabbix=False.
    """

    fecha_inicio = timezone.now()
    usuario_valido = obtener_usuario_valido(usuario)

    creados = 0
    actualizados = 0
    sin_cambios = 0
    no_encontrados = 0
    errores = []

    try:
        cliente = crear_cliente_zabbix(configuracion)
        hosts = cliente.obtener_hosts()

        nodo_pendiente = obtener_nodo_pendiente(
            usuario=usuario_valido
        )

        host_ids_recibidos = set()

        for host in hosts:
            host_id = str(host.get("hostid") or "").strip()

            if not host_id:
                errores.append(
                    {
                        "host": host,
                        "error": "El host no tiene hostid.",
                    }
                )
                continue

            host_ids_recibidos.add(host_id)

            try:
                with transaction.atomic():
                    componente = (
                        ComponenteRed.objects
                        .filter(host_id_zabbix=host_id)
                        .first()
                    )

                    interfaz = obtener_interfaz_principal(host)
                    ip_zabbix = obtener_ip_interfaz(interfaz)

                    nombre_host = (
                        host.get("name")
                        or host.get("host")
                        or f"Host Zabbix {host_id}"
                    )

                    monitoreado = str(host.get("status")) == "0"

                    if componente is None:
                        ip_modelo = obtener_ip_disponible(ip_zabbix)

                        componente = ComponenteRed(
                            nodo=nodo_pendiente,
                            codigo=f"ZBX-{host_id}",
                            nombre=nombre_host[:150],
                            tipo=TipoComponenteRed.OTRO,
                            funcion=FuncionComponenteRed.OTRO,
                            ip_gestion=ip_modelo,
                            host_id_zabbix=host_id,
                            es_monitoreado_zabbix=monitoreado,
                            impacto_por_caida=ImpactoPorCaida.COMPONENTE,
                            estado_operativo=EstadoOperativo.OPERATIVO,
                            criticidad=Criticidad.MEDIA,
                            clientes_estimados=0,
                            activo=True,
                            creado_por=usuario_valido,
                            actualizado_por=usuario_valido,
                        )

                        componente.datos_tecnicos_json = (
                            construir_datos_tecnicos(
                                host=host,
                                interfaz=interfaz,
                                pendiente=True,
                            )
                        )

                        componente.save()
                        creados += 1

                    else:
                        hubo_cambios = False

                        ip_modelo = obtener_ip_disponible(
                            ip_zabbix,
                            componente=componente,
                        )

                        datos_anteriores = (
                            componente.datos_tecnicos_json or {}
                        )

                        pendiente = (
                            componente.nodo.codigo
                            == CODIGO_NODO_PENDIENTE
                        )

                        nuevos_datos = construir_datos_tecnicos(
                            host=host,
                            interfaz=interfaz,
                            pendiente=pendiente,
                        )

                        if componente.nombre != nombre_host[:150]:
                            componente.nombre = nombre_host[:150]
                            hubo_cambios = True

                        if (
                            ip_modelo
                            and componente.ip_gestion != ip_modelo
                        ):
                            componente.ip_gestion = ip_modelo
                            hubo_cambios = True

                        if (
                            componente.es_monitoreado_zabbix
                            != monitoreado
                        ):
                            componente.es_monitoreado_zabbix = monitoreado
                            hubo_cambios = True

                        if datos_anteriores != nuevos_datos:
                            componente.datos_tecnicos_json = nuevos_datos
                            hubo_cambios = True

                        if usuario_valido:
                            componente.actualizado_por = usuario_valido

                        if hubo_cambios:
                            componente.save()
                            actualizados += 1
                        else:
                            sin_cambios += 1

            except Exception as exc:
                errores.append(
                    {
                        "host_id": host_id,
                        "host": host.get("host"),
                        "name": host.get("name"),
                        "error": str(exc),
                    }
                )

        # ----------------------------------------------------
        # Hosts locales que ya no aparecen en Zabbix
        # ----------------------------------------------------

        componentes_ausentes = (
            ComponenteRed.objects
            .filter(
                host_id_zabbix__isnull=False,
                es_monitoreado_zabbix=True,
            )
            .exclude(host_id_zabbix__in=host_ids_recibidos)
        )

        for componente in componentes_ausentes:
            datos = componente.datos_tecnicos_json or {}

            datos["estado_sincronizacion"] = "NO_ENCONTRADO"
            datos["ultima_sincronizacion"] = (
                timezone.now().isoformat()
            )

            componente.es_monitoreado_zabbix = False
            componente.datos_tecnicos_json = datos

            if usuario_valido:
                componente.actualizado_por = usuario_valido

            componente.save()
            no_encontrados += 1

        fecha_fin = timezone.now()

        estado_log = (
            EstadoLogIntegracion.PARCIAL
            if errores
            else EstadoLogIntegracion.EXITOSO
        )

        mensaje = (
            f"Hosts consultados: {len(hosts)}. "
            f"Creados: {creados}. "
            f"Actualizados: {actualizados}. "
            f"Sin cambios: {sin_cambios}. "
            f"No encontrados: {no_encontrados}. "
            f"Errores: {len(errores)}."
        )

        LogIntegracionZabbix.objects.create(
            proceso=ProcesoZabbix.SINCRONIZACION_HOSTS,
            estado=estado_log,
            mensaje=mensaje,
            total_alertas=len(hosts),
            total_procesadas=(
                creados
                + actualizados
                + sin_cambios
                + no_encontrados
            ),
            total_errores=len(errores),
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            detalle_json={
                "creados": creados,
                "actualizados": actualizados,
                "sin_cambios": sin_cambios,
                "no_encontrados": no_encontrados,
                "errores": errores,
                "host_ids_recibidos": sorted(host_ids_recibidos),
            },
            creado_por=usuario_valido,
            actualizado_por=usuario_valido,
        )

        return {
            "ok": not errores,
            "estado": estado_log,
            "mensaje": mensaje,
            "consultados": len(hosts),
            "creados": creados,
            "actualizados": actualizados,
            "sin_cambios": sin_cambios,
            "no_encontrados": no_encontrados,
            "errores": errores,
        }

    except Exception as exc:
        fecha_fin = timezone.now()

        LogIntegracionZabbix.objects.create(
            proceso=ProcesoZabbix.SINCRONIZACION_HOSTS,
            estado=EstadoLogIntegracion.ERROR,
            mensaje=f"Error sincronizando hosts: {exc}",
            total_alertas=0,
            total_procesadas=0,
            total_errores=1,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            detalle_json={
                "error": str(exc),
            },
            creado_por=usuario_valido,
            actualizado_por=usuario_valido,
        )

        raise