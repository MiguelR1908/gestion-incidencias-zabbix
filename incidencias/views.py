"""
Vistas del módulo de gestión de incidencias integrado con Zabbix.

Versión ordenada y consolidada:
- imports duplicados eliminados;
- página 404 duplicada eliminada;
- permisos uniformizados por rol;
- exportaciones CSV añadidas para recurrencia, SLA/tiempos y técnicos;
- se conservan las vistas legacy para no romper URLs existentes.
"""


import csv
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import (
    login_required,
    permission_required,
    user_passes_test,
)
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import AsignacionIncidenciaForm, RegistroAvanceIncidenciaForm
from .models import (
    AccionHistorial,
    AlertaZabbix,
    AsignacionIncidencia,
    ComentarioIncidencia,
    ComponenteRed,
    ConfiguracionZabbix,
    EstadoIncidencia,
    HistorialIncidencia,
    Incidencia,
    LogIntegracionZabbix,
    MedioNotificacion,
    Nodo,
    NotificacionIncidencia,
    SLAIncidencia,
    TipoComentario,
    Ubicacion,
    calcular_minutos,
)
from .services.notificaciones import crear_notificacion_sistema
from .services.sincronizacion_alertas import sincronizar_alertas_zabbix
from .services.sincronizacion_hosts import sincronizar_hosts_zabbix



# ==========================================================
# CONTROL DE ACCESO POR ROLES
# ==========================================================


def obtener_rol_usuario(user):
    """
    Obtiene el rol del usuario autenticado.
    """

    if not user or not user.is_authenticated:
        return None

    perfil = getattr(
        user,
        "perfil_incidencias",
        None,
    )

    if not perfil:
        return None

    return perfil.rol


def es_administrador(user):
    """
    Administrador funcional del sistema.
    """

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return (
        obtener_rol_usuario(user)
        == "ADMINISTRADOR"
    )


def es_operacion_noc(user):
    """
    Personal que participa en la operación del NOC.
    """

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return obtener_rol_usuario(user) in [
        "ADMINISTRADOR",
        "GESTOR_NOC",
        "SUPERVISOR",
    ]


def puede_atender_incidencias(user):
    """
    Usuarios que pueden consultar/atender incidencias.
    """

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return obtener_rol_usuario(user) in [
        "ADMINISTRADOR",
        "GESTOR_NOC",
        "SUPERVISOR",
        "TECNICO",
    ]


def puede_ver_infraestructura(user):
    """
    Acceso de consulta a infraestructura.
    """

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return obtener_rol_usuario(user) in [
        "ADMINISTRADOR",
        "GESTOR_NOC",
        "SUPERVISOR",
        "TECNICO",
    ]


def puede_ver_reportes(user):
    """
    Acceso a reportes operativos y gerenciales.
    """

    if not user or not user.is_authenticated:
        return False

    if user.is_superuser:
        return True

    return obtener_rol_usuario(user) in [
        "ADMINISTRADOR",
        "GESTOR_NOC",
        "SUPERVISOR",
        "DUENO",
    ]



# ==========================================================
# AUTENTICACIÓN Y PÁGINAS DE ERROR
# ==========================================================


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



# ==========================================================
# DASHBOARD Y FILTROS COMUNES
# ==========================================================


@login_required
def dashboard(request):

    from django.utils import timezone
    from django.db.models import Count, Q

    from .models import (
        Nodo,
        ComponenteRed,
        Incidencia,
        AlertaZabbix,
        EstadoIncidencia,
        Severidad,
        AsignacionIncidencia,
    )


    # ==========================================================
    # ROL DEL USUARIO
    # ==========================================================

    rol_usuario = obtener_rol_usuario(
        request.user
    )

    es_tecnico = (
        rol_usuario == "TECNICO"
        and not request.user.is_superuser
    )


    # ==========================================================
    # QUERYSET BASE DE INCIDENCIAS
    # ==========================================================

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
        )
    )


    # Técnico: dashboard únicamente con sus incidencias
    if es_tecnico:

        incidencias = incidencias.filter(
            Q(tecnico_asignado=request.user)
            | Q(asignaciones__tecnico=request.user)
        ).distinct()


    # ==========================================================
    # INCIDENCIAS ABIERTAS
    # ==========================================================

    incidencias_abiertas_qs = (
        incidencias
        .exclude(
            estado__in=[
                EstadoIncidencia.CERRADA,
                EstadoIncidencia.CANCELADA,
            ]
        )
    )

    incidencias_abiertas = (
        incidencias_abiertas_qs.count()
    )


    # ==========================================================
    # CRÍTICAS ABIERTAS
    # ==========================================================

    incidencias_criticas = (
        incidencias_abiertas_qs
        .filter(
            severidad=Severidad.CRITICA
        )
        .count()
    )


    # ==========================================================
    # SIN ASIGNAR
    # ==========================================================

    incidencias_sin_asignar = (
        incidencias_abiertas_qs
        .filter(
            tecnico_asignado__isnull=True
        )
        .count()
    )


    # ==========================================================
    # EN ATENCIÓN
    # ==========================================================

    incidencias_en_atencion = (
        incidencias_abiertas_qs
        .filter(
            estado=EstadoIncidencia.EN_ATENCION
        )
        .count()
    )


    # ==========================================================
    # SLA INCUMPLIDO
    # ==========================================================

    incidencias_sla_incumplido = (
        incidencias
        .filter(
            Q(cumple_sla_registro=False)
            | Q(cumple_sla_asignacion=False)
            | Q(cumple_sla_inicio_atencion=False)
            | Q(cumple_sla_resolucion=False)
        )
        .distinct()
        .count()
    )


    # ==========================================================
    # CERRADAS HOY
    # ==========================================================

    hoy = timezone.localdate()

    incidencias_cerradas_hoy = (
        incidencias
        .filter(
            estado=EstadoIncidencia.CERRADA,
            fecha_cierre__date=hoy,
        )
        .count()
    )


    # ==========================================================
    # CUMPLIMIENTO SLA
    # ==========================================================

    incidencias_evaluadas_sla = (
        incidencias
        .filter(
            cumple_sla_resolucion__isnull=False
        )
    )

    total_evaluadas_sla = (
        incidencias_evaluadas_sla.count()
    )

    total_cumplen_sla = (
        incidencias_evaluadas_sla
        .filter(
            cumple_sla_resolucion=True
        )
        .count()
    )

    if total_evaluadas_sla:

        cumplimiento_sla = round(
            (
                total_cumplen_sla
                / total_evaluadas_sla
            ) * 100,
            1,
        )

    else:

        cumplimiento_sla = 0


    # ==========================================================
    # INCIDENCIAS PRIORITARIAS
    # ==========================================================

    incidencias_prioritarias = (
        incidencias_abiertas_qs
        .order_by(
            "severidad",
            "fecha_deteccion",
        )[:10]
    )


    # ==========================================================
    # ALERTAS ZABBIX
    # ==========================================================

    alertas_zabbix = (
        AlertaZabbix.objects
        .order_by(
            "-fecha_evento"
        )[:10]
    )


    total_alertas_zabbix = (
        AlertaZabbix.objects.count()
    )


    # ==========================================================
    # CARGA POR TÉCNICO
    # ==========================================================

    if es_tecnico:

        carga_tecnicos = []

    else:

        carga_tecnicos = (
            AsignacionIncidencia.objects
            .filter(
                activo=True
            )
            .values(
                "tecnico__id",
                "tecnico__username",
                "tecnico__first_name",
                "tecnico__last_name",
            )
            .annotate(
                activas=Count(
                    "incidencia",
                    distinct=True,
                )
            )
            .order_by(
                "-activas"
            )[:10]
        )


    # ==========================================================
    # DATOS DE INFRAESTRUCTURA SECUNDARIOS
    # ==========================================================

    total_nodos = Nodo.objects.count()
    total_componentes = (
        ComponenteRed.objects.count()
    )


    # ==========================================================
    # CONTEXTO
    # ==========================================================

    context = {

        "rol_usuario": rol_usuario,
        "es_tecnico": es_tecnico,

        "incidencias_abiertas":
            incidencias_abiertas,

        "incidencias_criticas":
            incidencias_criticas,

        "incidencias_sin_asignar":
            incidencias_sin_asignar,

        "incidencias_en_atencion":
            incidencias_en_atencion,

        "incidencias_sla_incumplido":
            incidencias_sla_incumplido,

        "incidencias_cerradas_hoy":
            incidencias_cerradas_hoy,

        "cumplimiento_sla":
            cumplimiento_sla,

        "total_alertas_zabbix":
            total_alertas_zabbix,

        "incidencias_prioritarias":
            incidencias_prioritarias,

        "alertas_zabbix":
            alertas_zabbix,

        "carga_tecnicos":
            carga_tecnicos,

        "total_nodos":
            total_nodos,

        "total_componentes":
            total_componentes,
    }


    return render(
        request,
        "incidencias/dashboard/dashboard.html",
        context,
    )


