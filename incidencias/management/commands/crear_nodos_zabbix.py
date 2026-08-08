from django.core.management.base import BaseCommand
from django.db import transaction

from incidencias.models import (
    ComponenteRed,
    Nodo,
    Ubicacion,
)


def obtener_choice(modelo, campo, preferidos):
    """
    Obtiene un valor válido según los choices reales del modelo.
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


class Command(BaseCommand):
    help = (
        "Crea los nodos operativos y asigna los componentes "
        "sincronizados desde Zabbix."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        estado_activo = obtener_choice(
            Nodo,
            "estado",
            [
                "ACTIVO",
                "OPERATIVO",
                "EN_SERVICIO",
            ],
        )

        criticidad_critica = obtener_choice(
            Nodo,
            "criticidad",
            [
                "CRITICA",
                "CRITICAL",
                "ALTA",
            ],
        )

        criticidad_alta = obtener_choice(
            Nodo,
            "criticidad",
            [
                "ALTA",
                "HIGH",
                "MEDIA",
            ],
        )

        configuracion = [
            {
                "codigo": "CERRO-MILUCHACA",
                "nombre": "Cerro Miluchaca",
                "ubicacion": "Cerro Miluchaca",
                "criticidad": criticidad_alta,
                "hosts": ["10678"],
            },
            {
                "codigo": "CHONGOS",
                "nombre": "Chongos",
                "ubicacion": "Chongos",
                "criticidad": criticidad_alta,
                "hosts": ["10681"],
            },
            {
                "codigo": "CORE",
                "nombre": "Core principal",
                "ubicacion": "Core Fiber Z",
                "criticidad": criticidad_critica,
                "hosts": [
                    "10682",
                    "10725",
                    "10726",
                    "10690",
                    "10692",
                ],
            },
            {
                "codigo": "FORTALEZA",
                "nombre": "Fortaleza",
                "ubicacion": "Fortaleza",
                "criticidad": criticidad_alta,
                "hosts": ["10693"],
            },
            {
                "codigo": "HUANCAN",
                "nombre": "Huancán",
                "ubicacion": "Huancán",
                "criticidad": criticidad_alta,
                "hosts": ["10696"],
            },
            {
                "codigo": "LAS-LOMAS",
                "nombre": "Las Lomas",
                "ubicacion": "Las Lomas",
                "criticidad": criticidad_alta,
                "hosts": ["10706"],
            },
            {
                "codigo": "ORCOTUNA",
                "nombre": "Orcotuna",
                "ubicacion": "Orcotuna",
                "criticidad": criticidad_alta,
                "hosts": [
                    "10708",
                    "10709",
                ],
            },
            {
                "codigo": "PALIAN",
                "nombre": "Palián",
                "ubicacion": "Palián",
                "criticidad": criticidad_alta,
                "hosts": [
                    "10710",
                    "10711",
                ],
            },
            {
                "codigo": "TORRE-TORRE",
                "nombre": "Torre Torre",
                "ubicacion": "Torre Torre",
                "criticidad": criticidad_critica,
                "hosts": [
                    "10716",
                    "10717",
                    "10719",
                    "10720",
                    "10721",
                ],
            },
            {
                "codigo": "MONITOREO",
                "nombre": "Plataforma de monitoreo",
                "ubicacion": "Servidor de monitoreo",
                "criticidad": criticidad_alta,
                "hosts": ["10084"],
            },
        ]

        total_nodos_creados = 0
        total_nodos_actualizados = 0
        total_componentes_asignados = 0
        hosts_no_encontrados = []

        for datos in configuracion:
            ubicacion = (
                Ubicacion.objects
                .filter(nombre=datos["ubicacion"])
                .order_by("id")
                .first()
            )

            if ubicacion is None:
                ubicacion = Ubicacion.objects.create(
                    nombre=datos["ubicacion"],
                    departamento="Junín",
                    descripcion=(
                        "Ubicación creada automáticamente "
                        "desde el inventario de Zabbix."
                    ),
                    activo=True,
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Ubicación creada: {ubicacion.nombre}"
                    )
                )

            nodo, creado = Nodo.objects.update_or_create(
                codigo=datos["codigo"],
                defaults={
                    "ubicacion": ubicacion,
                    "nombre": datos["nombre"],
                    "descripcion": (
                        "Nodo de red asociado a componentes "
                        "monitoreados desde Zabbix."
                    ),
                    "estado": estado_activo,
                    "criticidad": datos["criticidad"],
                    "clientes_estimados": 0,
                    "activo": True,
                },
            )

            if creado:
                total_nodos_creados += 1
                accion = "creado"
            else:
                total_nodos_actualizados += 1
                accion = "actualizado"

            self.stdout.write(
                f"Nodo {nodo.codigo}: {accion}"
            )

            for host_id in datos["hosts"]:
                componente = (
                    ComponenteRed.objects
                    .filter(host_id_zabbix=host_id)
                    .first()
                )

                if componente is None:
                    hosts_no_encontrados.append(host_id)

                    self.stdout.write(
                        self.style.WARNING(
                            f"Host ID {host_id}: "
                            "componente no encontrado"
                        )
                    )

                    continue

                componente.nodo = nodo
                componente.save()

                total_componentes_asignados += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"  {host_id} - {componente.nombre} "
                        f"→ {nodo.codigo}"
                    )
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Proceso finalizado correctamente."
            )
        )
        self.stdout.write(
            f"Nodos creados: {total_nodos_creados}"
        )
        self.stdout.write(
            f"Nodos actualizados: {total_nodos_actualizados}"
        )
        self.stdout.write(
            f"Componentes asignados: "
            f"{total_componentes_asignados}"
        )
        self.stdout.write(
            f"Hosts no encontrados: "
            f"{len(hosts_no_encontrados)}"
        )

        if hosts_no_encontrados:
            self.stdout.write(
                self.style.WARNING(
                    "IDs no encontrados: "
                    + ", ".join(hosts_no_encontrados)
                )
            )