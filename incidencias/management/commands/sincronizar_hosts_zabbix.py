from django.core.management.base import BaseCommand, CommandError

from incidencias.models import ConfiguracionZabbix
from incidencias.services.sincronizacion_hosts import (
    sincronizar_hosts_zabbix,
)


class Command(BaseCommand):
    help = (
        "Sincroniza los hosts de Zabbix con el inventario "
        "de componentes de red."
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
                f"Sincronizando desde: {configuracion.nombre}"
            )
        )

        resultado = sincronizar_hosts_zabbix(
            configuracion=configuracion,
            usuario=None,
        )

        self.stdout.write("")
        self.stdout.write(resultado["mensaje"])

        if resultado["errores"]:
            for error in resultado["errores"]:
                self.stdout.write(
                    self.style.ERROR(str(error))
                )

        if resultado["ok"]:
            self.stdout.write(
                self.style.SUCCESS(
                    "Sincronización finalizada correctamente."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Sincronización finalizada parcialmente."
                )
            )