def aplicar_filtros_incidencias(request, queryset):
    """
    Aplica los filtros comunes del módulo de incidencias.

    Se utiliza para:
    - listado;
    - reporte PDF;
    - exportación CSV.

    El período se evalúa usando fecha_deteccion.
    """

    query = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "").strip()
    severidad = request.GET.get("severidad", "").strip()
    nodo_id = request.GET.get("nodo", "").strip()

    fecha_desde_texto = request.GET.get(
        "fecha_desde",
        "",
    ).strip()

    fecha_hasta_texto = request.GET.get(
        "fecha_hasta",
        "",
    ).strip()

    # ==========================================================
    # FILTROS GENERALES
    # ==========================================================

    if query:
        queryset = queryset.filter(
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
        queryset = queryset.filter(
            estado=estado,
        )

    if severidad:
        queryset = queryset.filter(
            severidad=severidad,
        )

    if nodo_id:
        queryset = queryset.filter(
            nodo_afectado_id=nodo_id,
        )

    # ==========================================================
    # FILTRO POR PERÍODO
    # ==========================================================

    fecha_desde = parse_date(fecha_desde_texto)
    fecha_hasta = parse_date(fecha_hasta_texto)

    zona_horaria = timezone.get_current_timezone()

    if fecha_desde:

        inicio = timezone.make_aware(
            datetime.combine(
                fecha_desde,
                time.min,
            ),
            zona_horaria,
        )

        queryset = queryset.filter(
            fecha_deteccion__gte=inicio,
        )

    if fecha_hasta:

        # Usamos el inicio del día siguiente como límite
        # exclusivo. Así se incluye TODO el día seleccionado.
        dia_siguiente = fecha_hasta + timedelta(days=1)

        fin_exclusivo = timezone.make_aware(
            datetime.combine(
                dia_siguiente,
                time.min,
            ),
            zona_horaria,
        )

        queryset = queryset.filter(
            fecha_deteccion__lt=fin_exclusivo,
        )

    return queryset, {
        "query": query,
        "estado_seleccionado": estado,
        "severidad_seleccionada": severidad,
        "nodo_seleccionado": nodo_id,
        "fecha_desde": fecha_desde_texto,
        "fecha_hasta": fecha_hasta_texto,
    }



# ==========================================================
# GESTIÓN DE USUARIOS
# ==========================================================


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



# ==========================================================
# INFRAESTRUCTURA
# ==========================================================


@login_required
@user_passes_test(
    puede_ver_infraestructura,
    login_url="incidencias:acceso_denegado",
)
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
@user_passes_test(
    puede_ver_infraestructura,
    login_url="incidencias:acceso_denegado",
)
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
@user_passes_test(
    puede_ver_infraestructura,
    login_url="incidencias:acceso_denegado",
)
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
@user_passes_test(
    puede_ver_infraestructura,
    login_url="incidencias:acceso_denegado",
)
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



# ==========================================================
# INTEGRACIÓN ZABBIX
# ==========================================================


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
@user_passes_test(
    es_operacion_noc,
    login_url="incidencias:acceso_denegado",
)
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
@user_passes_test(
    es_operacion_noc,
    login_url="incidencias:acceso_denegado",
)
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



# ==========================================================
# GESTIÓN OPERATIVA DE INCIDENCIAS
# ==========================================================


@login_required
@user_passes_test(
    puede_atender_incidencias,
    login_url="incidencias:acceso_denegado",
)
def incidencias_page(request):
    """
    Lista, busca y filtra las incidencias.

    Para ADMINISTRADOR, GESTOR_NOC y SUPERVISOR conserva
    exactamente la vista general existente.

    Para TECNICO muestra únicamente:
    - ACTIVAS: incidencias actualmente asignadas al técnico y no finalizadas.
    - HISTORIAL: incidencias que estuvieron asignadas al técnico y que ya
      no forman parte de su bandeja activa.

    Los filtros existentes se aplican después de esta restricción por rol.
    """

    # ==========================================================
    # CONSULTA BASE
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
    # VISTA PERSONAL DEL TÉCNICO
    # ==========================================================

    rol_usuario = obtener_rol_usuario(request.user)
    es_tecnico = rol_usuario == "TECNICO"

    vista_tecnico = "activas"
    total_activas_tecnico = 0
    total_historial_tecnico = 0

    if es_tecnico:

        vista_solicitada = request.GET.get(
            "vista",
            "activas",
        ).strip().lower()

        if vista_solicitada in [
            "activas",
            "historial",
        ]:
            vista_tecnico = vista_solicitada

        # ------------------------------------------------------
        # ACTIVAS
        # Actualmente están bajo responsabilidad del técnico
        # y todavía no están finalizadas.
        # ------------------------------------------------------

        incidencias_activas_tecnico = (
            base_incidencias
            .filter(
                tecnico_asignado=request.user,
            )
            .exclude(
                estado__in=[
                    EstadoIncidencia.CERRADA,
                    EstadoIncidencia.CANCELADA,
                ]
            )
        )

        # ------------------------------------------------------
        # HISTORIAL DE PARTICIPACIÓN
        # La incidencia tuvo en algún momento una asignación
        # hacia este técnico, pero ya no está en su bandeja activa.
        #
        # Incluye:
        # - cerradas/canceladas que atendió;
        # - incidencias reasignadas posteriormente a otra persona.
        # ------------------------------------------------------

        incidencias_historial_tecnico = (
            base_incidencias
            .filter(
                asignaciones__tecnico=request.user,
            )
            .filter(
                Q(
                    estado__in=[
                        EstadoIncidencia.CERRADA,
                        EstadoIncidencia.CANCELADA,
                    ]
                )
                | ~Q(
                    tecnico_asignado=request.user,
                )
            )
            .distinct()
        )

        total_activas_tecnico = (
            incidencias_activas_tecnico.count()
        )

        total_historial_tecnico = (
            incidencias_historial_tecnico.count()
        )

        if vista_tecnico == "historial":
            base_incidencias = incidencias_historial_tecnico
        else:
            base_incidencias = incidencias_activas_tecnico

    # ==========================================================
    # APLICAR FILTROS COMUNES
    # ==========================================================

    incidencias, filtros = aplicar_filtros_incidencias(
        request,
        base_incidencias,
    )

    # ==========================================================
    # NODOS PARA SELECT
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
    # RESUMEN DEL RESULTADO FILTRADO
    # ==========================================================

    total_general = incidencias.count()

    incidencias_detectadas = incidencias.filter(
        estado=EstadoIncidencia.DETECTADA,
    ).count()

    incidencias_en_proceso = incidencias.filter(
        estado__in=[
            EstadoIncidencia.ASIGNADA,
            EstadoIncidencia.EN_ATENCION,
        ],
    ).count()

    incidencias_altas = incidencias.filter(
        severidad__in=[
            "ALTA",
            "CRITICA",
        ],
    ).count()

    incidencias_cerradas = incidencias.filter(
        estado=EstadoIncidencia.CERRADA,
    ).count()

    # ==========================================================
    # CONTEXTO
    # ==========================================================

    context = {
        "incidencias": incidencias,
        "total_incidencias": total_general,

        "total_general": total_general,
        "incidencias_detectadas": incidencias_detectadas,
        "incidencias_en_proceso": incidencias_en_proceso,
        "incidencias_altas": incidencias_altas,
        "incidencias_cerradas": incidencias_cerradas,

        "nodos": nodos,

        # Vista por rol. No altera la lógica de las incidencias.
        "es_tecnico": es_tecnico,
        "vista_tecnico": vista_tecnico,
        "total_activas_tecnico": total_activas_tecnico,
        "total_historial_tecnico": total_historial_tecnico,

        **filtros,
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


@login_required
@user_passes_test(
    es_operacion_noc,
    login_url="incidencias:acceso_denegado",
)
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
                    crear_notificacion_sistema(
                        incidencia=incidencia_bloqueada,
                        usuario_destino=asignacion.tecnico,
                        mensaje=(
                            f"Se te asignó la incidencia "
                            f"{incidencia_bloqueada.codigo}. "
                            f"Severidad: "
                            f"{incidencia_bloqueada.get_severidad_display()}. "
                            f"Nodo: "
                            f"{incidencia_bloqueada.nodo_afectado.codigo}."
                        ),
                        creado_por=request.user,
                    )

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
@user_passes_test(
    puede_atender_incidencias,
    login_url="incidencias:acceso_denegado",
)
def incidencia_detalle(request, incidencia_id):
    """
    Detalle operativo de la incidencia.

    - Seguimiento / Diagnóstico / Observación: agregan bitácora.
    - Solución: registra la solución, pero la incidencia sigue EN_ATENCION.
    - Escalamiento: crea una nueva AsignacionIncidencia, cambia el técnico
      actual y mantiene EN_ATENCION.
    - Cierre: pasa directamente a CERRADA y deja la bitácora en solo lectura.

    Permisos para técnicos:
    - Puede visualizar una incidencia si participó en ella alguna vez.
    - Solo puede modificarla si actualmente es el técnico responsable.
    - Si nunca participó, obtiene 403.
    """

    # ==========================================================
    # OBTENER INCIDENCIA
    # ==========================================================

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


    # ==========================================================
    # PERMISOS POR ROL
    # ==========================================================

    rol_usuario = obtener_rol_usuario(request.user)

    es_tecnico = (
        rol_usuario == "TECNICO"
        and not request.user.is_superuser
    )

    puede_editar = True


    # ----------------------------------------------------------
    # TÉCNICO
    # ----------------------------------------------------------

    if es_tecnico:

        participo = (
            AsignacionIncidencia.objects
            .filter(
                incidencia=incidencia,
                tecnico=request.user,
            )
            .exists()
        )

        # Nunca participó en esta incidencia
        if not participo:
            return render(
                request,
                "incidencias/403.html",
                status=403,
            )


        # Solo puede modificarla si actualmente sigue asignado
        # y la incidencia continúa operativa.
        puede_editar = (
            incidencia.tecnico_asignado_id
            == request.user.id
            and incidencia.estado not in [
                EstadoIncidencia.CERRADA,
                EstadoIncidencia.CANCELADA,
            ]
        )


    # ==========================================================
    # HISTORIAL
    # ==========================================================

    historial = (
        incidencia.historial
        .select_related("usuario")
        .order_by("-fecha_evento")
    )


    # ==========================================================
    # POST
    # ==========================================================

    if request.method == "POST":

        # ------------------------------------------------------
        # SEGURIDAD PARA TÉCNICOS
        # ------------------------------------------------------

        if not puede_editar:
            return render(
                request,
                "incidencias/403.html",
                status=403,
            )


        # ------------------------------------------------------
        # INCIDENCIA AÚN NO ASIGNADA
        # ------------------------------------------------------

        if incidencia.estado == EstadoIncidencia.DETECTADA:

            messages.warning(
                request,
                "Primero debe asignar un técnico a la incidencia.",
            )

            return redirect(
                "incidencias:incidencia_detalle",
                incidencia_id=incidencia.id,
            )


        # ------------------------------------------------------
        # INCIDENCIA FINALIZADA
        # ------------------------------------------------------

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


        # ------------------------------------------------------
        # FORMULARIO
        # ------------------------------------------------------

        form_avance = RegistroAvanceIncidenciaForm(
            request.POST,
            incidencia=incidencia,
        )


        if form_avance.is_valid():

            tipo = form_avance.cleaned_data[
                "tipo_registro"
            ]

            detalle = (
                form_avance.cleaned_data.get(
                    "detalle"
                )
                or ""
            ).strip()


            try:

                with transaction.atomic():

                    incidencia_bloqueada = (
                        Incidencia.objects
                        .select_for_update()
                        .select_related(
                            "tecnico_asignado"
                        )
                        .get(
                            pk=incidencia.pk
                        )
                    )


                    # ==================================================
                    # ESCALAMIENTO / REASIGNACIÓN
                    # ==================================================

                    if tipo == TipoComentario.ESCALAMIENTO:

                        nuevo_tecnico = (
                            form_avance.cleaned_data[
                                "nuevo_tecnico"
                            ]
                        )

                        tecnico_anterior = (
                            incidencia_bloqueada
                            .tecnico_asignado
                        )


                        AsignacionIncidencia.objects.create(
                            incidencia=incidencia_bloqueada,
                            tecnico=nuevo_tecnico,
                            asignado_por=request.user,
                            comentario=detalle,
                            creado_por=request.user,
                            actualizado_por=request.user,
                            activo=True,
                        )


                        # ==============================================
                        # NOTIFICACIÓN AL NUEVO TÉCNICO
                        # ==============================================

                        crear_notificacion_sistema(
                            incidencia=incidencia_bloqueada,
                            usuario_destino=nuevo_tecnico,
                            mensaje=(
                                f"Se te reasignó la incidencia "
                                f"{incidencia_bloqueada.codigo}. "
                                f"Severidad: "
                                f"{incidencia_bloqueada.get_severidad_display()}. "
                                f"Nodo: "
                                f"{incidencia_bloqueada.nodo_afectado.codigo}. "
                                f"Motivo: "
                                f"{detalle or 'Sin observación adicional.'}"
                            ),
                            creado_por=request.user,
                        )


                        # ==============================================
                        # NOTIFICACIÓN AL TÉCNICO ANTERIOR
                        # ==============================================

                        if (
                            tecnico_anterior
                            and tecnico_anterior.id
                            != nuevo_tecnico.id
                        ):

                            nombre_nuevo_tecnico = (
                                nuevo_tecnico.get_full_name()
                                or nuevo_tecnico.username
                            )

                            crear_notificacion_sistema(
                                incidencia=incidencia_bloqueada,
                                usuario_destino=tecnico_anterior,
                                mensaje=(
                                    f"La incidencia "
                                    f"{incidencia_bloqueada.codigo} "
                                    f"fue reasignada a "
                                    f"{nombre_nuevo_tecnico}. "
                                    f"Ya no se encuentra bajo tu responsabilidad. "
                                    f"Motivo: "
                                    f"{detalle or 'Sin observación adicional.'}"
                                ),
                                creado_por=request.user,
                            )


                        messages.success(
                            request,
                            (
                                "La incidencia fue escalada y el técnico "
                                "responsable fue actualizado."
                            ),
                        )


                    # ==================================================
                    # CIERRE DIRECTO
                    # ==================================================

                    elif (
                        tipo
                        == RegistroAvanceIncidenciaForm.TIPO_CIERRE
                    ):

                        estados_cerrables = {
                            EstadoIncidencia.ASIGNADA,
                            EstadoIncidencia.EN_ATENCION,
                            EstadoIncidencia.RESUELTA,
                        }


                        if (
                            incidencia_bloqueada.estado
                            not in estados_cerrables
                        ):

                            messages.error(
                                request,
                                (
                                    "La incidencia no se encuentra "
                                    "en un estado cerrable."
                                ),
                            )

                            return redirect(
                                "incidencias:incidencia_detalle",
                                incidencia_id=incidencia_bloqueada.id,
                            )


                        estado_anterior = (
                            incidencia_bloqueada.estado
                        )

                        ahora = timezone.now()


                        # El modelo exige fecha_resolucion y solucion
                        # antes de guardar una incidencia CERRADA.

                        if not incidencia_bloqueada.solucion:
                            incidencia_bloqueada.solucion = (
                                detalle
                            )


                        if not incidencia_bloqueada.fecha_resolucion:
                            incidencia_bloqueada.fecha_resolucion = (
                                ahora
                            )


                        incidencia_bloqueada.fecha_cierre = (
                            ahora
                        )

                        incidencia_bloqueada.estado = (
                            EstadoIncidencia.CERRADA
                        )

                        incidencia_bloqueada.actualizado_por = (
                            request.user
                        )

                        incidencia_bloqueada.save()


                        # ==============================================
                        # DESACTIVAR ASIGNACIONES
                        # ==============================================

                        AsignacionIncidencia.objects.filter(
                            incidencia=incidencia_bloqueada,
                            activo=True,
                        ).update(
                            activo=False
                        )


                        # ==============================================
                        # HISTORIAL DE CIERRE
                        # ==============================================

                        HistorialIncidencia.objects.create(
                            incidencia=incidencia_bloqueada,
                            usuario=request.user,
                            accion=AccionHistorial.CIERRE,
                            estado_anterior=estado_anterior,
                            estado_nuevo=EstadoIncidencia.CERRADA,
                            descripcion=(
                                "Incidencia cerrada. "
                                f"Validación / solución final: "
                                f"{detalle}"
                            ),
                            creado_por=request.user,
                            actualizado_por=request.user,
                        )


                        # ==============================================
                        # NOTIFICACIÓN DE CIERRE
                        # ==============================================

                        tecnico_cierre = (
                            incidencia_bloqueada
                            .tecnico_asignado
                        )


                        if tecnico_cierre:

                            crear_notificacion_sistema(
                                incidencia=incidencia_bloqueada,
                                usuario_destino=tecnico_cierre,
                                mensaje=(
                                    f"La incidencia "
                                    f"{incidencia_bloqueada.codigo} "
                                    f"fue cerrada correctamente. "
                                    f"Solución final: "
                                    f"{detalle or incidencia_bloqueada.solucion or 'Sin detalle adicional.'}"
                                ),
                                creado_por=request.user,
                            )


                        messages.success(
                            request,
                            "La incidencia fue cerrada correctamente.",
                        )


                    # ==================================================
                    # SEGUIMIENTO / DIAGNÓSTICO /
                    # SOLUCIÓN / OBSERVACIÓN
                    # ==================================================

                    else:

                        # ----------------------------------------------
                        # SOLUCIÓN
                        # ----------------------------------------------

                        if tipo == TipoComentario.SOLUCION:

                            incidencia_bloqueada.solucion = (
                                detalle
                            )

                            incidencia_bloqueada.actualizado_por = (
                                request.user
                            )

                            incidencia_bloqueada.save()


                        # ----------------------------------------------
                        # BITÁCORA
                        # ----------------------------------------------

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


                # ======================================================
                # REDIRECCIÓN DESPUÉS DEL POST
                # ======================================================

                return redirect(
                    "incidencias:incidencia_detalle",
                    incidencia_id=incidencia.id,
                )


            except ValidationError as error:

                form_avance.add_error(
                    None,
                    error,
                )


            except Exception as error:

                messages.error(
                    request,
                    (
                        "No se pudo registrar el avance: "
                        f"{error}"
                    ),
                )


    # ==========================================================
    # GET
    # ==========================================================

    else:

        form_avance = RegistroAvanceIncidenciaForm(
            incidencia=incidencia,
        )


    # ==========================================================
    # TEMPLATE
    # ==========================================================

    return render(
        request,
        "incidencias/incidencias/detalle.html",
        {
            "incidencia": incidencia,
            "historial": historial,
            "form_avance": form_avance,

            # Permisos para el template
            "es_tecnico": es_tecnico,
            "puede_editar": puede_editar,
        },
    )


@login_required
@user_passes_test(
    puede_atender_incidencias,
    login_url="incidencias:acceso_denegado",
)
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
@user_passes_test(
    puede_atender_incidencias,
    login_url="incidencias:acceso_denegado",
)
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
@user_passes_test(
    puede_atender_incidencias,
    login_url="incidencias:acceso_denegado",
)
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



# ==========================================================
# NOTIFICACIONES
# ==========================================================


@login_required
def notificaciones_lista(request):

    perfil = getattr(
        request.user,
        "perfil_incidencias",
        None,
    )

    es_noc = (
        request.user.is_superuser
        or (
            perfil
            and perfil.rol in [
                "ADMINISTRADOR",
                "GESTOR_NOC",
                "SUPERVISOR",
            ]
        )
    )

    notificaciones = (
        NotificacionIncidencia.objects
        .filter(
            medio=MedioNotificacion.SISTEMA,
        )
    )

    # ==========================================================
    # FILTRO SEGÚN ROL
    # ==========================================================

    if es_noc:

        notificaciones = notificaciones.filter(
            Q(usuario_destino=request.user)
            | Q(usuario_destino__isnull=True)
        )

    else:

        notificaciones = notificaciones.filter(
            usuario_destino=request.user
        )


    # ==========================================================
    # FILTRO TODAS / NO LEÍDAS / LEÍDAS
    # ==========================================================

    filtro = request.GET.get(
        "filtro",
        "todas",
    )


    # ==========================================================
    # CONTADORES
    # ==========================================================

    total_notificaciones = (
        notificaciones.count()
    )

    notificaciones_no_leidas = (
        notificaciones
        .filter(
            leida=False
        )
        .count()
    )

    notificaciones_leidas = (
        notificaciones
        .filter(
            leida=True
        )
        .count()
    )


    # ==========================================================
    # APLICAR FILTRO DE BANDEJA
    # ==========================================================

    if filtro == "no_leidas":

        notificaciones = (
            notificaciones
            .filter(
                leida=False
            )
        )

    elif filtro == "leidas":

        notificaciones = (
            notificaciones
            .filter(
                leida=True
            )
        )


    # ==========================================================
    # DATOS PARA MOSTRAR
    # ==========================================================

    notificaciones = (
        notificaciones
        .select_related(
            "incidencia",
            "usuario_destino",
        )
        .order_by(
            "-creado_en"
        )
    )


    return render(
        request,
        "incidencias/notificaciones/lista.html",
        {
            "notificaciones": notificaciones,
            "total_notificaciones": total_notificaciones,
            "notificaciones_no_leidas": notificaciones_no_leidas,
            "notificaciones_leidas": notificaciones_leidas,
            "filtro": filtro,
        },
    )


@login_required
def notificaciones_nuevas(request):

    try:
        ultimo_id = int(
            request.GET.get("ultimo_id", 0)
        )
    except (TypeError, ValueError):
        ultimo_id = 0


    perfil = getattr(
        request.user,
        "perfil_incidencias",
        None,
    )

    es_noc = (
        request.user.is_superuser
        or (
            perfil
            and perfil.rol in [
                "ADMINISTRADOR",
                "GESTOR_NOC",
                "SUPERVISOR",
            ]
        )
    )


    notificaciones = (
        NotificacionIncidencia.objects
        .filter(
            medio=MedioNotificacion.SISTEMA,
            id__gt=ultimo_id,
        )
    )


    if es_noc:

        notificaciones = notificaciones.filter(
            Q(usuario_destino=request.user)
            | Q(usuario_destino__isnull=True)
        )

    else:

        notificaciones = notificaciones.filter(
            usuario_destino=request.user
        )


    notificaciones = (
        notificaciones
        .select_related("incidencia")
        .order_by("id")[:10]
    )


    datos = []

    for notificacion in notificaciones:

        datos.append({
            "id": notificacion.id,

            "mensaje": notificacion.mensaje,

            "codigo": (
                notificacion.incidencia.codigo
                if notificacion.incidencia
                else None
            ),

            "incidencia_id": (
                notificacion.incidencia.id
                if notificacion.incidencia
                else None
            ),

            "url": (
                reverse(
                    "incidencias:incidencia_detalle",
                    kwargs={
                        "incidencia_id":
                            notificacion.incidencia.id
                    },
                )
                if notificacion.incidencia
                else None
            ),

            "fecha": timezone.localtime(
                notificacion.creado_en
            ).strftime("%d/%m/%Y %H:%M"),
        })


    return JsonResponse({
        "notificaciones": datos,
    })


@login_required
def notificacion_abrir(request, notificacion_id):

    notificacion = get_object_or_404(
        NotificacionIncidencia.objects.select_related(
            "incidencia",
            "usuario_destino",
        ),
        pk=notificacion_id,
    )

    # Seguridad:
    # una notificación personal solo puede abrirla su destinatario
    if (
        notificacion.usuario_destino
        and notificacion.usuario_destino != request.user
    ):
        return render(
            request,
            "incidencias/403.html",
            status=403,
        )

    if not notificacion.leida:
        notificacion.leida = True
        notificacion.fecha_lectura = timezone.now()
        notificacion.actualizado_por = request.user

        notificacion.save(
            update_fields=[
                "leida",
                "fecha_lectura",
                "actualizado_por",
            ]
        )

    return redirect(
        "incidencias:incidencia_detalle",
        incidencia_id=notificacion.incidencia_id,
    )


@login_required
def notificaciones_marcar_todas_leidas(request):

    rol = obtener_rol_usuario(request.user)

    notificaciones = NotificacionIncidencia.objects.filter(
        medio=MedioNotificacion.SISTEMA,
        leida=False,
    )

    if (
        request.user.is_superuser
        or rol in [
            "ADMINISTRADOR",
            "GESTOR_NOC",
            "SUPERVISOR",
        ]
    ):
        notificaciones = notificaciones.filter(
            Q(usuario_destino=request.user)
            | Q(usuario_destino__isnull=True)
        )
    else:
        notificaciones = notificaciones.filter(
            usuario_destino=request.user
        )

    ahora = timezone.now()

    notificaciones.update(
        leida=True,
        fecha_lectura=ahora,
        actualizado_por=request.user,
    )

    messages.success(
        request,
        "Todas las notificaciones fueron marcadas como leídas.",
    )

    return redirect(
        "incidencias:notificaciones_lista"
    )



# ==========================================================
# CONFIGURACIÓN SLA
# ==========================================================


@login_required
@user_passes_test(
    es_administrador,
    login_url="incidencias:acceso_denegado",
)
def sla_configuracion_lista(request):

    slas = (
        SLAIncidencia.objects
        .annotate(
            orden_severidad=Case(
                When(severidad="CRITICA", then=Value(1)),
                When(severidad="ALTA", then=Value(2)),
                When(severidad="MEDIA", then=Value(3)),
                When(severidad="BAJA", then=Value(4)),
                When(severidad="INFORMATIVA", then=Value(5)),
                default=Value(99),
                output_field=IntegerField(),
            )
        )
        .order_by("orden_severidad")
    )

    return render(
        request,
        "incidencias/sla/configuracion_lista.html",
        {
            "slas": slas,
        },
    )


@login_required
@user_passes_test(
    es_administrador,
    login_url="incidencias:acceso_denegado",
)
def sla_configuracion_editar(request, sla_id):

    sla = get_object_or_404(
        SLAIncidencia,
        pk=sla_id,
    )

    if request.method == "POST":

        nombre = request.POST.get("nombre", "").strip()
        descripcion = request.POST.get("descripcion", "").strip()

        genera_incidencia_automatica = (
            request.POST.get("genera_incidencia_automatica") == "on"
        )

        tiempo_confirmacion = request.POST.get(
            "tiempo_confirmacion_zabbix_min"
        )

        tiempo_registro = request.POST.get(
            "tiempo_max_registro_min"
        )

        tiempo_asignacion = request.POST.get(
            "tiempo_max_asignacion_min"
        )

        tiempo_inicio = request.POST.get(
            "tiempo_max_inicio_atencion_min"
        )

        tiempo_resolucion = request.POST.get(
            "tiempo_max_resolucion_min"
        )

        activo = request.POST.get("activo") == "on"

        errores = []

        if not nombre:
            errores.append(
                "El nombre del SLA es obligatorio."
            )

        try:
            tiempo_confirmacion = int(tiempo_confirmacion)

            if tiempo_confirmacion <= 0:
                raise ValueError

        except (TypeError, ValueError):
            errores.append(
                "El tiempo de confirmación Zabbix debe ser mayor que 0."
            )

        try:
            tiempo_registro = int(tiempo_registro)

            if tiempo_registro <= 0:
                raise ValueError

        except (TypeError, ValueError):
            errores.append(
                "El tiempo máximo de registro debe ser mayor que 0."
            )

        try:
            tiempo_asignacion = int(tiempo_asignacion)

            if tiempo_asignacion <= 0:
                raise ValueError

        except (TypeError, ValueError):
            errores.append(
                "El tiempo máximo de asignación debe ser mayor que 0."
            )

        try:
            tiempo_inicio = int(tiempo_inicio)

            if tiempo_inicio <= 0:
                raise ValueError

        except (TypeError, ValueError):
            errores.append(
                "El tiempo máximo de inicio de atención debe ser mayor que 0."
            )

        try:
            tiempo_resolucion = int(tiempo_resolucion)

            if tiempo_resolucion <= 0:
                raise ValueError

        except (TypeError, ValueError):
            errores.append(
                "El tiempo máximo de resolución debe ser mayor que 0."
            )

        if errores:

            for error in errores:

                messages.error(
                    request,
                    error,
                )

            return render(
                request,
                "incidencias/sla/configuracion_editar.html",
                {
                    "sla": sla,
                },
            )

        sla.nombre = nombre

        sla.genera_incidencia_automatica = (
            genera_incidencia_automatica
        )

        sla.tiempo_confirmacion_zabbix_min = (
            tiempo_confirmacion
        )

        sla.tiempo_max_registro_min = (
            tiempo_registro
        )

        sla.tiempo_max_asignacion_min = (
            tiempo_asignacion
        )

        sla.tiempo_max_inicio_atencion_min = (
            tiempo_inicio
        )

        sla.tiempo_max_resolucion_min = (
            tiempo_resolucion
        )

        sla.descripcion = descripcion or None
        sla.activo = activo

        sla.save()

        messages.success(
            request,
            (
                f"SLA {sla.get_severidad_display()} "
                f"actualizado correctamente."
            ),
        )

        return redirect(
            "incidencias:sla_configuracion_lista"
        )

    return render(
        request,
        "incidencias/sla/configuracion_editar.html",
        {
            "sla": sla,
        },
    )



# ==========================================================
# REPORTES
# ==========================================================


def _crear_respuesta_csv(nombre_archivo):
    """Crea una respuesta CSV compatible con Excel (UTF-8 + BOM)."""
    response = HttpResponse(
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{nombre_archivo}"'
    )
    response.write("\ufeff")

    writer = csv.writer(
        response,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
    return response, writer


def _fecha_csv(valor):
    """Convierte una fecha/hora Django a hora local legible."""
    if not valor:
        return ""

    if timezone.is_naive(valor):
        valor = timezone.make_aware(
            valor,
            timezone.get_current_timezone(),
        )

    return timezone.localtime(valor).strftime(
        "%d/%m/%Y %H:%M:%S"
    )


def _sla_csv(valor):
    """Convierte un resultado SLA booleano a texto."""
    if valor is True:
        return "Cumple"
    if valor is False:
        return "Incumple"
    return "Pendiente"


def _valor_csv(valor):
    """Conserva correctamente el valor cero en las exportaciones."""
    return "" if valor is None else valor


def _nombre_csv(
    prefijo,
    request,
    parametro_desde="fecha_desde",
    parametro_hasta="fecha_hasta",
):
    """Construye un nombre de archivo según el período filtrado."""
    fecha_actual = timezone.localdate().strftime("%Y-%m-%d")

    fecha_desde = request.GET.get(
        parametro_desde,
        "",
    ).strip()

    fecha_hasta = request.GET.get(
        parametro_hasta,
        "",
    ).strip()

    if fecha_desde or fecha_hasta:
        desde = fecha_desde or "inicio"
        hasta = fecha_hasta or "actual"
        return f"{prefijo}_{desde}_{hasta}.csv"

    return f"{prefijo}_{fecha_actual}.csv"


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def reporte_incidencias(request):
    """
    PBI-096.
    Reporte general de incidencias.

    Utiliza exactamente los mismos filtros
    que el listado y la exportación CSV.
    """

    # ==========================================================
    # CONSULTA BASE
    # ==========================================================

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "registrado_por",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    # ==========================================================
    # FILTROS COMUNES
    # ==========================================================

    incidencias, filtros = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    query = filtros["query"]
    estado = filtros["estado_seleccionado"]
    severidad = filtros["severidad_seleccionada"]
    nodo_id = filtros["nodo_seleccionado"]

    fecha_desde = filtros["fecha_desde"]
    fecha_hasta = filtros["fecha_hasta"]

    # ==========================================================
    # RESUMEN EJECUTIVO
    # ==========================================================

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
        severidad__in=[
            "ALTA",
            "CRITICA",
        ],
    ).count()

    # ==========================================================
    # TIEMPOS
    # ==========================================================

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
        round(
            sum(tiempos_asignacion)
            / len(tiempos_asignacion),
            2,
        )
        if tiempos_asignacion
        else None
    )

    promedio_cierre_min = (
        round(
            sum(tiempos_cierre)
            / len(tiempos_cierre),
            2,
        )
        if tiempos_cierre
        else None
    )

    # ==========================================================
    # SLA
    # ==========================================================

    sla_evaluadas = incidencias.filter(
        cumple_sla_resolucion__isnull=False,
    ).count()

    sla_cumplidas = incidencias.filter(
        cumple_sla_resolucion=True,
    ).count()

    porcentaje_sla = (
        round(
            (sla_cumplidas / sla_evaluadas) * 100,
            2,
        )
        if sla_evaluadas
        else None
    )

    # ==========================================================
    # TEXTO DE FILTROS
    # ==========================================================

    estado_texto = ""

    if estado:
        estado_texto = dict(
            EstadoIncidencia.choices
        ).get(
            estado,
            estado,
        )

    severidad_texto = ""

    if severidad:
        severidad_texto = (
            severidad
            .replace("_", " ")
            .title()
        )

    nodo_texto = ""

    if nodo_id:
        nodo = Nodo.objects.filter(
            pk=nodo_id,
        ).first()

        if nodo:
            nodo_texto = (
                f"{nodo.codigo} - {nodo.nombre}"
            )

    # ==========================================================
    # CONTEXTO
    # ==========================================================

    context = {
        # ==========================================================
        # RESULTADOS
        # ==========================================================
        "incidencias": incidencias,
        "fecha_generacion": timezone.localtime(),

        # ==========================================================
        # RESUMEN
        # ==========================================================
        "total_incidencias": total_incidencias,
        "total_detectadas": total_detectadas,
        "total_en_atencion": total_en_atencion,
        "total_cerradas": total_cerradas,
        "total_altas_criticas": total_altas_criticas,

        # ==========================================================
        # INDICADORES
        # ==========================================================
        "promedio_asignacion_min": promedio_asignacion_min,
        "promedio_cierre_min": promedio_cierre_min,
        "porcentaje_sla": porcentaje_sla,

        # ==========================================================
        # MANTENER FILTROS EN PANTALLA
        # ==========================================================
        "query": query,
        "estado_seleccionado": estado,
        "severidad_seleccionada": severidad,
        "nodo_seleccionado": nodo_id,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,

        # ==========================================================
        # TEXTOS PARA REPORTE / IMPRESIÓN
        # ==========================================================
        "estado_texto": estado_texto,
        "severidad_texto": severidad_texto,
        "nodo_texto": nodo_texto,
    }

    return render(
        request,
        "incidencias/reportes/reporte_incidencias.html",
        context,
    )


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def exportar_incidencias_csv(request):
    """
    PBI-096.

    Exporta las incidencias filtradas en formato CSV.

    Utiliza exactamente los mismos filtros que:
    - listado de incidencias;
    - reporte general;
    - período desde / hasta;
    - estado;
    - severidad;
    - nodo;
    - búsqueda general.
    """

    # ==========================================================
    # CONSULTA BASE
    # ==========================================================

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "registrado_por",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    # ==========================================================
    # FILTROS COMUNES
    # ==========================================================

    incidencias, filtros = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    # ==========================================================
    # FUNCIONES AUXILIARES
    # ==========================================================

    def fecha_excel(valor):
        """
        Convierte un DateTimeField a fecha/hora local
        para mostrar correctamente en Excel.
        """

        if not valor:
            return ""

        if timezone.is_naive(valor):
            valor = timezone.make_aware(
                valor,
                timezone.get_current_timezone(),
            )

        return timezone.localtime(valor).strftime(
            "%d/%m/%Y %H:%M:%S"
        )

    def sla_texto(valor):
        """
        Convierte valores booleanos SLA
        a un texto legible.
        """

        if valor is True:
            return "Sí"

        if valor is False:
            return "No"

        return "No evaluado"

    def minutos_texto(valor):
        """
        Mantiene correctamente el valor 0.

        Evita usar:
            valor or ""

        porque 0 también sería convertido a vacío.
        """

        if valor is None:
            return ""

        return valor

    # ==========================================================
    # NOMBRE DEL ARCHIVO
    # ==========================================================

    fecha_actual = timezone.localdate().strftime(
        "%Y-%m-%d"
    )

    fecha_desde = filtros.get(
        "fecha_desde",
        "",
    )

    fecha_hasta = filtros.get(
        "fecha_hasta",
        "",
    )

    # Si existe un período, se incluye en el nombre.
    if fecha_desde or fecha_hasta:

        desde_nombre = (
            fecha_desde
            if fecha_desde
            else "inicio"
        )

        hasta_nombre = (
            fecha_hasta
            if fecha_hasta
            else "actual"
        )

        nombre_archivo = (
            f"incidencias_"
            f"{desde_nombre}_"
            f"{hasta_nombre}.csv"
        )

    else:

        nombre_archivo = (
            f"incidencias_{fecha_actual}.csv"
        )

    # ==========================================================
    # RESPUESTA HTTP
    # ==========================================================

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{nombre_archivo}"'
    )

    # BOM UTF-8.
    # Permite que Excel abra correctamente:
    # - tildes;
    # - ñ;
    # - caracteres especiales.
    response.write("\ufeff")

    # ==========================================================
    # WRITER CSV
    # ==========================================================

    writer = csv.writer(
        response,
        delimiter=";",
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
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
        "Nombre componente",

        "Técnico asignado",
        "Usuario registrador",

        "Clientes afectados",

        "Fecha detección",
        "Fecha registro",
        "Fecha asignación",
        "Inicio atención",
        "Fecha resolución",
        "Fecha cierre",

        "Tiempo registro (min)",
        "Tiempo asignación (min)",
        "Tiempo inicio atención (min)",
        "Tiempo resolución (min)",
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

        # ------------------------------------------------------
        # TÉCNICO
        # ------------------------------------------------------

        tecnico = ""

        if incidencia.tecnico_asignado:

            tecnico = (
                incidencia.tecnico_asignado.get_full_name()
                or incidencia.tecnico_asignado.username
            )

        # ------------------------------------------------------
        # USUARIO REGISTRADOR
        # ------------------------------------------------------

        registrador = ""

        if incidencia.registrado_por:

            registrador = (
                incidencia.registrado_por.get_full_name()
                or incidencia.registrado_por.username
            )

        # ------------------------------------------------------
        # COMPONENTE
        # ------------------------------------------------------

        componente_codigo = ""
        componente_nombre = ""

        if incidencia.componente_principal:

            componente_codigo = (
                incidencia.componente_principal.codigo
            )

            componente_nombre = (
                incidencia.componente_principal.nombre
            )

        # ------------------------------------------------------
        # FILA CSV
        # ------------------------------------------------------

        writer.writerow([

            # ==================================================
            # IDENTIFICACIÓN
            # ==================================================

            incidencia.codigo,
            incidencia.titulo,

            incidencia.get_estado_display(),
            incidencia.get_severidad_display(),
            incidencia.get_prioridad_display(),
            incidencia.get_origen_display(),

            # ==================================================
            # INFRAESTRUCTURA
            # ==================================================

            incidencia.nodo_afectado.codigo,
            incidencia.nodo_afectado.nombre,

            componente_codigo,
            componente_nombre,

            # ==================================================
            # RESPONSABLES
            # ==================================================

            tecnico,
            registrador,

            # ==================================================
            # IMPACTO
            # ==================================================

            incidencia.clientes_afectados_estimados,

            # ==================================================
            # FECHAS
            # ==================================================

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
                incidencia.fecha_resolucion
            ),

            fecha_excel(
                incidencia.fecha_cierre
            ),

            # ==================================================
            # TIEMPOS
            # ==================================================

            minutos_texto(
                incidencia.tiempo_registro_min
            ),

            minutos_texto(
                incidencia.tiempo_asignacion_min
            ),

            minutos_texto(
                incidencia.tiempo_inicio_atencion_min
            ),

            minutos_texto(
                incidencia.tiempo_resolucion_min
            ),

            minutos_texto(
                incidencia.tiempo_cierre_min
            ),

            # ==================================================
            # SLA
            # ==================================================

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

            # ==================================================
            # RESOLUCIÓN
            # ==================================================

            incidencia.solucion or "",
            incidencia.causa_raiz or "",
            incidencia.observaciones or "",
        ])

    # ==========================================================
    # RESPUESTA
    # ==========================================================

    return response

