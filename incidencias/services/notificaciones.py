from django.utils import timezone

from incidencias.models import (
    EstadoNotificacion,
    MedioNotificacion,
    NotificacionIncidencia,
)


def crear_notificacion_sistema(
    incidencia,
    mensaje,
    usuario_destino=None,
    creado_por=None,
):
    """
    Registra una notificación interna asociada
    a una incidencia.
    """

    if usuario_destino:
        destinatario = (
            usuario_destino.get_full_name()
            or usuario_destino.username
        )
    else:
        destinatario = "NOC"

    return NotificacionIncidencia.objects.create(
        incidencia=incidencia,
        usuario_destino=usuario_destino,
        medio=MedioNotificacion.SISTEMA,
        destinatario=destinatario,
        mensaje=mensaje,
        estado=EstadoNotificacion.ENVIADA,
        fecha_envio=timezone.now(),
        creado_por=creado_por,
        actualizado_por=creado_por,
    )