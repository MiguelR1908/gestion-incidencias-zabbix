from django.db.models import Q

from .models import (
    MedioNotificacion,
    NotificacionIncidencia,
)


def notificaciones_globales(request):

    if not request.user.is_authenticated:
        return {
            "contador_notificaciones_no_leidas": 0,
        }

    rol = None

    perfil = getattr(
        request.user,
        "perfil_incidencias",
        None,
    )

    if perfil:
        rol = perfil.rol


    notificaciones = NotificacionIncidencia.objects.filter(
        medio=MedioNotificacion.SISTEMA,
    )


    # Administrador / Gestor NOC / Supervisor:
    # ven personales + generales NOC
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

    # Técnico / Dueño / Vendedor:
    # solo notificaciones personales
    else:

        notificaciones = notificaciones.filter(
            usuario_destino=request.user
        )


    contador = notificaciones.filter(
        leida=False
    ).count()


    return {
        "contador_notificaciones_no_leidas": contador,
    }