@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def reporte_incidencias_pdf(request):
    """
    Vista limpia para impresión / PDF del reporte general
    de incidencias.
    """

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "registrado_por",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    incidencias, filtros = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    total_incidencias = incidencias.count()

    total_detectadas = incidencias.filter(
        estado=EstadoIncidencia.DETECTADA
    ).count()

    total_en_atencion = incidencias.filter(
        estado=EstadoIncidencia.EN_ATENCION
    ).count()

    total_cerradas = incidencias.filter(
        estado=EstadoIncidencia.CERRADA
    ).count()

    total_altas_criticas = incidencias.filter(
        severidad__in=[
            "ALTA",
            "CRITICA",
        ]
    ).count()

    context = {
        "incidencias": incidencias,
        "fecha_generacion": timezone.localtime(),

        "total_incidencias": total_incidencias,
        "total_detectadas": total_detectadas,
        "total_en_atencion": total_en_atencion,
        "total_cerradas": total_cerradas,
        "total_altas_criticas": total_altas_criticas,

        **filtros,
    }

    return render(
        request,
        "incidencias/reportes/reporte_incidencias_pdf.html",
        context,
    )
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


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def reporte_nodos_componentes(request):
    """
    PBI-097.

    Reporte de incidencias agrupadas por:
    - nodo;
    - componente de red.

    Permite identificar recurrencia y concentración
    de incidencias en la infraestructura.
    """

    # ==========================================================
    # CONSULTA BASE
    # ==========================================================

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "registrado_por",
            "alerta_zabbix",
        )
        .order_by("-fecha_deteccion")
    )

    # ==========================================================
    # FILTROS
    #
    # Reutilizamos exactamente los mismos filtros
    # del listado, PDF y CSV.
    # ==========================================================

    incidencias, filtros = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    # ==========================================================
    # RESUMEN GENERAL
    # ==========================================================

    total_incidencias = incidencias.count()

    total_nodos = (
        incidencias
        .values("nodo_afectado_id")
        .distinct()
        .count()
    )

    total_componentes = (
        incidencias
        .filter(
            componente_principal__isnull=False,
        )
        .values("componente_principal_id")
        .distinct()
        .count()
    )

    total_criticas = incidencias.filter(
        severidad="CRITICA",
    ).count()

    # ==========================================================
    # RANKING POR NODO
    # ==========================================================

    ranking_nodos = (
        incidencias
        .values(
            "nodo_afectado_id",
            "nodo_afectado__codigo",
            "nodo_afectado__nombre",
        )
        .annotate(
            total=Count("id"),

            criticas=Count(
                "id",
                filter=Q(
                    severidad="CRITICA"
                ),
            ),

            altas=Count(
                "id",
                filter=Q(
                    severidad="ALTA"
                ),
            ),

            cerradas=Count(
                "id",
                filter=Q(
                    estado=EstadoIncidencia.CERRADA
                ),
            ),
        )
        .order_by(
            "-total",
            "nodo_afectado__codigo",
        )
    )

    # ==========================================================
    # RANKING POR COMPONENTE
    # ==========================================================

    ranking_componentes = (
        incidencias
        .filter(
            componente_principal__isnull=False,
        )
        .values(
            "componente_principal_id",
            "componente_principal__codigo",
            "componente_principal__nombre",
            "nodo_afectado__codigo",
            "nodo_afectado__nombre",
        )
        .annotate(
            total=Count("id"),

            criticas=Count(
                "id",
                filter=Q(
                    severidad="CRITICA"
                ),
            ),

            altas=Count(
                "id",
                filter=Q(
                    severidad="ALTA"
                ),
            ),

            cerradas=Count(
                "id",
                filter=Q(
                    estado=EstadoIncidencia.CERRADA
                ),
            ),
        )
        .order_by(
            "-total",
            "componente_principal__codigo",
        )
    )

    # ==========================================================
    # CONTEXTO
    # ==========================================================

    context = {
        "ranking_nodos": ranking_nodos,
        "ranking_componentes": ranking_componentes,

        "total_incidencias": total_incidencias,
        "total_nodos": total_nodos,
        "total_componentes": total_componentes,
        "total_criticas": total_criticas,

        **filtros,
    }

    return render(
        request,
        "incidencias/reportes/reporte_nodos_componentes.html",
        context,
    )


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def exportar_reporte_nodos_componentes_csv(request):
    """
    PBI-097.

    Exporta el reporte de recurrencia por nodo y componente,
    respetando los filtros aplicados en pantalla.
    """

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
        )
        .order_by("-fecha_deteccion")
    )

    incidencias, _ = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    ranking_nodos = (
        incidencias
        .values(
            "nodo_afectado_id",
            "nodo_afectado__codigo",
            "nodo_afectado__nombre",
        )
        .annotate(
            total=Count("id"),
            criticas=Count(
                "id",
                filter=Q(severidad="CRITICA"),
            ),
            altas=Count(
                "id",
                filter=Q(severidad="ALTA"),
            ),
            cerradas=Count(
                "id",
                filter=Q(
                    estado=EstadoIncidencia.CERRADA,
                ),
            ),
        )
        .order_by(
            "-total",
            "nodo_afectado__codigo",
        )
    )

    ranking_componentes = (
        incidencias
        .filter(
            componente_principal__isnull=False,
        )
        .values(
            "componente_principal_id",
            "componente_principal__codigo",
            "componente_principal__nombre",
            "nodo_afectado__codigo",
            "nodo_afectado__nombre",
        )
        .annotate(
            total=Count("id"),
            criticas=Count(
                "id",
                filter=Q(severidad="CRITICA"),
            ),
            altas=Count(
                "id",
                filter=Q(severidad="ALTA"),
            ),
            cerradas=Count(
                "id",
                filter=Q(
                    estado=EstadoIncidencia.CERRADA,
                ),
            ),
        )
        .order_by(
            "-total",
            "componente_principal__codigo",
        )
    )

    nombre_archivo = _nombre_csv(
        "recurrencia",
        request,
    )

    response, writer = _crear_respuesta_csv(
        nombre_archivo,
    )

    writer.writerow([
        "Tipo",
        "Nodo",
        "Nombre nodo",
        "Componente",
        "Nombre componente",
        "Total incidencias",
        "Críticas",
        "Altas",
        "Cerradas",
    ])

    for item in ranking_nodos:
        writer.writerow([
            "Nodo",
            item["nodo_afectado__codigo"] or "",
            item["nodo_afectado__nombre"] or "",
            "",
            "",
            item["total"],
            item["criticas"],
            item["altas"],
            item["cerradas"],
        ])

    for item in ranking_componentes:
        writer.writerow([
            "Componente",
            item["nodo_afectado__codigo"] or "",
            item["nodo_afectado__nombre"] or "",
            item["componente_principal__codigo"] or "",
            item["componente_principal__nombre"] or "",
            item["total"],
            item["criticas"],
            item["altas"],
            item["cerradas"],
        ])

    return response


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def reporte_sla_tiempos(request):
    """
    Reporte operativo de tiempos de atención
    y cumplimiento de SLA.
    """

    # ==========================================================
    # CONSULTA BASE
    # ==========================================================

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "sla",
        )
        .order_by("-fecha_deteccion")
    )

    # ==========================================================
    # FILTROS COMUNES
    # ==========================================================

    incidencias, filtros = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    # Evaluamos una sola vez el queryset porque los tiempos
    # son propiedades calculadas del modelo.
    incidencias_lista = list(incidencias)

    # ==========================================================
    # LÍMITES SLA POR INCIDENCIA
    # ==========================================================

    for incidencia in incidencias_lista:

        incidencia.sla_registro_max = (
            incidencia.sla.tiempo_max_registro_min
            if incidencia.sla
            else None
        )

        incidencia.sla_asignacion_max = (
            incidencia.sla.tiempo_max_asignacion_min
            if incidencia.sla
            else None
        )

        incidencia.sla_inicio_max = (
            incidencia.sla.tiempo_max_inicio_atencion_min
            if incidencia.sla
            else None
        )

        incidencia.sla_resolucion_max = (
            incidencia.sla.tiempo_max_resolucion_min
            if incidencia.sla
            else None
        )

    # ==========================================================
    # ESTADO ACTUAL DEL SLA EN INCIDENCIAS ABIERTAS
    # ==========================================================

    ahora = timezone.now()

    for incidencia in incidencias_lista:

        incidencia.sla_actual_estado = None
        incidencia.sla_actual_etapa = None
        incidencia.sla_actual_transcurrido = None
        incidencia.sla_actual_limite = None

        if not incidencia.sla:
            continue

        # ======================================================
        # ESPERANDO ASIGNACIÓN
        # Registro -> Asignación
        # ======================================================

        if (
            incidencia.fecha_registro
            and not incidencia.fecha_asignacion
        ):

            minutos = calcular_minutos(
                incidencia.fecha_registro,
                ahora,
            )

            limite = (
                incidencia.sla
                .tiempo_max_asignacion_min
            )

            incidencia.sla_actual_etapa = "Asignación"
            incidencia.sla_actual_transcurrido = minutos
            incidencia.sla_actual_limite = limite

            if minutos is not None and limite is not None:

                if minutos > limite:
                    incidencia.sla_actual_estado = "VENCIDO"
                else:
                    incidencia.sla_actual_estado = "EN_TIEMPO"

        # ======================================================
        # ASIGNADA PERO SIN INICIAR ATENCIÓN
        # Asignación -> Inicio
        # ======================================================

        elif (
            incidencia.fecha_asignacion
            and not incidencia.fecha_inicio_atencion
        ):

            minutos = calcular_minutos(
                incidencia.fecha_asignacion,
                ahora,
            )

            limite = (
                incidencia.sla
                .tiempo_max_inicio_atencion_min
            )

            incidencia.sla_actual_etapa = "Inicio de atención"
            incidencia.sla_actual_transcurrido = minutos
            incidencia.sla_actual_limite = limite

            if minutos is not None and limite is not None:

                if minutos > limite:
                    incidencia.sla_actual_estado = "VENCIDO"
                else:
                    incidencia.sla_actual_estado = "EN_TIEMPO"

        # ======================================================
        # EN ATENCIÓN PERO SIN RESOLVER
        # Detección -> Resolución
        # ======================================================

        elif (
            incidencia.fecha_inicio_atencion
            and not incidencia.fecha_resolucion
        ):

            minutos = calcular_minutos(
                incidencia.fecha_deteccion,
                ahora,
            )

            limite = (
                incidencia.sla
                .tiempo_max_resolucion_min
            )

            incidencia.sla_actual_etapa = "Resolución"
            incidencia.sla_actual_transcurrido = minutos
            incidencia.sla_actual_limite = limite

            if minutos is not None and limite is not None:

                if minutos > limite:
                    incidencia.sla_actual_estado = "VENCIDO"
                else:
                    incidencia.sla_actual_estado = "EN_TIEMPO"

    # ==========================================================
    # RESUMEN SLA ACTUAL DE INCIDENCIAS ABIERTAS
    # ==========================================================

    incidencias_sla_vencido = sum(
        1
        for incidencia in incidencias_lista
        if incidencia.sla_actual_estado == "VENCIDO"
    )

    incidencias_sla_en_tiempo = sum(
        1
        for incidencia in incidencias_lista
        if incidencia.sla_actual_estado == "EN_TIEMPO"
    )

    # ==========================================================
    # FUNCIONES AUXILIARES
    # ==========================================================

    def promedio(valores):

        valores_validos = [
            valor
            for valor in valores
            if valor is not None
        ]

        if not valores_validos:
            return None

        return round(
            sum(valores_validos) / len(valores_validos),
            2,
        )

    def calcular_sla(nombre_campo):

        valores = [
            getattr(incidencia, nombre_campo)
            for incidencia in incidencias_lista
        ]

        evaluados = [
            valor
            for valor in valores
            if valor is not None
        ]

        cumplidos = sum(
            1
            for valor in evaluados
            if valor is True
        )

        incumplidos = sum(
            1
            for valor in evaluados
            if valor is False
        )

        porcentaje = (
            round(
                (
                    cumplidos
                    / len(evaluados)
                ) * 100,
                2,
            )
            if evaluados
            else None
        )

        return {
            "evaluados": len(evaluados),
            "cumplidos": cumplidos,
            "incumplidos": incumplidos,
            "porcentaje": porcentaje,
        }

    # ==========================================================
    # TOTAL GENERAL
    # ==========================================================

    total_incidencias = len(incidencias_lista)

    # ==========================================================
    # TIEMPOS PROMEDIO
    # ==========================================================

    promedio_registro = promedio([
        incidencia.tiempo_registro_min
        for incidencia in incidencias_lista
    ])

    promedio_asignacion = promedio([
        incidencia.tiempo_asignacion_min
        for incidencia in incidencias_lista
    ])

    promedio_inicio_atencion = promedio([
        incidencia.tiempo_inicio_atencion_min
        for incidencia in incidencias_lista
    ])

    promedio_resolucion = promedio([
        incidencia.tiempo_resolucion_min
        for incidencia in incidencias_lista
    ])

    promedio_cierre = promedio([
        incidencia.tiempo_cierre_min
        for incidencia in incidencias_lista
    ])

    # ==========================================================
    # CUMPLIMIENTO SLA HISTÓRICO
    # ==========================================================

    sla_registro = calcular_sla(
        "cumple_sla_registro"
    )

    sla_asignacion = calcular_sla(
        "cumple_sla_asignacion"
    )

    sla_inicio_atencion = calcular_sla(
        "cumple_sla_inicio_atencion"
    )

    sla_resolucion = calcular_sla(
        "cumple_sla_resolucion"
    )

    # ==========================================================
    # RESUMEN SLA POR ETAPA
    # ==========================================================

    resumen_sla = [
        {
            "etapa": "Registro",
            **sla_registro,
        },
        {
            "etapa": "Asignación",
            **sla_asignacion,
        },
        {
            "etapa": "Inicio de atención",
            **sla_inicio_atencion,
        },
        {
            "etapa": "Resolución",
            **sla_resolucion,
        },
    ]

    # ==========================================================
    # INDICADORES GENERALES
    # ==========================================================

    sla_total_evaluados = sum(
        item["evaluados"]
        for item in resumen_sla
    )

    sla_total_cumplidos = sum(
        item["cumplidos"]
        for item in resumen_sla
    )

    sla_total_incumplidos = sum(
        item["incumplidos"]
        for item in resumen_sla
    )

    porcentaje_sla_general = (
        round(
            (
                sla_total_cumplidos
                / sla_total_evaluados
            ) * 100,
            2,
        )
        if sla_total_evaluados
        else None
    )

    # ==========================================================
    # NODOS PARA FILTRO
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
    # CONTEXTO
    # ==========================================================

    context = {

        # ------------------------------------------------------
        # GENERAL
        # ------------------------------------------------------

        "total_incidencias": total_incidencias,
        "incidencias": incidencias_lista,

        # ------------------------------------------------------
        # TIEMPOS PROMEDIO
        # ------------------------------------------------------

        "promedio_registro": promedio_registro,
        "promedio_asignacion": promedio_asignacion,
        "promedio_inicio_atencion": promedio_inicio_atencion,
        "promedio_resolucion": promedio_resolucion,
        "promedio_cierre": promedio_cierre,

        # ------------------------------------------------------
        # SLA HISTÓRICO
        # ------------------------------------------------------

        "resumen_sla": resumen_sla,

        "sla_total_evaluados": sla_total_evaluados,
        "sla_total_cumplidos": sla_total_cumplidos,
        "sla_total_incumplidos": sla_total_incumplidos,

        "porcentaje_sla_general": porcentaje_sla_general,

        # ------------------------------------------------------
        # SLA ACTUAL DE INCIDENCIAS ABIERTAS
        # ------------------------------------------------------

        "incidencias_sla_vencido": incidencias_sla_vencido,
        "incidencias_sla_en_tiempo": incidencias_sla_en_tiempo,

        # ------------------------------------------------------
        # FILTROS
        # ------------------------------------------------------

        "nodos": nodos,

        **filtros,
    }

    return render(
        request,
        "incidencias/reportes/reporte_sla_tiempos.html",
        context,
    )


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def exportar_reporte_sla_tiempos_csv(request):
    """
    PBI-098.

    Exporta tiempos reales, límites y cumplimiento SLA
    para las incidencias filtradas.
    """

    incidencias = (
        Incidencia.objects
        .select_related(
            "nodo_afectado",
            "componente_principal",
            "tecnico_asignado",
            "sla",
        )
        .order_by("-fecha_deteccion")
    )

    incidencias, _ = aplicar_filtros_incidencias(
        request,
        incidencias,
    )

    ahora = timezone.now()

    nombre_archivo = _nombre_csv(
        "sla_tiempos",
        request,
    )

    response, writer = _crear_respuesta_csv(
        nombre_archivo,
    )

    writer.writerow([
        "Código",
        "Título",
        "Estado",
        "Severidad",
        "Nodo",
        "Componente",
        "Técnico",
        "Fecha detección",
        "Fecha registro",
        "Fecha asignación",
        "Inicio atención",
        "Fecha resolución",
        "Fecha cierre",
        "Tiempo registro (min)",
        "Límite registro (min)",
        "Resultado registro",
        "Tiempo asignación (min)",
        "Límite asignación (min)",
        "Resultado asignación",
        "Tiempo inicio atención (min)",
        "Límite inicio atención (min)",
        "Resultado inicio",
        "Tiempo resolución (min)",
        "Límite resolución (min)",
        "Resultado resolución",
        "Etapa SLA actual",
        "Transcurrido SLA actual (min)",
        "Límite SLA actual (min)",
        "Estado SLA actual",
    ])

    for incidencia in incidencias:
        componente = (
            incidencia.componente_principal.codigo
            if incidencia.componente_principal
            else ""
        )

        tecnico = ""
        if incidencia.tecnico_asignado:
            tecnico = (
                incidencia.tecnico_asignado.get_full_name()
                or incidencia.tecnico_asignado.username
            )

        sla = incidencia.sla

        limite_registro = (
            sla.tiempo_max_registro_min
            if sla
            else None
        )
        limite_asignacion = (
            sla.tiempo_max_asignacion_min
            if sla
            else None
        )
        limite_inicio = (
            sla.tiempo_max_inicio_atencion_min
            if sla
            else None
        )
        limite_resolucion = (
            sla.tiempo_max_resolucion_min
            if sla
            else None
        )

        etapa_actual = ""
        transcurrido_actual = None
        limite_actual = None
        estado_actual = ""

        if sla:
            if (
                incidencia.fecha_registro
                and not incidencia.fecha_asignacion
            ):
                etapa_actual = "Asignación"
                transcurrido_actual = calcular_minutos(
                    incidencia.fecha_registro,
                    ahora,
                )
                limite_actual = limite_asignacion

            elif (
                incidencia.fecha_asignacion
                and not incidencia.fecha_inicio_atencion
            ):
                etapa_actual = "Inicio de atención"
                transcurrido_actual = calcular_minutos(
                    incidencia.fecha_asignacion,
                    ahora,
                )
                limite_actual = limite_inicio

            elif (
                incidencia.fecha_inicio_atencion
                and not incidencia.fecha_resolucion
            ):
                etapa_actual = "Resolución"
                transcurrido_actual = calcular_minutos(
                    incidencia.fecha_deteccion,
                    ahora,
                )
                limite_actual = limite_resolucion

            if (
                transcurrido_actual is not None
                and limite_actual is not None
            ):
                estado_actual = (
                    "VENCIDO"
                    if transcurrido_actual > limite_actual
                    else "EN TIEMPO"
                )

        writer.writerow([
            incidencia.codigo,
            incidencia.titulo,
            incidencia.get_estado_display(),
            incidencia.get_severidad_display(),
            incidencia.nodo_afectado.codigo,
            componente,
            tecnico,
            _fecha_csv(incidencia.fecha_deteccion),
            _fecha_csv(incidencia.fecha_registro),
            _fecha_csv(incidencia.fecha_asignacion),
            _fecha_csv(incidencia.fecha_inicio_atencion),
            _fecha_csv(incidencia.fecha_resolucion),
            _fecha_csv(incidencia.fecha_cierre),
            _valor_csv(incidencia.tiempo_registro_min),
            _valor_csv(limite_registro),
            _sla_csv(incidencia.cumple_sla_registro),
            _valor_csv(incidencia.tiempo_asignacion_min),
            _valor_csv(limite_asignacion),
            _sla_csv(incidencia.cumple_sla_asignacion),
            _valor_csv(incidencia.tiempo_inicio_atencion_min),
            _valor_csv(limite_inicio),
            _sla_csv(
                incidencia.cumple_sla_inicio_atencion
            ),
            _valor_csv(incidencia.tiempo_resolucion_min),
            _valor_csv(limite_resolucion),
            _sla_csv(incidencia.cumple_sla_resolucion),
            etapa_actual,
            _valor_csv(transcurrido_actual),
            _valor_csv(limite_actual),
            estado_actual,
        ])

    return response


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def reporte_tecnicos(request):

    User = get_user_model()

    tecnico_id = request.GET.get("tecnico", "").strip()
    fecha_desde = request.GET.get("desde", "").strip()
    fecha_hasta = request.GET.get("hasta", "").strip()

    tecnicos = (
        User.objects
        .filter(
            perfil_incidencias__rol="TECNICO",
            is_active=True,
        )
        .order_by(
            "first_name",
            "last_name",
            "username",
        )
    )

    if tecnico_id:
        tecnicos_reporte = tecnicos.filter(
            id=tecnico_id
        )
    else:
        tecnicos_reporte = tecnicos


    resultados = []

    total_asignadas_general = 0
    total_cerradas_general = 0
    total_activas_general = 0
    total_reasignadas_general = 0

    total_cerradas_sla = 0
    total_cumple_sla = 0

    tiempos_globales = []

    def formatear_minutos(minutos):
        if minutos is None:
            return "-"

        minutos = int(round(minutos))

        dias = minutos // 1440
        horas = (minutos % 1440) // 60
        mins = minutos % 60

        partes = []

        if dias:
            partes.append(f"{dias} d")

        if horas:
            partes.append(f"{horas} h")

        if mins or not partes:
            partes.append(f"{mins} min")

        return " ".join(partes)
    
    for tecnico in tecnicos_reporte:

        # ======================================================
        # INCIDENCIAS EN LAS QUE PARTICIPÓ EL TÉCNICO
        # ======================================================

        asignaciones = (
            AsignacionIncidencia.objects
            .filter(
                tecnico=tecnico,
            )
            .select_related(
                "incidencia",
            )
        )

        if fecha_desde:
            asignaciones = asignaciones.filter(
                incidencia__fecha_deteccion__date__gte=fecha_desde
            )

        if fecha_hasta:
            asignaciones = asignaciones.filter(
                incidencia__fecha_deteccion__date__lte=fecha_hasta
            )


        incidencias_participadas_ids = (
            asignaciones
            .values_list(
                "incidencia_id",
                flat=True,
            )
            .distinct()
        )

        total_asignadas = (
            incidencias_participadas_ids.count()
        )


        # ======================================================
        # INCIDENCIAS ACTUALMENTE A SU CARGO
        # ======================================================

        incidencias_actuales = (
            Incidencia.objects
            .filter(
                tecnico_asignado=tecnico,
            )
        )

        if fecha_desde:
            incidencias_actuales = incidencias_actuales.filter(
                fecha_deteccion__date__gte=fecha_desde
            )

        if fecha_hasta:
            incidencias_actuales = incidencias_actuales.filter(
                fecha_deteccion__date__lte=fecha_hasta
            )


        total_activas = (
            incidencias_actuales
            .exclude(
                estado__in=[
                    EstadoIncidencia.CERRADA,
                    EstadoIncidencia.CANCELADA,
                ]
            )
            .count()
        )


        # ======================================================
        # INCIDENCIAS CERRADAS SIENDO RESPONSABLE FINAL
        # ======================================================

        cerradas = (
            incidencias_actuales
            .filter(
                estado=EstadoIncidencia.CERRADA,
            )
        )

        total_cerradas = cerradas.count()


        # ======================================================
        # INCIDENCIAS QUE FUERON REASIGNADAS A OTRO TÉCNICO
        # ======================================================

        incidencias_reasignadas = (
            Incidencia.objects
            .filter(
                id__in=incidencias_participadas_ids,
            )
            .exclude(
                tecnico_asignado=tecnico,
            )
        )

        if fecha_desde:
            incidencias_reasignadas = incidencias_reasignadas.filter(
                fecha_deteccion__date__gte=fecha_desde
            )

        if fecha_hasta:
            incidencias_reasignadas = incidencias_reasignadas.filter(
                fecha_deteccion__date__lte=fecha_hasta
            )

        total_reasignadas = (
            incidencias_reasignadas
            .distinct()
            .count()
        )


        # ======================================================
        # CUMPLIMIENTO SLA DE RESOLUCIÓN
        # ======================================================

        cerradas_cumplen_sla = (
            cerradas
            .filter(
                cumple_sla_resolucion=True,
            )
            .count()
        )

        if total_cerradas > 0:

            porcentaje_sla = round(
                (
                    cerradas_cumplen_sla
                    / total_cerradas
                ) * 100,
                1,
            )

        else:

            porcentaje_sla = 0


        # ======================================================
        # TIEMPO PROMEDIO DE RESOLUCIÓN
        # ======================================================

        tiempos_resolucion = []

        for incidencia in cerradas:

            tiempo = (
                incidencia.tiempo_resolucion_min
            )

            if tiempo is not None:

                tiempos_resolucion.append(
                    tiempo
                )

                tiempos_globales.append(
                    tiempo
                )


        if tiempos_resolucion:

            tiempo_promedio = round(
                sum(tiempos_resolucion)
                / len(tiempos_resolucion),
                1,
            )

        else:

            tiempo_promedio = None


        resultados.append(
            {
                "tecnico": tecnico,
                "total_asignadas": total_asignadas,
                "total_activas": total_activas,
                "total_cerradas": total_cerradas,
                "total_reasignadas": total_reasignadas,
                "cumple_sla": cerradas_cumplen_sla,
                "porcentaje_sla": porcentaje_sla,
                "tiempo_promedio": tiempo_promedio,
                "tiempo_promedio_texto": formatear_minutos(
                    tiempo_promedio
                ),
            }
        )


        total_asignadas_general += total_asignadas
        total_activas_general += total_activas
        total_cerradas_general += total_cerradas
        total_reasignadas_general += total_reasignadas

        total_cerradas_sla += total_cerradas
        total_cumple_sla += cerradas_cumplen_sla


    # ==========================================================
    # RESUMEN GENERAL
    # ==========================================================

    if total_cerradas_sla > 0:

        cumplimiento_sla_general = round(
            (
                total_cumple_sla
                / total_cerradas_sla
            ) * 100,
            1,
        )

    else:

        cumplimiento_sla_general = 0


    if tiempos_globales:

        tiempo_promedio_general = round(
            sum(tiempos_globales)
            / len(tiempos_globales),
            1,
        )

    else:

        tiempo_promedio_general = None


    tiempo_promedio_general_texto = formatear_minutos(
        tiempo_promedio_general
    )


    return render(
        request,
        "incidencias/reportes/reporte_tecnicos.html",
        {
            "resultados": resultados,
            "tecnicos": tecnicos,

            "tecnico_id": tecnico_id,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,

            "total_asignadas_general": total_asignadas_general,
            "total_activas_general": total_activas_general,
            "total_cerradas_general": total_cerradas_general,
            "total_reasignadas_general": total_reasignadas_general,

            "cumplimiento_sla_general": cumplimiento_sla_general,
            "tiempo_promedio_general": tiempo_promedio_general,
            "tiempo_promedio_general_texto": tiempo_promedio_general_texto,
        },
    )


