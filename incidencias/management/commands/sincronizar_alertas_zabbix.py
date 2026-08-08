from django.core.management.base import BaseCommand, CommandError

from incidencias.models import ConfiguracionZabbix
from incidencias.services.sincronizacion_alertas import (
    sincronizar_alertas_zabbix,
)


class Command(BaseCommand):
    help = (
        "Sincroniza las alertas activas de Zabbix, "
        "las guarda localmente y evalúa la creación "
        "automática de incidencias."
    )

    def handle(self, *args, **options):
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
            raise CommandError(
                "No existe una configuración Zabbix activa "
                "y con conexión exitosa."
            )

        self.stdout.write(
            self.style.WARNING(
                f"Sincronizando alertas desde: "
                f"{configuracion.nombre}"
            )
        )

        try:
            resultado = sincronizar_alertas_zabbix(
                configuracion=configuracion,
                usuario=None,
            )

        except Exception as exc:
            raise CommandError(
                f"Error durante la sincronización: {exc}"
            ) from exc

        self.stdout.write("")
        self.stdout.write(resultado["mensaje"])

        errores = resultado.get("errores", [])

        if errores:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    f"Se encontraron {len(errores)} errores:"
                )
            )

            for error in errores:
                self.stdout.write(
                    self.style.ERROR(str(error))
                )

        if resultado.get("ok"):
            self.stdout.write(
                self.style.SUCCESS(
                    "Sincronización de alertas finalizada "
                    "correctamente."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "La sincronización terminó parcialmente."
                )
            )