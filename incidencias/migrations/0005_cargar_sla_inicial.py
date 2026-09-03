from django.db import migrations


def cargar_sla_inicial(apps, schema_editor):
    SLAIncidencia = apps.get_model("incidencias", "SLAIncidencia")

    datos = [
        {
            "severidad": "CRITICA",
            "nombre": "SLA Crítica",
            "genera_incidencia_automatica": True,
            "tiempo_confirmacion_zabbix_min": 1,
            "tiempo_max_registro_min": 5,
            "tiempo_max_asignacion_min": 5,
            "tiempo_max_inicio_atencion_min": 10,
            "tiempo_max_resolucion_min": 60,
            "descripcion": "SLA para incidencias críticas.",
            "activo": True,
        },
        {
            "severidad": "ALTA",
            "nombre": "SLA Alta",
            "genera_incidencia_automatica": True,
            "tiempo_confirmacion_zabbix_min": 2,
            "tiempo_max_registro_min": 10,
            "tiempo_max_asignacion_min": 10,
            "tiempo_max_inicio_atencion_min": 20,
            "tiempo_max_resolucion_min": 120,
            "descripcion": "SLA para incidencias de severidad alta.",
            "activo": True,
        },
        {
            "severidad": "MEDIA",
            "nombre": "SLA Media",
            "genera_incidencia_automatica": True,
            "tiempo_confirmacion_zabbix_min": 5,
            "tiempo_max_registro_min": 15,
            "tiempo_max_asignacion_min": 20,
            "tiempo_max_inicio_atencion_min": 30,
            "tiempo_max_resolucion_min": 240,
            "descripcion": "SLA para incidencias de severidad media.",
            "activo": True,
        },
        {
            "severidad": "BAJA",
            "nombre": "SLA Baja",
            "genera_incidencia_automatica": True,
            "tiempo_confirmacion_zabbix_min": 10,
            "tiempo_max_registro_min": 30,
            "tiempo_max_asignacion_min": 30,
            "tiempo_max_inicio_atencion_min": 60,
            "tiempo_max_resolucion_min": 480,
            "descripcion": "SLA para incidencias de severidad baja.",
            "activo": True,
        },
        {
            "severidad": "INFORMATIVA",
            "nombre": "SLA Informativa",
            "genera_incidencia_automatica": False,
            "tiempo_confirmacion_zabbix_min": 15,
            "tiempo_max_registro_min": 60,
            "tiempo_max_asignacion_min": 60,
            "tiempo_max_inicio_atencion_min": 120,
            "tiempo_max_resolucion_min": 1440,
            "descripcion": "SLA para eventos informativos.",
            "activo": True,
        },
    ]

    for item in datos:
        severidad = item["severidad"]

        SLAIncidencia.objects.get_or_create(
            severidad=severidad,
            defaults=item,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("incidencias", "0004_notificacionincidencia_fecha_lectura_and_more"),
    ]

    operations = [
        migrations.RunPython(
            cargar_sla_inicial,
            migrations.RunPython.noop,
        ),
    ]