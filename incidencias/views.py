from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.db.models import Q
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Ubicacion, Nodo, ComponenteRed, ConfiguracionZabbix, ConfiguracionZabbix, LogIntegracionZabbix, AlertaZabbix, Incidencia, AsignacionIncidencia
from django.utils import timezone
from datetime import datetime

@login_required
def acceso_denegado(request):
    return render(request, "incidencias/403.html", status=403)

def pagina_no_encontrada(request, ruta_invalida=None):
    """
    Vista personalizada para rutas no encontradas.
    """

    context = {
        "ruta_invalida": ruta_invalida,
    }

    return render(request, "incidencias/404.html", context, status=404)


def login_view(request):
    """
    Vista para iniciar sesión en el sistema.
    Corresponde al PBI-001: Iniciar sesión.
    """

    if request.user.is_authenticated:
        return redirect("incidencias:dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        usuario_existente = User.objects.filter(username=username).first()

        if usuario_existente and not usuario_existente.is_active:
            messages.error(
                request,
                "El usuario se encuentra inactivo. Comuníquese con el administrador del sistema."
            )
            return render(request, "incidencias/login.html")

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            return redirect("incidencias:dashboard")
        else:
            messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "incidencias/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("incidencias:login")


@login_required
def dashboard(request):
    from .models import Nodo, ComponenteRed, Incidencia, AlertaZabbix, EstadoIncidencia

    total_nodos = Nodo.objects.count()
    total_componentes = ComponenteRed.objects.count()
    alertas_zabbix = AlertaZabbix.objects.count()

    incidencias_abiertas = Incidencia.objects.exclude(
        estado__in=[
            EstadoIncidencia.CERRADA,
            EstadoIncidencia.CANCELADA,
        ]
    ).count()

    context = {
        "total_nodos": total_nodos,
        "total_componentes": total_componentes,
        "incidencias_abiertas": incidencias_abiertas,
        "alertas_zabbix": alertas_zabbix,
    }

    return render(request, "incidencias/dashboard/dashboard.html", context)

@login_required
def incidencias_page(request):
    """
    Módulo de gestión de incidencias.
    """

    return render(
        request,
        "incidencias/incidencias/lista.html",
        {
            "titulo": "Gestión de Incidencias",
            "subtitulo": (
                "Registro, seguimiento, atención y cierre "
                "de incidencias operativas."
            ),
            "pbi": "EP04 - Gestión de incidencias",
        }
    )


@login_required
def asignaciones_page(request):
    """
    Módulo de asignaciones de incidencias.
    """

    return render(
        request,
        "incidencias/asignaciones/lista.html",
        {
            "titulo": "Asignaciones",
            "subtitulo": (
                "Asignación y reasignación de incidencias "
                "al personal técnico."
            ),
            "pbi": "EP05 - Gestión de atención de incidencias",
        }
    )

def es_administrador(user):
    """
    Verifica si el usuario tiene permisos de administración del sistema.
    Permite acceso a:
    - Superusuarios de Django.
    - Usuarios con perfil ADMINISTRADOR.
    """

    if not user.is_authenticated:
        return False

    # Superusuario de Django: acceso total
    if user.is_superuser:
        return True

    perfil = getattr(user, "perfil_incidencias", None)

    if not perfil:
        return False

    return perfil.rol == "ADMINISTRADOR"

@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")

def usuarios_lista(request):
    """
    Lista de usuarios del sistema.
    PBI-007 y PBI-008.
    """

    query = request.GET.get("q", "")

    usuarios = User.objects.select_related("perfil_incidencias").all().order_by("username")

    if query:
        usuarios = usuarios.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(perfil_incidencias__rol__icontains=query) |
            Q(perfil_incidencias__cargo__icontains=query) |
            Q(perfil_incidencias__area__icontains=query)
        )

    context = {
        "usuarios": usuarios,
        "query": query,
    }

    return render(request, "incidencias/usuarios/lista.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def usuario_crear(request):
    """
    Registro de usuarios.
    PBI-003 y PBI-006.
    """

    from .forms import UsuarioForm

    if request.method == "POST":
        form = UsuarioForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Usuario registrado correctamente.")
            return redirect("incidencias:usuarios_lista")
    else:
        form = UsuarioForm()

    context = {
        "form": form,
        "titulo": "Registrar usuario",
        "accion": "Crear usuario",
    }

    return render(request, "incidencias/usuarios/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def usuario_editar(request, user_id):
    """
    Modificación de usuarios.
    PBI-004 y PBI-006.
    """

    from django.shortcuts import get_object_or_404
    from .forms import UsuarioForm

    usuario = get_object_or_404(User, id=user_id)

    # IMPORTANTE:
    # En tu modelo la relación no se llama "perfil", sino "perfil_incidencias".
    perfil = getattr(usuario, "perfil_incidencias", None)

    if request.method == "POST":
        form = UsuarioForm(request.POST, instance=usuario, perfil=perfil)

        if form.is_valid():
            form.save()
            messages.success(request, "Usuario actualizado correctamente.")
            return redirect("incidencias:usuarios_lista")
    else:
        form = UsuarioForm(instance=usuario, perfil=perfil)

    context = {
        "form": form,
        "titulo": "Editar usuario",
        "accion": "Guardar cambios",
        "usuario_obj": usuario,
    }

    return render(request, "incidencias/usuarios/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")

def usuario_cambiar_estado(request, user_id):
    """
    Activar o desactivar usuarios.
    PBI-005.
    """

    from django.shortcuts import get_object_or_404

    usuario = get_object_or_404(User, id=user_id)

    if usuario == request.user:
        messages.error(request, "No puedes desactivar tu propio usuario.")
        return redirect("incidencias:usuarios_lista")

    usuario.is_active = not usuario.is_active
    usuario.save()

    # IMPORTANTE:
    # En tu modelo la relación no se llama "perfil", sino "perfil_incidencias".
    perfil = getattr(usuario, "perfil_incidencias", None)

    if perfil:
        perfil.activo = usuario.is_active
        perfil.save()

    if usuario.is_active:
        messages.success(request, "Usuario activado correctamente.")
    else:
        messages.warning(request, "Usuario desactivado correctamente.")

    return redirect("incidencias:usuarios_lista")




@login_required
def alertas_zabbix_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "Alertas Zabbix",
        "subtitulo": "Alertas sincronizadas desde la plataforma de monitoreo Zabbix.",
        "pbi": "EP03 - Integración con Zabbix",
    })




