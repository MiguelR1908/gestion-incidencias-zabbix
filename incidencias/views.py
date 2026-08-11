from datetime import datetime
import csv
from django.http import HttpResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.contrib.auth.decorators import (
    login_required,
    permission_required,
    user_passes_test,
)
from django.db import transaction
from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import (
    HistorialIncidencia,
    AccionHistorial,
    AlertaZabbix,
    AsignacionIncidencia,
    ComentarioIncidencia,
    ComponenteRed,
    ConfiguracionZabbix,
    EstadoIncidencia,
    Incidencia,
    LogIntegracionZabbix,
    Nodo,
    TipoComentario,
    Ubicacion,
)
from .services.evaluacion_alertas import evaluar_alerta_para_incidencia
from .services.sincronizacion_alertas import sincronizar_alertas_zabbix
from .services.sincronizacion_hosts import sincronizar_hosts_zabbix
from .forms import AsignacionIncidenciaForm, RegistroAvanceIncidenciaForm



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
    Lista, busca y filtra las incidencias.

    Las tarjetas superiores muestran cantidades generales.
    La tabla muestra únicamente el resultado filtrado.
    """

    # ==========================================================
    # CONSULTA GENERAL
    # ==========================================================

    base_incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "alerta_zabbix",
            "registrado_por",
            "tecnico_asignado",
        )
        .order_by("-fecha_deteccion")
    )

    # ==========================================================
    # PARÁMETROS DE FILTRO
    # ==========================================================

    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    severidad = request.GET.get("severidad", "").strip()
    nodo_id = request.GET.get("nodo", "").strip()

    # La tabla comienza con todas las incidencias.
    incidencias = base_incidencias

    # ==========================================================
    # APLICAR FILTROS
    # ==========================================================

    if query:
        incidencias = incidencias.filter(
            Q(codigo__icontains=query)
            | Q(titulo__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(nodo_afectado__codigo__icontains=query)
            | Q(nodo_afectado__nombre__icontains=query)
            | Q(componente_principal__codigo__icontains=query)
            | Q(componente_principal__nombre__icontains=query)
            | Q(tecnico_asignado__username__icontains=query)
            | Q(registrado_por__username__icontains=query)
        )

    if estado:
        incidencias = incidencias.filter(
            estado=estado,
        )

    if severidad:
        incidencias = incidencias.filter(
            severidad=severidad,
        )

    if nodo_id:
        incidencias = incidencias.filter(
            nodo_afectado_id=nodo_id,
        )

    # ==========================================================
    # NODOS DISPONIBLES PARA EL SELECT
    # ==========================================================

    nodos = (
        Nodo.objects
        .filter(activo=True)
        .order_by(
            "codigo",
            "nombre",
        )
    )

    # ==========================================================
    # CANTIDADES GENERALES
    # ==========================================================

    total_general = base_incidencias.count()

    incidencias_detectadas = base_incidencias.filter(
        estado="DETECTADA",
    ).count()

    incidencias_en_proceso = base_incidencias.filter(
        estado="EN_PROCESO",
    ).count()

    incidencias_altas = base_incidencias.filter(
        severidad__in=[
            "ALTA",
            "CRITICA",
        ],
    ).count()

    incidencias_cerradas = base_incidencias.filter(
        estado="CERRADA",
    ).count()

    # ==========================================================
    # CONTEXTO
    # ==========================================================

    context = {
        # Listado filtrado
        "incidencias": incidencias,
        "total_incidencias": incidencias.count(),

        # Tarjetas generales
        "total_general": total_general,
        "incidencias_detectadas": incidencias_detectadas,
        "incidencias_en_proceso": incidencias_en_proceso,
        "incidencias_altas": incidencias_altas,
        "incidencias_cerradas": incidencias_cerradas,

        # Filtro de nodos
        "nodos": nodos,

        # Mantener valores seleccionados
        "query": query,
        "estado_seleccionado": estado,
        "severidad_seleccionada": severidad,
        "nodo_seleccionado": nodo_id,
    }

    return render(
        request,
        "incidencias/incidencias/lista.html",
        context,
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
            for problema in problemas:
                clock = problema.get("clock")

                if clock:
                    fecha_evento = datetime.fromtimestamp(
                        int(clock),
                        tz=timezone.get_current_timezone(),
                    )

                    problema["fecha_evento_local"] = fecha_evento

                    segundos_activa = max(
                        int((timezone.now() - fecha_evento).total_seconds()),
                        0,
                    )

                    dias, resto = divmod(segundos_activa, 86400)
                    horas, resto = divmod(resto, 3600)
                    minutos, segundos = divmod(resto, 60)

                    partes = []

                    if dias:
                        partes.append(f"{dias} d")

                    if horas or dias:
                        partes.append(f"{horas} h")

                    partes.append(f"{minutos} min")

                    problema["duracion_texto"] = " ".join(partes)

                else:
                    problema["fecha_evento_local"] = None
                    problema["duracion_texto"] = "-"

                hosts = problema.get("hosts") or []
                host_id = None

                if hosts:
                    host_id = str(
                        hosts[0].get("hostid") or ""
                    ).strip()

                problema["host_id_local"] = host_id

                componente = None
                incidencia = None

                if host_id:
                    componente = (
                        ComponenteRed.objects
                        .select_related("nodo")
                        .filter(
                            host_id_zabbix=host_id,
                        )
                        .first()
                    )

                if componente:
                    problema["componente_codigo"] = componente.codigo
                    problema["componente_nombre"] = componente.nombre
                    problema["nodo_codigo"] = componente.nodo.codigo
                    problema["ip_gestion"] = componente.ip_gestion

                    alerta_local = (
                        AlertaZabbix.objects
                        .filter(
                            event_id=str(
                                problema.get("eventid") or ""
                            )
                        )
                        .select_related("incidencia")
                        .first()
                    )

                    if alerta_local:
                        incidencia = getattr(
                            alerta_local,
                            "incidencia",
                            None,
                        )

                if incidencia:
                    problema["incidencia_codigo"] = incidencia.codigo
                    problema["incidencia_estado"] = (
                        incidencia.get_estado_display()
                    )
                else:
                    problema["incidencia_codigo"] = None
                    problema["incidencia_estado"] = None

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
@user_passes_test(
    es_administrador,
    login_url="incidencias:acceso_denegado",
)
@require_POST
def zabbix_alertas_sincronizar(request):
    """
    Ejecuta manualmente la sincronización de alertas
    desde la interfaz web.
    """

    configuracion = (
        ConfiguracionZabbix.objects
        .filter(
            activo=True,
            conexion_exitosa=True,
        )
        .order_by("id")
        .first()
    )

    if configuracion is None:
        messages.error(
            request,
            (
                "No existe una configuración Zabbix "
                "activa y con conexión exitosa."
            ),
        )

        return redirect(
            "incidencias:zabbix_alertas_activas"
        )

    try:
        resultado = sincronizar_alertas_zabbix(
            configuracion=configuracion,
            usuario=request.user,
        )

        if resultado.get("ok"):
            messages.success(
                request,
                resultado["mensaje"],
            )
        else:
            messages.warning(
                request,
                resultado["mensaje"],
            )

    except Exception as exc:
        messages.error(
            request,
            f"No se pudieron sincronizar las alertas: {exc}",
        )

    return redirect(
        "incidencias:zabbix_alertas_activas"
    )


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


@login_required
@permission_required(
    "incidencias.change_componentered",
    raise_exception=True,
)
@require_POST
def zabbix_hosts_sincronizar(request):
    """
    Sincroniza los hosts de Zabbix con el inventario local.
    """

    configuracion = (
        ConfiguracionZabbix.objects
        .filter(
            activo=True,
            conexion_exitosa=True,
        )
        .order_by("id")
        .first()
    )

    if configuracion is None:
        messages.error(
            request,
            (
                "No existe una configuración Zabbix activa "
                "y con conexión exitosa."
            ),
        )

        return redirect(
            "incidencias:configuracion_zabbix_lista"
        )

    try:
        resultado = sincronizar_hosts_zabbix(
            configuracion=configuracion,
            usuario=request.user,
        )

        if resultado["errores"]:
            messages.warning(
                request,
                (
                    "La sincronización terminó parcialmente. "
                    f"Consultados: {resultado['consultados']}. "
                    f"Creados: {resultado['creados']}. "
                    f"Actualizados: {resultado['actualizados']}. "
                    f"Sin cambios: {resultado['sin_cambios']}. "
                    f"No encontrados: "
                    f"{resultado['no_encontrados']}. "
                    f"Errores: {len(resultado['errores'])}."
                ),
            )

        else:
            messages.success(
                request,
                (
                    "Hosts sincronizados correctamente. "
                    f"Consultados: {resultado['consultados']}. "
                    f"Creados: {resultado['creados']}. "
                    f"Actualizados: {resultado['actualizados']}. "
                    f"Sin cambios: {resultado['sin_cambios']}. "
                    f"No encontrados: "
                    f"{resultado['no_encontrados']}."
                ),
            )

    except Exception as exc:
        messages.error(
            request,
            f"No se pudieron sincronizar los hosts: {exc}",
        )

    return redirect(
        "incidencias:zabbix_hosts_lista"
    )

@login_required
@require_POST
def incidencias_sincronizar(request):
    """
    Ejecuta manualmente la sincronización con Zabbix desde
    la pantalla de gestión de incidencias.

    La función:
    1. Consulta Zabbix.
    2. Guarda o actualiza alertas.
    3. Evalúa severidad y duración.
    4. Genera incidencias cuando corresponde.
    5. Regresa al listado conservando los filtros.
    """

    configuracion = (
        ConfiguracionZabbix.objects
        .filter(
            activo=True,
            conexion_exitosa=True,
        )
        .order_by("id")
        .first()
    )

    if configuracion is None:
        messages.error(
            request,
            (
                "No existe una configuración Zabbix activa "
                "y con conexión exitosa."
            ),
        )

        return redirect("incidencias:incidencias")

    try:
        resultado = sincronizar_alertas_zabbix(
            configuracion=configuracion,
            usuario=request.user,
        )

        mensaje = resultado.get(
            "mensaje",
            "Sincronización ejecutada.",
        )

        if resultado.get("ok"):
            messages.success(
                request,
                mensaje,
            )
        else:
            messages.warning(
                request,
                mensaje,
            )

    except Exception as error:
        messages.error(
            request,
            f"No se pudo sincronizar con Zabbix: {error}",
        )

    # Regresar a la misma página conservando filtros.
    siguiente = request.POST.get("next", "").strip()

    if siguiente and url_has_allowed_host_and_scheme(
        url=siguiente,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(siguiente)

    return redirect("incidencias:incidencias")



@login_required
def incidencia_asignar(request, incidencia_id):
    """
    Asignación inicial.

    Al guardar la asignación, AsignacionIncidencia.save() cambia la
    incidencia inmediatamente a EN_ATENCION y registra el historial.
    """

    incidencia = get_object_or_404(
        Incidencia.objects.select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
        ),
        pk=incidencia_id,
    )

    if incidencia.estado in (
        EstadoIncidencia.CERRADA,
        EstadoIncidencia.CANCELADA,
    ):
        messages.error(
            request,
            "No se puede asignar una incidencia cerrada o cancelada.",
        )
        return redirect("incidencias:incidencias")

    if incidencia.tecnico_asignado_id:
        messages.warning(
            request,
            (
                f"La incidencia {incidencia.codigo} ya tiene un técnico. "
                "Use Escalamiento / Reasignación desde el detalle."
            ),
        )
        return redirect(
            "incidencias:incidencia_detalle",
            incidencia_id=incidencia.id,
        )

    if request.method == "POST":
        asignacion_temporal = AsignacionIncidencia(
            incidencia=incidencia,
        )

        form = AsignacionIncidenciaForm(
            request.POST,
            instance=asignacion_temporal,
        )

        if form.is_valid():
            try:
                with transaction.atomic():
                    incidencia_bloqueada = (
                        Incidencia.objects
                        .select_for_update()
                        .get(pk=incidencia.pk)
                    )

                    if incidencia_bloqueada.tecnico_asignado_id:
                        messages.warning(
                            request,
                            "La incidencia ya fue asignada por otro usuario.",
                        )
                        return redirect(
                            "incidencias:incidencia_detalle",
                            incidencia_id=incidencia_bloqueada.id,
                        )

                    asignacion = form.save(commit=False)
                    asignacion.incidencia = incidencia_bloqueada
                    asignacion.asignado_por = request.user
                    asignacion.creado_por = request.user
                    asignacion.actualizado_por = request.user
                    asignacion.activo = True
                    asignacion.save()

                nombre_tecnico = (
                    asignacion.tecnico.get_full_name()
                    or asignacion.tecnico.username
                )

                messages.success(
                    request,
                    (
                        f"{incidencia.codigo} fue asignada a "
                        f"{nombre_tecnico} y quedó en atención."
                    ),
                )

                return redirect(
                    "incidencias:incidencia_detalle",
                    incidencia_id=incidencia.id,
                )

            except ValidationError as error:
                form.add_error(None, error)

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo asignar la incidencia: {error}",
                )
    else:
        form = AsignacionIncidenciaForm(
            instance=AsignacionIncidencia(
                incidencia=incidencia,
            )
        )

    return render(
        request,
        "incidencias/incidencias/asignar.html",
        {
            "incidencia": incidencia,
            "form": form,
        },
    )


@login_required
def incidencia_detalle(request, incidencia_id):
    """
    Detalle operativo de la incidencia.

    - Seguimiento / Diagnóstico / Observación: agregan bitácora.
    - Solución: registra la solución, pero la incidencia sigue EN_ATENCION.
    - Escalamiento: crea una nueva AsignacionIncidencia, cambia el técnico
      actual y mantiene EN_ATENCION.
    - Cierre: pasa directamente a CERRADA y deja la bitácora en solo lectura.
    """

    incidencia = get_object_or_404(
        Incidencia.objects.select_related(
            "nodo_afectado",
            "componente_principal",
            "alerta_zabbix",
            "tecnico_asignado",
            "registrado_por",
            "categoria",
            "sla",
        ),
        pk=incidencia_id,
    )

    historial = (
        incidencia.historial
        .select_related("usuario")
        .order_by("-fecha_evento")
    )

    if request.method == "POST":
        if incidencia.estado == EstadoIncidencia.DETECTADA:
            messages.warning(
                request,
                "Primero debe asignar un técnico a la incidencia.",
            )
            return redirect(
                "incidencias:incidencia_detalle",
                incidencia_id=incidencia.id,
            )

        if incidencia.estado in [
            EstadoIncidencia.CERRADA,
            EstadoIncidencia.CANCELADA,
        ]:
            messages.warning(
                request,
                "La incidencia está finalizada y no admite nuevos registros.",
            )
            return redirect(
                "incidencias:incidencia_detalle",
                incidencia_id=incidencia.id,
            )

        form_avance = RegistroAvanceIncidenciaForm(
            request.POST,
            incidencia=incidencia,
        )

        if form_avance.is_valid():
            tipo = form_avance.cleaned_data["tipo_registro"]
            detalle = (
                form_avance.cleaned_data.get("detalle")
                or ""
            ).strip()

            try:
                with transaction.atomic():
                    incidencia_bloqueada = (
                        Incidencia.objects
                        .select_for_update()
                        .select_related("tecnico_asignado")
                        .get(pk=incidencia.pk)
                    )

                    # --------------------------------------------------
                    # ESCALAMIENTO / REASIGNACIÓN
                    # --------------------------------------------------
                    if tipo == TipoComentario.ESCALAMIENTO:
                        nuevo_tecnico = form_avance.cleaned_data["nuevo_tecnico"]

                        AsignacionIncidencia.objects.create(
                            incidencia=incidencia_bloqueada,
                            tecnico=nuevo_tecnico,
                            asignado_por=request.user,
                            comentario=detalle,
                            creado_por=request.user,
                            actualizado_por=request.user,
                            activo=True,
                        )

                        messages.success(
                            request,
                            (
                                "La incidencia fue escalada y el técnico "
                                "responsable fue actualizado."
                            ),
                        )

                    # --------------------------------------------------
                    # CIERRE DIRECTO
                    # --------------------------------------------------
                    elif tipo == RegistroAvanceIncidenciaForm.TIPO_CIERRE:
                        estados_cerrables = {
                            EstadoIncidencia.ASIGNADA,
                            EstadoIncidencia.EN_ATENCION,
                            EstadoIncidencia.RESUELTA,
                        }

                        if incidencia_bloqueada.estado not in estados_cerrables:
                            messages.error(
                                request,
                                "La incidencia no se encuentra en un estado cerrable.",
                            )
                            return redirect(
                                "incidencias:incidencia_detalle",
                                incidencia_id=incidencia_bloqueada.id,
                            )

                        estado_anterior = incidencia_bloqueada.estado
                        ahora = timezone.now()

                        # El modelo actual exige fecha_resolucion y solucion
                        # para poder guardar una incidencia CERRADA. No se usa
                        # RESUELTA como paso visible/intermedio.
                        if not incidencia_bloqueada.solucion:
                            incidencia_bloqueada.solucion = detalle

                        if not incidencia_bloqueada.fecha_resolucion:
                            incidencia_bloqueada.fecha_resolucion = ahora

                        incidencia_bloqueada.fecha_cierre = ahora
                        incidencia_bloqueada.estado = EstadoIncidencia.CERRADA
                        incidencia_bloqueada.actualizado_por = request.user
                        incidencia_bloqueada.save()

                        # Al cerrar ya no queda una asignación activa pendiente,
                        # pero se conserva tecnico_asignado para trazabilidad.
                        AsignacionIncidencia.objects.filter(
                            incidencia=incidencia_bloqueada,
                            activo=True,
                        ).update(activo=False)

                        HistorialIncidencia.objects.create(
                            incidencia=incidencia_bloqueada,
                            usuario=request.user,
                            accion=AccionHistorial.CIERRE,
                            estado_anterior=estado_anterior,
                            estado_nuevo=EstadoIncidencia.CERRADA,
                            descripcion=(
                                "Incidencia cerrada. "
                                f"Validación / solución final: {detalle}"
                            ),
                            creado_por=request.user,
                            actualizado_por=request.user,
                        )

                        messages.success(
                            request,
                            "La incidencia fue cerrada correctamente.",
                        )

                    # --------------------------------------------------
                    # SEGUIMIENTO / DIAGNÓSTICO / SOLUCIÓN / OBSERVACIÓN
                    # --------------------------------------------------
                    else:
                        # SOLUCION se conserva también en el campo principal
                        # de Incidencia, pero no cambia el estado.
                        if tipo == TipoComentario.SOLUCION:
                            incidencia_bloqueada.solucion = detalle
                            incidencia_bloqueada.actualizado_por = request.user
                            incidencia_bloqueada.save()

                        ComentarioIncidencia.objects.create(
                            incidencia=incidencia_bloqueada,
                            usuario=request.user,
                            tipo_comentario=tipo,
                            comentario=detalle,
                            creado_por=request.user,
                            actualizado_por=request.user,
                        )

                        messages.success(
                            request,
                            "Avance registrado correctamente.",
                        )

                return redirect(
                    "incidencias:incidencia_detalle",
                    incidencia_id=incidencia.id,
                )

            except ValidationError as error:
                form_avance.add_error(None, error)

            except Exception as error:
                messages.error(
                    request,
                    f"No se pudo registrar el avance: {error}",
                )
    else:
        form_avance = RegistroAvanceIncidenciaForm(
            incidencia=incidencia,
        )

    return render(
        request,
        "incidencias/incidencias/detalle.html",
        {
            "incidencia": incidencia,
            "historial": historial,
            "form_avance": form_avance,
        },
    )


# =============================================================
# RUTAS ANTIGUAS - COMPATIBILIDAD
# =============================================================
# Se conservan para que un urls.py anterior no genere errores.
# La interfaz actual ya no usa estos botones.

@login_required
@require_POST
def incidencia_iniciar_atencion(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, pk=incidencia_id)

    if incidencia.estado == EstadoIncidencia.ASIGNADA:
        estado_anterior = incidencia.estado
        incidencia.estado = EstadoIncidencia.EN_ATENCION
        incidencia.fecha_inicio_atencion = (
            incidencia.fecha_inicio_atencion or timezone.now()
        )
        incidencia.actualizado_por = request.user
        incidencia.save()

        HistorialIncidencia.objects.create(
            incidencia=incidencia,
            usuario=request.user,
            accion=AccionHistorial.ATENCION,
            estado_anterior=estado_anterior,
            estado_nuevo=incidencia.estado,
            descripcion="Se inició la atención de una incidencia antigua asignada.",
            creado_por=request.user,
            actualizado_por=request.user,
        )

    return redirect(
        "incidencias:incidencia_detalle",
        incidencia_id=incidencia.id,
    )


@login_required
def incidencia_resolver(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, pk=incidencia_id)
    messages.info(
        request,
        "Registre la solución desde el selector 'Tipo de registro' del detalle.",
    )
    return redirect(
        "incidencias:incidencia_detalle",
        incidencia_id=incidencia.id,
    )


@login_required
@require_POST
def incidencia_cerrar(request, incidencia_id):
    incidencia = get_object_or_404(Incidencia, pk=incidencia_id)
    messages.info(
        request,
        "Use 'Tipo de registro → Cierre' desde el detalle de la incidencia.",
    )
    return redirect(
        "incidencias:incidencia_detalle",
        incidencia_id=incidencia.id,
    )

@login_required
def reporte_incidencias(request):
    """
    Reporte general y limpio de incidencias.
    Respeta los filtros recibidos desde el listado.
    """

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    severidad = request.GET.get("severidad", "").strip()
    nodo_id = request.GET.get("nodo", "").strip()

    if query:
        incidencias = incidencias.filter(
            Q(codigo__icontains=query)
            | Q(titulo__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(nodo_afectado__codigo__icontains=query)
            | Q(nodo_afectado__nombre__icontains=query)
            | Q(componente_principal__codigo__icontains=query)
            | Q(componente_principal__nombre__icontains=query)
            | Q(tecnico_asignado__username__icontains=query)
        )

    if estado:
        incidencias = incidencias.filter(estado=estado)

    if severidad:
        incidencias = incidencias.filter(severidad=severidad)

    if nodo_id:
        incidencias = incidencias.filter(nodo_afectado_id=nodo_id)

    # ----------------------------------------------------------
    # Resumen ejecutivo
    # ----------------------------------------------------------

    total_incidencias = incidencias.count()

    total_detectadas = incidencias.filter(
        estado=EstadoIncidencia.DETECTADA,
    ).count()

    total_en_atencion = incidencias.filter(
        estado__in=[
            EstadoIncidencia.ASIGNADA,
            EstadoIncidencia.EN_ATENCION,
        ],
    ).count()

    total_cerradas = incidencias.filter(
        estado=EstadoIncidencia.CERRADA,
    ).count()

    total_altas_criticas = incidencias.filter(
        severidad__in=["ALTA", "CRITICA"],
    ).count()

    # ----------------------------------------------------------
    # Indicadores de tiempo
    # ----------------------------------------------------------

    tiempos_asignacion = [
        incidencia.tiempo_asignacion_min
        for incidencia in incidencias
        if incidencia.tiempo_asignacion_min is not None
    ]

    tiempos_cierre = [
        incidencia.tiempo_cierre_min
        for incidencia in incidencias
        if incidencia.tiempo_cierre_min is not None
    ]

    promedio_asignacion_min = (
        round(sum(tiempos_asignacion) / len(tiempos_asignacion), 2)
        if tiempos_asignacion
        else None
    )

    promedio_cierre_min = (
        round(sum(tiempos_cierre) / len(tiempos_cierre), 2)
        if tiempos_cierre
        else None
    )

    # ----------------------------------------------------------
    # SLA de resolución
    # ----------------------------------------------------------

    sla_evaluadas = incidencias.filter(
        cumple_sla_resolucion__isnull=False,
    ).count()

    sla_cumplidas = incidencias.filter(
        cumple_sla_resolucion=True,
    ).count()

    porcentaje_sla = (
        round((sla_cumplidas / sla_evaluadas) * 100, 2)
        if sla_evaluadas
        else None
    )

    # ----------------------------------------------------------
    # Texto de filtros para la cabecera
    # ----------------------------------------------------------

    estado_texto = ""
    if estado:
        estado_texto = dict(EstadoIncidencia.choices).get(
            estado,
            estado,
        )

    severidad_texto = ""
    if severidad:
        severidad_texto = severidad.replace("_", " ").title()

    nodo_texto = ""
    if nodo_id:
        nodo = Nodo.objects.filter(pk=nodo_id).first()
        if nodo:
            nodo_texto = f"{nodo.codigo} - {nodo.nombre}"

    context = {
        "incidencias": incidencias,
        "fecha_generacion": timezone.localtime(),

        "total_incidencias": total_incidencias,
        "total_detectadas": total_detectadas,
        "total_en_atencion": total_en_atencion,
        "total_cerradas": total_cerradas,
        "total_altas_criticas": total_altas_criticas,

        "promedio_asignacion_min": promedio_asignacion_min,
        "promedio_cierre_min": promedio_cierre_min,
        "porcentaje_sla": porcentaje_sla,

        "query": query,
        "estado_texto": estado_texto,
        "severidad_texto": severidad_texto,
        "nodo_texto": nodo_texto,
    }

    return render(
        request,
        "incidencias/reportes/reporte_incidencias.html",
        context,
    )
    """
    Reporte general de incidencias.
    Respeta los filtros enviados desde el listado.
    """

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    severidad = request.GET.get("severidad", "").strip()
    nodo_id = request.GET.get("nodo", "").strip()

    if query:
        incidencias = incidencias.filter(
            Q(codigo__icontains=query)
            | Q(titulo__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(nodo_afectado__codigo__icontains=query)
            | Q(nodo_afectado__nombre__icontains=query)
            | Q(tecnico_asignado__username__icontains=query)
        )

    if estado:
        incidencias = incidencias.filter(
            estado=estado
        )

    if severidad:
        incidencias = incidencias.filter(
            severidad=severidad
        )

    if nodo_id:
        incidencias = incidencias.filter(
            nodo_afectado_id=nodo_id
        )

    context = {
        "incidencias": incidencias,
        "total_incidencias": incidencias.count(),

        "query": query,
        "estado_seleccionado": estado,
        "severidad_seleccionada": severidad,
        "nodo_seleccionado": nodo_id,
    }

    return render(
        request,
        "incidencias/reportes/reporte_incidencias.html",
        context,
    )

@login_required
def exportar_incidencias_csv(request):
    """
    Exporta las incidencias a CSV respetando los filtros
    utilizados en el listado de incidencias.
    """

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    # ==========================================================
    # FILTROS
    # ==========================================================

    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    severidad = request.GET.get("severidad", "").strip()
    nodo_id = request.GET.get("nodo", "").strip()

    if query:
        incidencias = incidencias.filter(
            Q(codigo__icontains=query)
            | Q(titulo__icontains=query)
            | Q(descripcion__icontains=query)
            | Q(nodo_afectado__codigo__icontains=query)
            | Q(nodo_afectado__nombre__icontains=query)
            | Q(componente_principal__codigo__icontains=query)
            | Q(componente_principal__nombre__icontains=query)
            | Q(tecnico_asignado__username__icontains=query)
        )

    if estado:
        incidencias = incidencias.filter(
            estado=estado
        )

    if severidad:
        incidencias = incidencias.filter(
            severidad=severidad
        )

    if nodo_id:
        incidencias = incidencias.filter(
            nodo_afectado_id=nodo_id
        )

    # ==========================================================
    # ARCHIVO
    # ==========================================================

    fecha = timezone.localdate().strftime("%Y-%m-%d")

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="incidencias_{fecha}.csv"'
    )

    # BOM UTF-8 para que Excel muestre correctamente tildes y ñ
    response.write("\ufeff")

    # ; funciona mejor con Excel en configuraciones regionales ES
    writer = csv.writer(
        response,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
    )

    # ==========================================================
    # CABECERAS
    # ==========================================================

    writer.writerow([
        "Código",
        "Título",
        "Estado",
        "Severidad",
        "Prioridad",
        "Origen",
        "Nodo",
        "Nombre nodo",
        "Componente",
        "Técnico asignado",
        "Clientes afectados",
        "Fecha detección",
        "Fecha registro",
        "Fecha asignación",
        "Inicio atención",
        "Fecha cierre",
        "Tiempo asignación (min)",
        "Tiempo inicio atención (min)",
        "Tiempo cierre (min)",
        "Cumple SLA registro",
        "Cumple SLA asignación",
        "Cumple SLA inicio atención",
        "Cumple SLA resolución",
        "Solución",
        "Causa raíz",
        "Observaciones",
    ])

    # ==========================================================
    # DATOS
    # ==========================================================

    for incidencia in incidencias:

        tecnico = ""

        if incidencia.tecnico_asignado:
            tecnico = (
                incidencia.tecnico_asignado.get_full_name()
                or incidencia.tecnico_asignado.username
            )

        componente = ""

        if incidencia.componente_principal:
            componente = (
                incidencia.componente_principal.codigo
            )

        def fecha_excel(valor):
            if not valor:
                return ""

            return timezone.localtime(valor).strftime(
                "%d/%m/%Y %H:%M:%S"
            )

        def sla_texto(valor):
            if valor is True:
                return "Sí"

            if valor is False:
                return "No"

            return "No evaluado"

        writer.writerow([
            incidencia.codigo,
            incidencia.titulo,
            incidencia.get_estado_display(),
            incidencia.get_severidad_display(),
            incidencia.get_prioridad_display(),
            incidencia.get_origen_display(),

            incidencia.nodo_afectado.codigo,
            incidencia.nodo_afectado.nombre,

            componente,
            tecnico,

            incidencia.clientes_afectados_estimados,

            fecha_excel(
                incidencia.fecha_deteccion
            ),

            fecha_excel(
                incidencia.fecha_registro
            ),

            fecha_excel(
                incidencia.fecha_asignacion
            ),

            fecha_excel(
                incidencia.fecha_inicio_atencion
            ),

            fecha_excel(
                incidencia.fecha_cierre
            ),

            incidencia.tiempo_asignacion_min or "",
            incidencia.tiempo_inicio_atencion_min or "",
            incidencia.tiempo_cierre_min or "",

            sla_texto(
                incidencia.cumple_sla_registro
            ),

            sla_texto(
                incidencia.cumple_sla_asignacion
            ),

            sla_texto(
                incidencia.cumple_sla_inicio_atencion
            ),

            sla_texto(
                incidencia.cumple_sla_resolucion
            ),

            incidencia.solucion or "",
            incidencia.causa_raiz or "",
            incidencia.observaciones or "",
        ])

    return response

@login_required
def reporte_incidencia(request, incidencia_id):
    """
    Reporte individual de una incidencia con:
    - información general,
    - tiempos,
    - SLA,
    - Zabbix,
    - historial de asignaciones,
    - solución,
    - bitácora completa.
    """

    incidencia = get_object_or_404(
        Incidencia.objects.select_related(
            "nodo_afectado",
            "componente_principal",
            "alerta_zabbix",
            "tecnico_asignado",
            "registrado_por",
            "categoria",
            "sla",
        ),
        pk=incidencia_id,
    )

    historial = (
        incidencia.historial
        .select_related("usuario")
        .order_by("fecha_evento")
    )

    asignaciones = (
        incidencia.asignaciones
        .select_related(
            "tecnico",
            "asignado_por",
        )
        .order_by("fecha_asignacion")
    )

    context = {
        "incidencia": incidencia,
        "historial": historial,
        "asignaciones": asignaciones,
        "fecha_generacion": timezone.localtime(),
    }

    return render(
        request,
        "incidencias/reportes/reporte_incidencia.html",
        context,
    )