@login_required
@user_passes_test(
    puede_ver_reportes,
    login_url="incidencias:acceso_denegado",
)
def exportar_reporte_tecnicos_csv(request):
    """
    Exporta el reporte de rendimiento por técnico
    respetando los filtros de técnico y período.
    """

    UserModel = get_user_model()

    tecnico_id = request.GET.get(
        "tecnico",
        "",
    ).strip()

    fecha_desde = request.GET.get(
        "desde",
        "",
    ).strip()

    fecha_hasta = request.GET.get(
        "hasta",
        "",
    ).strip()

    tecnicos = (
        UserModel.objects
        .filter(
            perfil_incidencias__rol="TECNICO",
            is_active=True,
        )
        .order_by(
            "first_name",
            "last_name",
            "username",
        )
    )

    if tecnico_id:
        tecnicos = tecnicos.filter(
            id=tecnico_id,
        )

    nombre_archivo = _nombre_csv(
        "rendimiento_tecnicos",
        request,
        parametro_desde="desde",
        parametro_hasta="hasta",
    )

    response, writer = _crear_respuesta_csv(
        nombre_archivo,
    )

    writer.writerow([
        "Técnico",
        "Usuario",
        "Incidencias asignadas",
        "Activas actuales",
        "Cerradas como responsable final",
        "Reasignadas",
        "Cerradas que cumplen SLA",
        "Cumplimiento SLA (%)",
        "Tiempo promedio resolución (min)",
    ])

    for tecnico in tecnicos:
        asignaciones = (
            AsignacionIncidencia.objects
            .filter(
                tecnico=tecnico,
            )
            .select_related(
                "incidencia",
            )
        )

        if fecha_desde:
            asignaciones = asignaciones.filter(
                incidencia__fecha_deteccion__date__gte=fecha_desde,
            )

        if fecha_hasta:
            asignaciones = asignaciones.filter(
                incidencia__fecha_deteccion__date__lte=fecha_hasta,
            )

        incidencias_participadas_ids = (
            asignaciones
            .values_list(
                "incidencia_id",
                flat=True,
            )
            .distinct()
        )

        total_asignadas = (
            incidencias_participadas_ids.count()
        )

        incidencias_actuales = (
            Incidencia.objects
            .filter(
                tecnico_asignado=tecnico,
            )
        )

        if fecha_desde:
            incidencias_actuales = (
                incidencias_actuales.filter(
                    fecha_deteccion__date__gte=fecha_desde,
                )
            )

        if fecha_hasta:
            incidencias_actuales = (
                incidencias_actuales.filter(
                    fecha_deteccion__date__lte=fecha_hasta,
                )
            )

        total_activas = (
            incidencias_actuales
            .exclude(
                estado__in=[
                    EstadoIncidencia.CERRADA,
                    EstadoIncidencia.CANCELADA,
                ],
            )
            .count()
        )

        cerradas = incidencias_actuales.filter(
            estado=EstadoIncidencia.CERRADA,
        )

        total_cerradas = cerradas.count()

        incidencias_reasignadas = (
            Incidencia.objects
            .filter(
                id__in=incidencias_participadas_ids,
            )
            .exclude(
                tecnico_asignado=tecnico,
            )
        )

        if fecha_desde:
            incidencias_reasignadas = (
                incidencias_reasignadas.filter(
                    fecha_deteccion__date__gte=fecha_desde,
                )
            )

        if fecha_hasta:
            incidencias_reasignadas = (
                incidencias_reasignadas.filter(
                    fecha_deteccion__date__lte=fecha_hasta,
                )
            )

        total_reasignadas = (
            incidencias_reasignadas
            .distinct()
            .count()
        )

        cerradas_cumplen_sla = (
            cerradas
            .filter(
                cumple_sla_resolucion=True,
            )
            .count()
        )

        porcentaje_sla = (
            round(
                (
                    cerradas_cumplen_sla
                    / total_cerradas
                ) * 100,
                1,
            )
            if total_cerradas
            else 0
        )

        tiempos_resolucion = [
            incidencia.tiempo_resolucion_min
            for incidencia in cerradas
            if incidencia.tiempo_resolucion_min is not None
        ]

        tiempo_promedio = (
            round(
                sum(tiempos_resolucion)
                / len(tiempos_resolucion),
                1,
            )
            if tiempos_resolucion
            else None
        )

        nombre_tecnico = (
            tecnico.get_full_name()
            or tecnico.username
        )

        writer.writerow([
            nombre_tecnico,
            tecnico.username,
            total_asignadas,
            total_activas,
            total_cerradas,
            total_reasignadas,
            cerradas_cumplen_sla,
            porcentaje_sla,
            _valor_csv(tiempo_promedio),
        ])

    return response



# ==========================================================
# VISTAS DE COMPATIBILIDAD / LEGACY
# ==========================================================


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