@login_required
def ubicaciones_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "Ubicaciones",
        "subtitulo": "Administración de las ubicaciones donde opera la infraestructura de red.",
        "pbi": "EP02 - Gestión de infraestructura de red",
    })


@login_required
def nodos_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "Nodos",
        "subtitulo": "Administración de nodos principales de la red de Fiber Z Telecom.",
        "pbi": "EP02 - Gestión de infraestructura de red",
    })


@login_required
def componentes_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "Componentes de Red",
        "subtitulo": "Gestión de routers, radios AP, switches, UPS y demás equipos asociados a nodos.",
        "pbi": "EP02 - Gestión de infraestructura de red",
    })


@login_required
def sla_indicadores_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "SLA e Indicadores",
        "subtitulo": "Control de tiempos de registro, asignación, atención, resolución y cumplimiento de SLA.",
        "pbi": "EP08 - Gestión de SLA e indicadores",
    })


@login_required
def reportes_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "Reportes",
        "subtitulo": "Reportes operativos, históricos y estadísticos de incidencias.",
        "pbi": "EP10 - Reportes y estadísticas",
    })


@login_required
def configuracion_page(request):
    return render(request, "incidencias/modulo.html", {
        "titulo": "Configuración",
        "subtitulo": "Parámetros generales, catálogos y opciones administrativas del sistema.",
        "pbi": "EP11 - Administración y configuración del sistema",
    })


def pagina_no_encontrada(request, ruta_invalida=None):
    return render(request, "incidencias/404.html", {
        "ruta_invalida": ruta_invalida,
    }, status=404)

@login_required
def ubicaciones_lista(request):
    """
    Lista de ubicaciones.
    PBI-017 y PBI-021.
    """

    query = request.GET.get("q", "")

    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    if query:
        ubicaciones = ubicaciones.filter(
            Q(nombre__icontains=query) |
            Q(departamento__icontains=query) |
            Q(provincia__icontains=query) |
            Q(distrito__icontains=query) |
            Q(direccion_referencia__icontains=query)
        )

    context = {
        "ubicaciones": ubicaciones,
        "query": query,
    }

    return render(request, "incidencias/ubicaciones/lista.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def ubicacion_crear(request):
    """
    Registrar ubicación.
    PBI-009.
    """

    from .forms import UbicacionForm

    if request.method == "POST":
        form = UbicacionForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Ubicación registrada correctamente.")
            return redirect("incidencias:ubicaciones_lista")
    else:
        form = UbicacionForm()

    context = {
        "form": form,
        "titulo": "Registrar ubicación",
        "accion": "Crear ubicación",
    }

    return render(request, "incidencias/ubicaciones/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def ubicacion_editar(request, ubicacion_id):
    """
    Modificar ubicación.
    PBI-010.
    """

    from .forms import UbicacionForm

    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    if request.method == "POST":
        form = UbicacionForm(request.POST, instance=ubicacion)

        if form.is_valid():
            form.save()
            messages.success(request, "Ubicación actualizada correctamente.")
            return redirect("incidencias:ubicaciones_lista")
    else:
        form = UbicacionForm(instance=ubicacion)

    context = {
        "form": form,
        "titulo": "Editar ubicación",
        "accion": "Guardar cambios",
        "ubicacion": ubicacion,
    }

    return render(request, "incidencias/ubicaciones/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def ubicacion_cambiar_estado(request, ubicacion_id):
    """
    Activar o desactivar ubicación.
    PBI-021.
    """

    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    ubicacion.activo = not ubicacion.activo
    ubicacion.save()

    if ubicacion.activo:
        messages.success(request, "Ubicación activada correctamente.")
    else:
        messages.warning(request, "Ubicación desactivada correctamente.")

    return redirect("incidencias:ubicaciones_lista")

@login_required
def nodos_lista(request):
    """
    Lista de nodos.
    PBI-017, PBI-018 y PBI-021.
    """

    query = request.GET.get("q", "")

    nodos = Nodo.objects.select_related("ubicacion").all().order_by("codigo")

    if query:
        nodos = nodos.filter(
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(ubicacion__nombre__icontains=query) |
            Q(ubicacion__departamento__icontains=query) |
            Q(ubicacion__provincia__icontains=query) |
            Q(ubicacion__distrito__icontains=query) |
            Q(estado__icontains=query) |
            Q(criticidad__icontains=query) |
            Q(direccion_referencia__icontains=query)
        )

    context = {
        "nodos": nodos,
        "query": query,
    }

    return render(request, "incidencias/nodos/lista.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def nodo_crear(request):
    """
    Registrar nodo.
    PBI-011.
    """

    from .forms import NodoForm

    if request.method == "POST":
        form = NodoForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Nodo registrado correctamente.")
            return redirect("incidencias:nodos_lista")
    else:
        form = NodoForm()

    context = {
        "form": form,
        "titulo": "Registrar nodo",
        "accion": "Crear nodo",
    }

    return render(request, "incidencias/nodos/formulario.html", context)


@login_required                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def nodo_editar(request, nodo_id):
    """
    Modificar nodo.
    PBI-012.
    """

    from .forms import NodoForm

    nodo = get_object_or_404(Nodo, id=nodo_id)

    if request.method == "POST":
        form = NodoForm(request.POST, instance=nodo)

        if form.is_valid():
            form.save()
            messages.success(request, "Nodo actualizado correctamente.")
            return redirect("incidencias:nodos_lista")
    else:
        form = NodoForm(instance=nodo)

    context = {
        "form": form,
        "titulo": "Editar nodo",
        "accion": "Guardar cambios",
        "nodo": nodo,
    }

    return render(request, "incidencias/nodos/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def nodo_cambiar_estado(request, nodo_id):
    """
    Activar o desactivar nodo.
    PBI-021.
    """

    nodo = get_object_or_404(Nodo, id=nodo_id)

    nodo.activo = not nodo.activo
    nodo.save()

    if nodo.activo:
        messages.success(request, "Nodo activado correctamente.")
    else:
        messages.warning(request, "Nodo desactivado correctamente.")

    return redirect("incidencias:nodos_lista")


@login_required
def componentes_lista(request):
    """
    Lista de componentes de red.
    PBI-017, PBI-018, PBI-019, PBI-020, PBI-022 y PBI-023.
    """

    query = request.GET.get("q", "")

    componentes = ComponenteRed.objects.select_related(
        "nodo",
        "nodo__ubicacion"
    ).all().order_by("nodo__codigo", "codigo")

    if query:
        componentes = componentes.filter(
            Q(codigo__icontains=query) |
            Q(nombre__icontains=query) |
            Q(nodo__codigo__icontains=query) |
            Q(nodo__nombre__icontains=query) |
            Q(nodo__ubicacion__nombre__icontains=query) |
            Q(tipo__icontains=query) |
            Q(funcion__icontains=query) |
            Q(ip_gestion__icontains=query) |
            Q(mac_address__icontains=query) |
            Q(fabricante__icontains=query) |
            Q(modelo__icontains=query) |
            Q(host_id_zabbix__icontains=query) |
            Q(estado_operativo__icontains=query) |
            Q(criticidad__icontains=query)
        )

    context = {
        "componentes": componentes,
        "query": query,
    }

    return render(request, "incidencias/componentes/lista.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def componente_crear(request):
    """
    Registrar componente de red.
    PBI-013, PBI-015 y PBI-016.
    """

    from .forms import ComponenteRedForm

    if request.method == "POST":
        form = ComponenteRedForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Componente de red registrado correctamente.")
            return redirect("incidencias:componentes_lista")
    else:
        form = ComponenteRedForm()

    context = {
        "form": form,
        "titulo": "Registrar componente de red",
        "accion": "Crear componente",
    }

    return render(request, "incidencias/componentes/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def componente_editar(request, componente_id):
    """
    Modificar componente de red.
    PBI-014, PBI-015 y PBI-016.
    """

    from .forms import ComponenteRedForm

    componente = get_object_or_404(ComponenteRed, id=componente_id)

    if request.method == "POST":
        form = ComponenteRedForm(request.POST, instance=componente)

        if form.is_valid():
            form.save()
            messages.success(request, "Componente de red actualizado correctamente.")
            return redirect("incidencias:componentes_lista")
    else:
        form = ComponenteRedForm(instance=componente)

    context = {
        "form": form,
        "titulo": "Editar componente de red",
        "accion": "Guardar cambios",
        "componente": componente,
    }

    return render(request, "incidencias/componentes/formulario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def componente_cambiar_estado(request, componente_id):
    """
    Activar o desactivar componente de red.
    PBI-021.
    """

    componente = get_object_or_404(ComponenteRed, id=componente_id)

    componente.activo = not componente.activo
    componente.save()

    if componente.activo:
        messages.success(request, "Componente de red activado correctamente.")
    else:
        messages.warning(request, "Componente de red desactivado correctamente.")

    return redirect("incidencias:componentes_lista")

@login_required
def infraestructura_inventario(request):
    """
    Inventario completo de infraestructura.
    PBI-017, PBI-020 y PBI-022.
    """

    query = request.GET.get("q", "")

    ubicaciones = Ubicacion.objects.prefetch_related(
        "nodos__componentes_red"
    ).all().order_by("nombre")

    if query:
        ubicaciones = ubicaciones.filter(
            Q(nombre__icontains=query) |
            Q(departamento__icontains=query) |
            Q(provincia__icontains=query) |
            Q(distrito__icontains=query) |
            Q(nodos__codigo__icontains=query) |
            Q(nodos__nombre__icontains=query) |
            Q(nodos__componentes_red__codigo__icontains=query) |
            Q(nodos__componentes_red__nombre__icontains=query) |
            Q(nodos__componentes_red__ip_gestion__icontains=query) |
            Q(nodos__componentes_red__fabricante__icontains=query) |
            Q(nodos__componentes_red__modelo__icontains=query)
        ).distinct()

    total_ubicaciones = Ubicacion.objects.count()
    total_nodos = Nodo.objects.count()
    total_componentes = ComponenteRed.objects.count()
    componentes_activos = ComponenteRed.objects.filter(activo=True).count()
    componentes_caidos = ComponenteRed.objects.filter(estado_operativo="CAIDO").count()
    componentes_mantenimiento = ComponenteRed.objects.filter(estado_operativo="MANTENIMIENTO").count()

    context = {
        "ubicaciones": ubicaciones,
        "query": query,
        "total_ubicaciones": total_ubicaciones,
        "total_nodos": total_nodos,
        "total_componentes": total_componentes,
        "componentes_activos": componentes_activos,
        "componentes_caidos": componentes_caidos,
        "componentes_mantenimiento": componentes_mantenimiento,
    }

    return render(request, "incidencias/infraestructura/inventario.html", context)


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def configuracion_zabbix_lista(request):
    """
    Lista de configuraciones Zabbix.
    PBI-024.
    """

    configuraciones = ConfiguracionZabbix.objects.all().order_by("nombre")

    return render(request, "incidencias/zabbix/configuracion_lista.html", {
        "configuraciones": configuraciones,
    })


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def configuracion_zabbix_crear(request):
    """
    Registrar configuración Zabbix.
    PBI-024.
    """

    from .forms import ConfiguracionZabbixForm

    if request.method == "POST":
        form = ConfiguracionZabbixForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Configuración Zabbix registrada correctamente.")
            return redirect("incidencias:configuracion_zabbix_lista")
    else:
        form = ConfiguracionZabbixForm()

    return render(request, "incidencias/zabbix/configuracion_formulario.html", {
        "form": form,
        "titulo": "Registrar configuración Zabbix",
        "accion": "Guardar configuración",
    })


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def configuracion_zabbix_editar(request, configuracion_id):
    """
    Editar configuración Zabbix.
    PBI-024.
    """

    from .forms import ConfiguracionZabbixForm

    configuracion = get_object_or_404(ConfiguracionZabbix, id=configuracion_id)

    if request.method == "POST":
        form = ConfiguracionZabbixForm(request.POST, instance=configuracion)

        if form.is_valid():
            form.save()
            messages.success(request, "Configuración Zabbix actualizada correctamente.")
            return redirect("incidencias:configuracion_zabbix_lista")
    else:
        form = ConfiguracionZabbixForm(instance=configuracion)

    return render(request, "incidencias/zabbix/configuracion_formulario.html", {
        "form": form,
        "titulo": "Editar configuración Zabbix",
        "accion": "Guardar cambios",
        "configuracion": configuracion,
    })

@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def configuracion_zabbix_probar(request, configuracion_id):
    """
    Probar conexión con Zabbix.
    PBI-025.
    """

    from .zabbix_api import ZabbixClient, ZabbixAPIError

    configuracion = get_object_or_404(ConfiguracionZabbix, id=configuracion_id)

    try:
        cliente = ZabbixClient(
            url_api=configuracion.url_api,
            usuario=configuracion.usuario,
            password=configuracion.password,
            token_api=configuracion.token_api,
            usar_token=configuracion.usar_token,
        )

        resultado = cliente.probar_conexion()

        configuracion.conexion_exitosa = True
        configuracion.ultima_prueba_conexion = timezone.now()
        configuracion.mensaje_ultima_prueba = resultado["mensaje"]
        configuracion.save()

        messages.success(request, resultado["mensaje"])

    except ZabbixAPIError as error:
        configuracion.conexion_exitosa = False
        configuracion.ultima_prueba_conexion = timezone.now()
        configuracion.mensaje_ultima_prueba = str(error)
        configuracion.save()

        messages.error(request, f"No se pudo conectar con Zabbix: {error}")

    except Exception as error:
        configuracion.conexion_exitosa = False
        configuracion.ultima_prueba_conexion = timezone.now()
        configuracion.mensaje_ultima_prueba = str(error)
        configuracion.save()

        messages.error(request, f"Error inesperado al probar conexión: {error}")

    return redirect("incidencias:configuracion_zabbix_lista")


@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def zabbix_hosts_lista(request):
    """
    Consulta hosts desde Zabbix.
    PBI-026.
    """

    from .zabbix_api import ZabbixClient, ZabbixAPIError

    configuracion = ConfiguracionZabbix.objects.filter(
        activo=True,
        conexion_exitosa=True
    ).first()

    hosts = []
    error = None

    fecha_inicio_log = timezone.now()
    proceso_log = obtener_valor_choice(
        LogIntegracionZabbix,
        "proceso",
        [
            "CONSULTA_ALERTAS",
            "SINCRONIZACION_ZABBIX",
            "SINCRONIZACION",
            "ALERTAS_ZABBIX",
            "IMPORTACION_ALERTAS",
            "HOSTS",
        ]
    )

    estado_exitoso = obtener_valor_choice(
        LogIntegracionZabbix,
        "estado",
        [
            "EXITOSO",
            "EXITO",
            "OK",
            "COMPLETADO",
        ]
    )

    estado_error = obtener_valor_choice(
        LogIntegracionZabbix,
        "estado",
        [
            "ERROR",
            "FALLIDO",
            "FAILED",
        ]
    )
    if not configuracion:
        error = "No existe una configuración Zabbix activa y validada."

        LogIntegracionZabbix.objects.create(
            proceso="SINCRONIZACION_HOSTS",
            estado="ERROR",
            mensaje=error,
            total_errores=1,
            fecha_inicio=fecha_inicio_log,
            fecha_fin=timezone.now()
        )

    else:
        try:
            cliente = ZabbixClient(
                url_api=configuracion.url_api,
                usuario=configuracion.usuario,
                password=configuracion.password,
                token_api=configuracion.token_api,
                usar_token=configuracion.usar_token,
            )

            hosts = cliente.obtener_hosts()

            LogIntegracionZabbix.objects.create(
                proceso="SINCRONIZACION_HOSTS",
                estado="EXITOSO",
                mensaje="Consulta de hosts ejecutada correctamente.",
                total_alertas=0,
                total_procesadas=len(hosts),
                total_errores=0,
                fecha_inicio=fecha_inicio_log,
                fecha_fin=timezone.now(),
                detalle_json={
                    "total_hosts": len(hosts)
                }
            )

        except ZabbixAPIError as e:
            error = str(e)

            LogIntegracionZabbix.objects.create(
                proceso="SINCRONIZACION_HOSTS",
                estado="ERROR",
                mensaje=error,
                total_alertas=0,
                total_procesadas=0,
                total_errores=1,
                fecha_inicio=fecha_inicio_log,
                fecha_fin=timezone.now()
            )

        except Exception as e:
            error = str(e)

            LogIntegracionZabbix.objects.create(
                proceso="SINCRONIZACION_HOSTS",
                estado="ERROR",
                mensaje=error,
                total_alertas=0,
                total_procesadas=0,
                total_errores=1,
                fecha_inicio=fecha_inicio_log,
                fecha_fin=timezone.now()
            )

    return render(request, "incidencias/zabbix/hosts_lista.html", {
        "configuracion": configuracion,
        "hosts": hosts,
        "error": error,
    })

@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def zabbix_alertas_activas(request):
    """
    Consulta alertas/problemas activos desde Zabbix.
    PBI-027.
    """

    from .zabbix_api import ZabbixClient, ZabbixAPIError

    configuracion = ConfiguracionZabbix.objects.filter(
        activo=True,
        conexion_exitosa=True
    ).first()

    problemas = []
    error = None

    fecha_inicio_log = timezone.now()

    if not configuracion:
        error = "No existe una configuración Zabbix activa y validada."

        LogIntegracionZabbix.objects.create(
            proceso="CONSULTA_ALERTAS",
            estado="ERROR",
            mensaje=error,
            total_alertas=0,
            total_procesadas=0,
            total_errores=1,
            fecha_inicio=fecha_inicio_log,
            fecha_fin=timezone.now()
        )

    else:
        try:
            cliente = ZabbixClient(
                url_api=configuracion.url_api,
                usuario=configuracion.usuario,
                password=configuracion.password,
                token_api=configuracion.token_api,
                usar_token=configuracion.usar_token,
            )

            problemas = cliente.obtener_problemas_activos()

            LogIntegracionZabbix.objects.create(
                proceso="CONSULTA_ALERTAS",
                estado="EXITOSO",
                mensaje="Consulta de alertas activas ejecutada correctamente.",
                total_alertas=len(problemas),
                total_procesadas=len(problemas),
                total_errores=0,
                fecha_inicio=fecha_inicio_log,
                fecha_fin=timezone.now(),
                detalle_json={
                    "total_problemas": len(problemas)
                }
            )

        except ZabbixAPIError as e:
            error = str(e)

            LogIntegracionZabbix.objects.create(
                proceso="CONSULTA_ALERTAS",
                estado="ERROR",
                mensaje=error,
                total_alertas=0,
                total_procesadas=0,
                total_errores=1,
                fecha_inicio=fecha_inicio_log,
                fecha_fin=timezone.now()
            )

        except Exception as e:
            error = str(e)

            LogIntegracionZabbix.objects.create(
                proceso="CONSULTA_ALERTAS",
                estado="ERROR",
                mensaje=error,
                total_alertas=0,
                total_procesadas=0,
                total_errores=1,
                fecha_inicio=fecha_inicio_log,
                fecha_fin=timezone.now()
            )

    return render(request, "incidencias/zabbix/alertas_activas.html", {
        "configuracion": configuracion,
        "problemas": problemas,
        "error": error,
    })
@login_required
@user_passes_test(es_administrador, login_url="incidencias:acceso_denegado")
def zabbix_alertas_sincronizar(request):
    """
    Sincroniza alertas activas desde Zabbix hacia la base de datos.
    PBI-028, PBI-029, PBI-030 y PBI-031.
    """

    from .zabbix_api import ZabbixClient, ZabbixAPIError

    if request.method != "POST":
        return redirect("incidencias:zabbix_alertas_activas")

    configuracion = ConfiguracionZabbix.objects.filter(
        activo=True,
        conexion_exitosa=True
    ).first()

    fecha_inicio_log = timezone.now()

    proceso_log = obtener_valor_choice(
        LogIntegracionZabbix,
        "proceso",
        [
            "CONSULTA_ALERTAS",
            "SINCRONIZACION_ZABBIX",
            "SINCRONIZACION",
            "ALERTAS_ZABBIX",
            "IMPORTACION_ALERTAS",
            "HOSTS",
        ]
    )

    estado_exitoso = obtener_valor_choice(
        LogIntegracionZabbix,
        "estado",
        [
            "EXITOSO",
            "EXITO",
            "OK",
            "COMPLETADO",
        ]
    )

    estado_error = obtener_valor_choice(
        LogIntegracionZabbix,
        "estado",
        [
            "ERROR",
            "FALLIDO",
            "FAILED",
        ]
    )

    total_alertas = 0
    total_creadas = 0
    total_duplicadas = 0
    total_sin_componente = 0
    total_errores = 0

    if not configuracion:
        mensaje = "No existe una configuración Zabbix activa y validada."

        LogIntegracionZabbix.objects.create(
            proceso=proceso_log,
            estado=estado_error,
            mensaje=mensaje,
            total_alertas=0,
            total_procesadas=0,
            total_errores=1,
            fecha_inicio=fecha_inicio_log,
            fecha_fin=timezone.now()
        )

        messages.error(request, mensaje)
        return redirect("incidencias:zabbix_alertas_activas")

    try:
        cliente = ZabbixClient(
            url_api=configuracion.url_api,
            usuario=configuracion.usuario,
            password=configuracion.password,
            token_api=configuracion.token_api,
            usar_token=configuracion.usar_token,
        )

        problemas = cliente.obtener_problemas_activos()
        total_alertas = len(problemas)

        for problema in problemas:
            try:
                event_id = problema.get("eventid")
                trigger_id = problema.get("objectid")
                nombre_alerta = problema.get("name", "Alerta Zabbix")
                severidad_zabbix = str(problema.get("severity", "0"))
                acknowledged = str(problema.get("acknowledged", "0")) == "1"
                clock = problema.get("clock")
                hosts = problema.get("hosts", [])
                tags = problema.get("tags", [])

                if not event_id:
                    total_errores += 1
                    continue

                host_id = None

                if hosts:
                    host_id = hosts[0].get("hostid")

                if not host_id:
                    total_sin_componente += 1
                    continue

                componente = ComponenteRed.objects.filter(
                    host_id_zabbix=host_id,
                    activo=True
                ).first()

                if not componente:
                    total_sin_componente += 1
                    continue

                if AlertaZabbix.objects.filter(event_id=event_id).exists():
                    total_duplicadas += 1
                    continue

                if clock:
                    fecha_evento = datetime.fromtimestamp(
                        int(clock),
                        tz=timezone.get_current_timezone()
                    )
                else:
                    fecha_evento = timezone.now()

                severidad = obtener_valor_choice(
                    AlertaZabbix,
                    "severidad",
                    {
                        "0": [
                            "NO_CLASIFICADA",
                            "NOT_CLASSIFIED",
                            "INFORMACION",
                            "INFORMATION",
                            "INFO",
                            "BAJA",
                        ],
                        "1": [
                            "INFORMACION",
                            "INFORMATION",
                            "INFO",
                            "BAJA",
                        ],
                        "2": [
                            "ADVERTENCIA",
                            "WARNING",
                            "MEDIA",
                        ],
                        "3": [
                            "PROMEDIO",
                            "AVERAGE",
                            "MEDIA",
                        ],
                        "4": [
                            "ALTA",
                            "HIGH",
                        ],
                        "5": [
                            "DESASTRE",
                            "DISASTER",
                            "CRITICA",
                            "CRITICAL",
                        ],
                    }.get(severidad_zabbix, ["NO_CLASIFICADA"])
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
                    ]
                )

                AlertaZabbix.objects.create(
                    componente_red=componente,
                    event_id=event_id,
                    trigger_id=trigger_id,
                    problem_id=event_id,
                    host_id=host_id,
                    nombre_alerta=nombre_alerta,
                    descripcion=nombre_alerta,
                    severidad=severidad,
                    estado_zabbix=estado_zabbix,
                    fecha_evento=fecha_evento,
                    acknowledged=acknowledged,
                    procesada=False,
                    datos_json=problema,
                    tags_json=tags,
                )

                total_creadas += 1

            except Exception:
                total_errores += 1

        mensaje = (
            f"Sincronización finalizada. "
            f"Alertas consultadas: {total_alertas}. "
            f"Creadas: {total_creadas}. "
            f"Duplicadas: {total_duplicadas}. "
            f"Sin componente asociado: {total_sin_componente}. "
            f"Errores: {total_errores}."
        )

        estado_log = estado_exitoso

        if total_errores > 0:
            estado_log = estado_error

        LogIntegracionZabbix.objects.create(
            proceso=proceso_log,
            estado=estado_log,
            mensaje=mensaje,
            total_alertas=total_alertas,
            total_procesadas=total_creadas,
            total_errores=total_errores,
            fecha_inicio=fecha_inicio_log,
            fecha_fin=timezone.now(),
            detalle_json={
                "total_alertas": total_alertas,
                "total_creadas": total_creadas,
                "total_duplicadas": total_duplicadas,
                "total_sin_componente": total_sin_componente,
                "total_errores": total_errores,
            }
        )

        if total_creadas > 0:
            messages.success(request, mensaje)
        else:
            messages.warning(request, mensaje)

    except ZabbixAPIError as error:
        mensaje = f"Error al consultar Zabbix: {error}"

        LogIntegracionZabbix.objects.create(
            proceso=proceso_log,
            estado=estado_error,
            mensaje=mensaje,
            total_alertas=0,
            total_procesadas=0,
            total_errores=1,
            fecha_inicio=fecha_inicio_log,
            fecha_fin=timezone.now()
        )

        messages.error(request, mensaje)

    except Exception as error:
        mensaje = f"Error inesperado en sincronización: {error}"

        LogIntegracionZabbix.objects.create(
            proceso=proceso_log,
            estado=estado_error,
            mensaje=mensaje,
            total_alertas=0,
            total_procesadas=0,
            total_errores=1,
            fecha_inicio=fecha_inicio_log,
            fecha_fin=timezone.now()
        )

        messages.error(request, mensaje)

    return redirect("incidencias:zabbix_alertas_activas")


def obtener_valor_choice(modelo, campo, preferidos):
    """
    Devuelve un valor válido para un campo con choices.
    Sirve para evitar errores si los valores del modelo tienen nombres distintos.
    """

    field = modelo._meta.get_field(campo)
    choices = getattr(field, "choices", None)

    if not choices:
        return preferidos[0]

    valores_validos = [valor for valor, etiqueta in choices]

    for preferido in preferidos:
        if preferido in valores_validos:
            return preferido

    return valores_validos[0]

@login_required
def alertas_sistema_lista(request):
    """
    Lista alertas Zabbix sincronizadas y almacenadas en la base de datos.
    Punto de partida para evaluar y crear incidencias.
    """

    query = request.GET.get("q", "")

    alertas = AlertaZabbix.objects.select_related(
        "componente_red",
        "componente_red__nodo",
    ).all().order_by("-fecha_evento")

    if query:
        alertas = alertas.filter(
            Q(event_id__icontains=query) |
            Q(trigger_id__icontains=query) |
            Q(host_id__icontains=query) |
            Q(nombre_alerta__icontains=query) |
            Q(componente_red__codigo__icontains=query) |
            Q(componente_red__nombre__icontains=query) |
            Q(componente_red__nodo__codigo__icontains=query) |
            Q(componente_red__nodo__nombre__icontains=query)
        ).distinct()

    total_alertas = alertas.count()
    total_pendientes = alertas.filter(procesada=False).count()
    total_procesadas = alertas.filter(procesada=True).count()

    context = {
        "alertas": alertas,
        "query": query,
        "total_alertas": total_alertas,
        "total_pendientes": total_pendientes,
        "total_procesadas": total_procesadas,
    }

    return render(
        request,
        "incidencias/alertas/lista.html",
        context
    )