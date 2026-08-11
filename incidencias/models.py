import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def generar_codigo_incidencia():
    """
    Genera un código único de incidencia.
    Ejemplo: FZT-INC-20260629-A1B2C3
    """
    fecha = timezone.now().strftime("%Y%m%d")
    aleatorio = uuid.uuid4().hex[:6].upper()
    return f"FZT-INC-{fecha}-{aleatorio}"


def calcular_minutos(fecha_inicio, fecha_fin):
    """
    Calcula diferencia en minutos entre dos fechas.
    """
    if fecha_inicio and fecha_fin:
        return round((fecha_fin - fecha_inicio).total_seconds() / 60, 2)
    return None


def prioridad_por_severidad(severidad):
    """
    Mapea severidad técnica a prioridad operativa.
    """
    mapa = {
        "INFORMATIVA": "BAJA",
        "BAJA": "BAJA",
        "MEDIA": "MEDIA",
        "ALTA": "ALTA",
        "CRITICA": "URGENTE",
    }
    return mapa.get(severidad, "MEDIA")


# =====================================================
# CHOICES
# =====================================================

class RolUsuario(models.TextChoices):
    ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
    GESTOR_NOC = "GESTOR_NOC", "Gestor NOC"
    TECNICO = "TECNICO", "Técnico"
    SUPERVISOR = "SUPERVISOR", "Supervisor"
    VENDEDOR = "VENDEDOR", "Vendedor"
    DUENO = "DUENO", "Dueño"


class EstadoGeneral(models.TextChoices):
    ACTIVO = "ACTIVO", "Activo"
    INACTIVO = "INACTIVO", "Inactivo"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"


class Criticidad(models.TextChoices):
    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"
    CRITICA = "CRITICA", "Crítica"


class TipoComponenteRed(models.TextChoices):
    ROUTER_PRINCIPAL = "ROUTER_PRINCIPAL", "Router principal"
    ROUTER = "ROUTER", "Router"
    SWITCH = "SWITCH", "Switch"
    RADIO_AP = "RADIO_AP", "Radio AP / Sectorial"
    BACKHAUL = "BACKHAUL", "Backhaul"
    UPS = "UPS", "UPS / Energía"
    FIREWALL = "FIREWALL", "Firewall"
    OLT = "OLT", "OLT"
    SERVIDOR = "SERVIDOR", "Servidor"
    OTRO = "OTRO", "Otro"


class FuncionComponenteRed(models.TextChoices):
    NODO_PRINCIPAL = "NODO_PRINCIPAL", "Nodo principal"
    SECTORIAL = "SECTORIAL", "Sectorial"
    TRANSPORTE = "TRANSPORTE", "Transporte"
    DISTRIBUCION = "DISTRIBUCION", "Distribución"
    ENERGIA = "ENERGIA", "Energía"
    SEGURIDAD = "SEGURIDAD", "Seguridad"
    MONITOREO = "MONITOREO", "Monitoreo"
    OTRO = "OTRO", "Otro"


class EstadoOperativo(models.TextChoices):
    OPERATIVO = "OPERATIVO", "Operativo"
    CAIDO = "CAIDO", "Caído"
    MANTENIMIENTO = "MANTENIMIENTO", "Mantenimiento"
    RETIRADO = "RETIRADO", "Retirado"


class ImpactoPorCaida(models.TextChoices):
    NODO_COMPLETO = "NODO_COMPLETO", "Nodo completo"
    SECTORIAL = "SECTORIAL", "Sectorial"
    COMPONENTE = "COMPONENTE", "Componente específico"


class Severidad(models.TextChoices):
    INFORMATIVA = "INFORMATIVA", "Informativa"
    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"
    CRITICA = "CRITICA", "Crítica"


class Prioridad(models.TextChoices):
    BAJA = "BAJA", "Baja"
    MEDIA = "MEDIA", "Media"
    ALTA = "ALTA", "Alta"
    URGENTE = "URGENTE", "Urgente"


class EstadoZabbix(models.TextChoices):
    PROBLEM = "PROBLEM", "Problema"
    RESOLVED = "RESOLVED", "Resuelto"


class OrigenIncidencia(models.TextChoices):
    ZABBIX = "ZABBIX", "Zabbix"
    MANUAL = "MANUAL", "Manual"
    CORREO = "CORREO", "Correo"
    TELEFONO = "TELEFONO", "Teléfono"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    OTRO = "OTRO", "Otro"


class EstadoIncidencia(models.TextChoices):
    DETECTADA = "DETECTADA", "Detectada"
    REGISTRADA = "REGISTRADA", "Registrada"
    ASIGNADA = "ASIGNADA", "Asignada"
    EN_ATENCION = "EN_ATENCION", "En atención"
    RESUELTA = "RESUELTA", "Resuelta"
    CERRADA = "CERRADA", "Cerrada"
    CANCELADA = "CANCELADA", "Cancelada"


class TipoImpacto(models.TextChoices):
    DIRECTO = "DIRECTO", "Directo"
    INDIRECTO = "INDIRECTO", "Indirecto"


class MedioNotificacion(models.TextChoices):
    SISTEMA = "SISTEMA", "Sistema"
    CORREO = "CORREO", "Correo"
    WHATSAPP = "WHATSAPP", "WhatsApp"
    TELEFONO = "TELEFONO", "Teléfono"
    ZABBIX = "ZABBIX", "Zabbix"
    OTRO = "OTRO", "Otro"


class EstadoNotificacion(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    ENVIADA = "ENVIADA", "Enviada"
    FALLIDA = "FALLIDA", "Fallida"


class AccionHistorial(models.TextChoices):
    CREACION = "CREACION", "Creación"
    ASIGNACION = "ASIGNACION", "Asignación"
    REASIGNACION = "REASIGNACION", "Reasignación"
    NOTIFICACION = "NOTIFICACION", "Notificación"
    CAMBIO_ESTADO = "CAMBIO_ESTADO", "Cambio de estado"
    CAMBIO_SEVERIDAD = "CAMBIO_SEVERIDAD", "Cambio de severidad"
    ATENCION = "ATENCION", "Atención"
    DIAGNOSTICO = "DIAGNOSTICO", "Diagnóstico"
    RESOLUCION = "RESOLUCION", "Resolución"
    CIERRE = "CIERRE", "Cierre"
    CANCELACION = "CANCELACION", "Cancelación"
    COMENTARIO = "COMENTARIO", "Comentario"
    EVIDENCIA = "EVIDENCIA", "Evidencia"


class TipoComentario(models.TextChoices):
    SEGUIMIENTO = "SEGUIMIENTO", "Seguimiento"
    DIAGNOSTICO = "DIAGNOSTICO", "Diagnóstico"
    SOLUCION = "SOLUCION", "Solución"
    ESCALAMIENTO = "ESCALAMIENTO", "Escalamiento"
    OBSERVACION = "OBSERVACION", "Observación"


class ProcesoZabbix(models.TextChoices):
    CONSULTA_ALERTAS = "CONSULTA_ALERTAS", "Consulta de alertas"
    CREACION_ALERTA = "CREACION_ALERTA", "Creación de alerta"
    CREACION_INCIDENCIA = "CREACION_INCIDENCIA", "Creación de incidencia"
    ACTUALIZACION_ALERTA = "ACTUALIZACION_ALERTA", "Actualización de alerta"
    ACTUALIZACION_INCIDENCIA = "ACTUALIZACION_INCIDENCIA", "Actualización de incidencia"
    SINCRONIZACION_HOSTS = "SINCRONIZACION_HOSTS", "Sincronización de hosts"


class EstadoLogIntegracion(models.TextChoices):
    EXITOSO = "EXITOSO", "Exitoso"
    ERROR = "ERROR", "Error"
    PARCIAL = "PARCIAL", "Parcial"


# =====================================================
# MODELOS ABSTRACTOS
# =====================================================

class ModeloAuditoria(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(class)s_creados",
        blank=True,
        null=True
    )
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="%(class)s_actualizados",
        blank=True,
        null=True
    )

    class Meta:
        abstract = True


class ModeloCatalogo(ModeloAuditoria):
    activo = models.BooleanField(default=True)

    class Meta:
        abstract = True


# =====================================================
# 1. PERFIL USUARIO
# =====================================================

class PerfilUsuario(ModeloCatalogo):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_incidencias"
    )
    rol = models.CharField(
        max_length=30,
        choices=RolUsuario.choices,
        default=RolUsuario.TECNICO
    )
    telefono = models.CharField(max_length=30, blank=True, null=True)
    cargo = models.CharField(max_length=100, blank=True, null=True)
    area = models.CharField(max_length=100, blank=True, null=True)
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuarios"
        ordering = ["user__username"]
        indexes = [
            models.Index(fields=["rol"]),
            models.Index(fields=["activo"]),
            models.Index(fields=["disponible"]),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.get_rol_display()}"


# =====================================================
# 2. UBICACION
# =====================================================

class Ubicacion(ModeloCatalogo):
    nombre = models.CharField(max_length=150)
    departamento = models.CharField(max_length=100, blank=True, null=True)
    provincia = models.CharField(max_length=100, blank=True, null=True)
    distrito = models.CharField(max_length=100, blank=True, null=True)
    direccion_referencia = models.CharField(max_length=255, blank=True, null=True)

    latitud = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Ubicación"
        verbose_name_plural = "Ubicaciones"
        ordering = ["departamento", "provincia", "distrito", "nombre"]
        indexes = [
            models.Index(fields=["departamento"]),
            models.Index(fields=["provincia"]),
            models.Index(fields=["distrito"]),
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(latitud__isnull=True) | (Q(latitud__gte=-90) & Q(latitud__lte=90)),
                name="ubicacion_latitud_valida"
            ),
            models.CheckConstraint(
                condition=Q(longitud__isnull=True) | (Q(longitud__gte=-180) & Q(longitud__lte=180)),
                name="ubicacion_longitud_valida"
            ),
        ]

    def __str__(self):
        return self.nombre


# =====================================================
# 3. NODO
# =====================================================

class Nodo(ModeloCatalogo):
    ubicacion = models.ForeignKey(
        Ubicacion,
        on_delete=models.PROTECT,
        related_name="nodos"
    )

    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)

    direccion_referencia = models.CharField(max_length=255, blank=True, null=True)
    latitud = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)

    estado = models.CharField(
        max_length=30,
        choices=EstadoGeneral.choices,
        default=EstadoGeneral.ACTIVO
    )
    criticidad = models.CharField(
        max_length=30,
        choices=Criticidad.choices,
        default=Criticidad.MEDIA
    )

    clientes_estimados = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Nodo"
        verbose_name_plural = "Nodos"
        ordering = ["codigo"]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["nombre"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["criticidad"]),
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(latitud__isnull=True) | (Q(latitud__gte=-90) & Q(latitud__lte=90)),
                name="nodo_latitud_valida"
            ),
            models.CheckConstraint(
                condition=Q(longitud__isnull=True) | (Q(longitud__gte=-180) & Q(longitud__lte=180)),
                name="nodo_longitud_valida"
            ),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


# =====================================================
# 4. COMPONENTE RED
# =====================================================

class ComponenteRed(ModeloCatalogo):
    nodo = models.ForeignKey(
        Nodo,
        on_delete=models.PROTECT,
        related_name="componentes_red"
    )

    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=150)

    tipo = models.CharField(
        max_length=30,
        choices=TipoComponenteRed.choices
    )
    funcion = models.CharField(
        max_length=30,
        choices=FuncionComponenteRed.choices,
        default=FuncionComponenteRed.OTRO
    )

    ip_gestion = models.GenericIPAddressField(
        protocol="both",
        unpack_ipv4=True,
        unique=True,
        blank=True,
        null=True
    )
    mac_address = models.CharField(max_length=17, blank=True, null=True)

    fabricante = models.CharField(max_length=100, blank=True, null=True)
    modelo = models.CharField(max_length=100, blank=True, null=True)
    numero_serie = models.CharField(max_length=100, blank=True, null=True)

    host_id_zabbix = models.CharField(max_length=100, unique=True, blank=True, null=True)
    es_monitoreado_zabbix = models.BooleanField(default=True)

    impacto_por_caida = models.CharField(
        max_length=30,
        choices=ImpactoPorCaida.choices,
        default=ImpactoPorCaida.COMPONENTE
    )

    estado_operativo = models.CharField(
        max_length=30,
        choices=EstadoOperativo.choices,
        default=EstadoOperativo.OPERATIVO
    )
    criticidad = models.CharField(
        max_length=30,
        choices=Criticidad.choices,
        default=Criticidad.MEDIA
    )

    clientes_estimados = models.PositiveIntegerField(default=0)
    datos_tecnicos_json = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Componente de red"
        verbose_name_plural = "Componentes de red"
        ordering = ["nodo", "codigo"]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["nombre"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["funcion"]),
            models.Index(fields=["host_id_zabbix"]),
            models.Index(fields=["estado_operativo"]),
            models.Index(fields=["criticidad"]),
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["nodo", "codigo"],
                name="unique_componente_red_por_nodo"
            ),
        ]

    def clean(self):
        if self.es_monitoreado_zabbix and not self.host_id_zabbix:
            raise ValidationError(
                "Si el componente es monitoreado por Zabbix, debe tener host_id_zabbix."
            )

        if self.impacto_por_caida == ImpactoPorCaida.NODO_COMPLETO:
            if self.funcion != FuncionComponenteRed.NODO_PRINCIPAL:
                raise ValidationError(
                    "Un componente que afecta al nodo completo debe tener función 'Nodo principal'."
                )

        if self.funcion == FuncionComponenteRed.SECTORIAL:
            if self.impacto_por_caida != ImpactoPorCaida.SECTORIAL:
                raise ValidationError(
                    "Un componente con función sectorial debe tener impacto por caída 'Sectorial'."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nodo.codigo} - {self.codigo} - {self.nombre}"


# =====================================================
# 5. CATEGORIA INCIDENCIA
# =====================================================

class CategoriaIncidencia(ModeloCatalogo):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Categoría de incidencia"
        verbose_name_plural = "Categorías de incidencias"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["activo"]),
        ]

    def __str__(self):
        return self.nombre


# =====================================================
# 6. SLA INCIDENCIA
# =====================================================

class SLAIncidencia(ModeloCatalogo):
    severidad = models.CharField(
        max_length=30,
        choices=Severidad.choices,
        unique=True
    )
    nombre = models.CharField(max_length=100)

    tiempo_max_registro_min = models.PositiveIntegerField(default=10)
    tiempo_max_asignacion_min = models.PositiveIntegerField(default=15)
    tiempo_max_inicio_atencion_min = models.PositiveIntegerField(default=30)
    tiempo_max_resolucion_min = models.PositiveIntegerField()

    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "SLA de incidencia"
        verbose_name_plural = "SLAs de incidencias"
        ordering = ["severidad"]
        indexes = [
            models.Index(fields=["severidad"]),
            models.Index(fields=["activo"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(tiempo_max_registro_min__gt=0),
                name="sla_registro_mayor_cero"
            ),
            models.CheckConstraint(
                condition=Q(tiempo_max_asignacion_min__gt=0),
                name="sla_asignacion_mayor_cero"
            ),
            models.CheckConstraint(
                condition=Q(tiempo_max_inicio_atencion_min__gt=0),
                name="sla_inicio_atencion_mayor_cero"
            ),
            models.CheckConstraint(
                condition=Q(tiempo_max_resolucion_min__gt=0),
                name="sla_resolucion_mayor_cero"
            ),
        ]

    def __str__(self):
        return f"{self.get_severidad_display()} - {self.nombre}"

# =====================================================
# 7. CONFIGURACION ZABBIX
# =====================================================
class ConfiguracionZabbix(ModeloCatalogo):
    nombre = models.CharField(
        max_length=100,
        default="Servidor Zabbix Principal"
    )

    url_api = models.URLField(
        max_length=255,
        help_text="URL de la API de Zabbix. Ejemplo: http://192.168.1.10/zabbix/api_jsonrpc.php"
    )

    usuario = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    password = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    token_api = models.TextField(
        blank=True,
        null=True,
        help_text="Token API de Zabbix, si se usa autenticación por token."
    )

    usar_token = models.BooleanField(default=False)

    ultima_prueba_conexion = models.DateTimeField(
        blank=True,
        null=True
    )

    conexion_exitosa = models.BooleanField(default=False)

    mensaje_ultima_prueba = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        verbose_name = "Configuración Zabbix"
        verbose_name_plural = "Configuraciones Zabbix"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["activo"]),
            models.Index(fields=["conexion_exitosa"]),
        ]

    def clean(self):
        if self.usar_token:
            if not self.token_api:
                raise ValidationError(
                    "Debe ingresar el token API si selecciona autenticación por token."
                )
        else:
            if not self.usuario or not self.password:
                raise ValidationError(
                    "Debe ingresar usuario y contraseña si no usa token API."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre
# =====================================================
# 8. ALERTA ZABBIX
# =====================================================

class AlertaZabbix(ModeloAuditoria):
    componente_red = models.ForeignKey(
        ComponenteRed,
        on_delete=models.PROTECT,
        related_name="alertas_zabbix"
    )

    event_id = models.CharField(max_length=100, unique=True)
    trigger_id = models.CharField(max_length=100, blank=True, null=True)
    problem_id = models.CharField(max_length=100, blank=True, null=True)
    recovery_event_id = models.CharField(max_length=100, blank=True, null=True)
    host_id = models.CharField(max_length=100)

    nombre_alerta = models.CharField(max_length=255)
    descripcion = models.TextField(blank=True, null=True)

    severidad = models.CharField(
        max_length=30,
        choices=Severidad.choices,
        default=Severidad.MEDIA
    )
    estado_zabbix = models.CharField(
        max_length=30,
        choices=EstadoZabbix.choices,
        default=EstadoZabbix.PROBLEM
    )

    fecha_evento = models.DateTimeField()
    fecha_recuperacion = models.DateTimeField(blank=True, null=True)
    fecha_recepcion_sistema = models.DateTimeField(default=timezone.now)

    acknowledged = models.BooleanField(default=False)
    procesada = models.BooleanField(default=False)

    datos_json = models.JSONField(blank=True, null=True)
    tags_json = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Alerta Zabbix"
        verbose_name_plural = "Alertas Zabbix"
        ordering = ["-fecha_evento"]
        indexes = [
            models.Index(fields=["event_id"]),
            models.Index(fields=["trigger_id"]),
            models.Index(fields=["problem_id"]),
            models.Index(fields=["host_id"]),
            models.Index(fields=["estado_zabbix"]),
            models.Index(fields=["severidad"]),
            models.Index(fields=["fecha_evento"]),
            models.Index(fields=["procesada"]),
        ]

    def clean(self):
        if not self.componente_red.activo:
            raise ValidationError(
                "No se puede registrar una alerta sobre un componente de red inactivo."
            )

        if not self.componente_red.es_monitoreado_zabbix:
            raise ValidationError(
                "El componente de red no está marcado como monitoreado por Zabbix."
            )

        if self.componente_red.host_id_zabbix != self.host_id:
            raise ValidationError(
                "El host_id de la alerta no coincide con el host_id_zabbix del componente de red."
            )

        if self.fecha_recuperacion and self.fecha_recuperacion < self.fecha_evento:
            raise ValidationError(
                "La fecha de recuperación no puede ser menor que la fecha del evento."
            )

        if self.estado_zabbix == EstadoZabbix.RESOLVED and not self.fecha_recuperacion:
            raise ValidationError(
                "Una alerta resuelta debe tener fecha de recuperación."
            )

    def save(self, *args, **kwargs):
        severidad_anterior = None

        if self.pk:
            severidad_anterior = (
                AlertaZabbix.objects
                .filter(pk=self.pk)
                .values_list("severidad", flat=True)
                .first()
            )

        self.full_clean()
        super().save(*args, **kwargs)

        if severidad_anterior and severidad_anterior != self.severidad:
            try:
                incidencia = self.incidencia
            except Incidencia.DoesNotExist:
                incidencia = None

            if incidencia and incidencia.estado not in [
                EstadoIncidencia.CERRADA,
                EstadoIncidencia.CANCELADA,
            ]:
                estado_anterior = incidencia.estado
                severidad_antigua = incidencia.severidad

                incidencia.severidad = self.severidad
                incidencia.prioridad = prioridad_por_severidad(self.severidad)
                incidencia.asignar_sla_por_severidad()
                incidencia.save()

                HistorialIncidencia.objects.create(
                    incidencia=incidencia,
                    accion=AccionHistorial.CAMBIO_SEVERIDAD,
                    estado_anterior=estado_anterior,
                    estado_nuevo=incidencia.estado,
                    descripcion=(
                        f"Se actualizó la severidad desde Zabbix: "
                        f"{severidad_antigua} → {self.severidad}."
                    )
                )

    def __str__(self):
        return f"{self.event_id} - {self.nombre_alerta}"


# =====================================================
# 9. INCIDENCIA
# =====================================================

class Incidencia(ModeloAuditoria):
    alerta_zabbix = models.OneToOneField(
        AlertaZabbix,
        on_delete=models.SET_NULL,
        related_name="incidencia",
        blank=True,
        null=True
    )

    nodo_afectado = models.ForeignKey(
        Nodo,
        on_delete=models.PROTECT,
        related_name="incidencias"
    )

    componente_principal = models.ForeignKey(
        ComponenteRed,
        on_delete=models.PROTECT,
        related_name="incidencias_principales",
        blank=True,
        null=True
    )

    categoria = models.ForeignKey(
        CategoriaIncidencia,
        on_delete=models.PROTECT,
        related_name="incidencias",
        blank=True,
        null=True
    )

    sla = models.ForeignKey(
        SLAIncidencia,
        on_delete=models.PROTECT,
        related_name="incidencias",
        blank=True,
        null=True
    )

    tecnico_asignado = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="incidencias_asignadas",
        blank=True,
        null=True
    )

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="incidencias_registradas",
        blank=True,
        null=True
    )

    codigo = models.CharField(
        max_length=40,
        unique=True,
        default=generar_codigo_incidencia,
        editable=False
    )

    ticket_externo = models.CharField(max_length=100, blank=True, null=True)

    titulo = models.CharField(max_length=255)
    descripcion = models.TextField()

    origen = models.CharField(
        max_length=30,
        choices=OrigenIncidencia.choices,
        default=OrigenIncidencia.ZABBIX
    )

    tipo_afectacion = models.CharField(
        max_length=30,
        choices=ImpactoPorCaida.choices,
        default=ImpactoPorCaida.COMPONENTE
    )

    severidad = models.CharField(
        max_length=30,
        choices=Severidad.choices,
        default=Severidad.MEDIA
    )

    prioridad = models.CharField(
        max_length=30,
        choices=Prioridad.choices,
        default=Prioridad.MEDIA
    )

    estado = models.CharField(
        max_length=30,
        choices=EstadoIncidencia.choices,
        default=EstadoIncidencia.DETECTADA
    )

    clientes_afectados_estimados = models.PositiveIntegerField(default=0)

    fecha_deteccion = models.DateTimeField(default=timezone.now)
    fecha_registro = models.DateTimeField(default=timezone.now)
    fecha_asignacion = models.DateTimeField(blank=True, null=True)
    fecha_inicio_atencion = models.DateTimeField(blank=True, null=True)
    fecha_resolucion = models.DateTimeField(blank=True, null=True)
    fecha_cierre = models.DateTimeField(blank=True, null=True)

    solucion = models.TextField(blank=True, null=True)
    causa_raiz = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)

    cumple_sla_registro = models.BooleanField(blank=True, null=True)
    cumple_sla_asignacion = models.BooleanField(blank=True, null=True)
    cumple_sla_inicio_atencion = models.BooleanField(blank=True, null=True)
    cumple_sla_resolucion = models.BooleanField(blank=True, null=True)

    componentes_afectados = models.ManyToManyField(
        ComponenteRed,
        through="IncidenciaComponenteAfectado",
        related_name="incidencias_afectadas",
        blank=True
    )

    class Meta:
        verbose_name = "Incidencia"
        verbose_name_plural = "Incidencias"
        ordering = ["-fecha_registro"]
        indexes = [
            models.Index(fields=["codigo"]),
            models.Index(fields=["ticket_externo"]),
            models.Index(fields=["origen"]),
            models.Index(fields=["tipo_afectacion"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["severidad"]),
            models.Index(fields=["prioridad"]),
            models.Index(fields=["fecha_deteccion"]),
            models.Index(fields=["fecha_registro"]),
            models.Index(fields=["fecha_asignacion"]),
            models.Index(fields=["fecha_inicio_atencion"]),
            models.Index(fields=["fecha_resolucion"]),
            models.Index(fields=["fecha_cierre"]),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.titulo}"

    def sincronizar_desde_alerta(self):
        if not self.alerta_zabbix:
            return

        componente = self.alerta_zabbix.componente_red

        self.origen = OrigenIncidencia.ZABBIX
        self.componente_principal = componente
        self.nodo_afectado = componente.nodo
        self.severidad = self.alerta_zabbix.severidad
        self.prioridad = prioridad_por_severidad(self.severidad)
        self.fecha_deteccion = self.alerta_zabbix.fecha_evento

        self.tipo_afectacion = componente.impacto_por_caida

        if not self.titulo:
            self.titulo = self.alerta_zabbix.nombre_alerta

        if not self.descripcion:
            self.descripcion = self.alerta_zabbix.descripcion or self.alerta_zabbix.nombre_alerta

    def asignar_sla_por_severidad(self):
        self.sla = SLAIncidencia.objects.filter(
            severidad=self.severidad,
            activo=True
        ).first()

    def calcular_clientes_afectados(self):
        if self.tipo_afectacion == ImpactoPorCaida.NODO_COMPLETO:
            self.clientes_afectados_estimados = self.nodo_afectado.clientes_estimados
        elif self.componente_principal:
            self.clientes_afectados_estimados = self.componente_principal.clientes_estimados

    def evaluar_sla(self):
        if not self.sla:
            self.cumple_sla_registro = None
            self.cumple_sla_asignacion = None
            self.cumple_sla_inicio_atencion = None
            self.cumple_sla_resolucion = None
            return

        minutos_registro = calcular_minutos(self.fecha_deteccion, self.fecha_registro)
        if minutos_registro is not None:
            self.cumple_sla_registro = minutos_registro <= self.sla.tiempo_max_registro_min

        minutos_asignacion = calcular_minutos(self.fecha_registro, self.fecha_asignacion)
        if minutos_asignacion is not None:
            self.cumple_sla_asignacion = minutos_asignacion <= self.sla.tiempo_max_asignacion_min

        minutos_inicio = calcular_minutos(self.fecha_asignacion, self.fecha_inicio_atencion)
        if minutos_inicio is not None:
            self.cumple_sla_inicio_atencion = minutos_inicio <= self.sla.tiempo_max_inicio_atencion_min

        minutos_resolucion = calcular_minutos(self.fecha_deteccion, self.fecha_resolucion)
        if minutos_resolucion is not None:
            self.cumple_sla_resolucion = minutos_resolucion <= self.sla.tiempo_max_resolucion_min

    def validar_fechas(self):
        if self.fecha_registro and self.fecha_registro < self.fecha_deteccion:
            raise ValidationError("La fecha de registro no puede ser menor que la fecha de detección.")

        if self.fecha_asignacion and self.fecha_asignacion < self.fecha_registro:
            raise ValidationError("La fecha de asignación no puede ser menor que la fecha de registro.")

        if self.fecha_inicio_atencion:
            referencia = self.fecha_asignacion or self.fecha_registro
            if self.fecha_inicio_atencion < referencia:
                raise ValidationError(
                    "La fecha de inicio de atención no puede ser menor que la fecha de asignación o registro."
                )

        if self.fecha_resolucion and self.fecha_resolucion < self.fecha_deteccion:
            raise ValidationError("La fecha de resolución no puede ser menor que la fecha de detección.")

        if self.fecha_cierre:
            referencia = self.fecha_resolucion or self.fecha_deteccion
            if self.fecha_cierre < referencia:
                raise ValidationError("La fecha de cierre no puede ser menor que la fecha de resolución.")

    def clean(self):
        if self.pk:
            estado_anterior = (
                Incidencia.objects
                .filter(pk=self.pk)
                .values_list("estado", flat=True)
                .first()
            )
            if estado_anterior == EstadoIncidencia.CERRADA and self.estado != EstadoIncidencia.CERRADA:
                raise ValidationError(
                    "Una incidencia cerrada no puede reabrirse. Debe registrarse una nueva incidencia."
                )

        if self.origen == OrigenIncidencia.ZABBIX and not self.alerta_zabbix:
            raise ValidationError("Una incidencia de origen Zabbix debe tener una alerta asociada.")

        if self.alerta_zabbix and self.alerta_zabbix.componente_red.nodo_id != self.nodo_afectado_id:
            raise ValidationError("La alerta Zabbix no pertenece al nodo afectado.")

        if self.componente_principal and self.componente_principal.nodo_id != self.nodo_afectado_id:
            raise ValidationError("El componente principal no pertenece al nodo afectado.")

        if self.tipo_afectacion in [ImpactoPorCaida.SECTORIAL, ImpactoPorCaida.COMPONENTE]:
            if not self.componente_principal:
                raise ValidationError(
                    "Las incidencias de componente o sectorial deben tener componente principal."
                )

        if self.estado in [
            EstadoIncidencia.ASIGNADA,
            EstadoIncidencia.EN_ATENCION,
            EstadoIncidencia.RESUELTA,
            EstadoIncidencia.CERRADA,
        ]:
            if not self.tecnico_asignado:
                raise ValidationError("La incidencia debe tener un técnico asignado.")

        if self.estado in [EstadoIncidencia.ASIGNADA, EstadoIncidencia.EN_ATENCION]:
            if not self.fecha_asignacion:
                raise ValidationError("Una incidencia asignada debe tener fecha de asignación.")

        if self.estado == EstadoIncidencia.EN_ATENCION and not self.fecha_inicio_atencion:
            raise ValidationError("Una incidencia en atención debe tener fecha de inicio de atención.")

        if self.estado in [EstadoIncidencia.RESUELTA, EstadoIncidencia.CERRADA]:
            if not self.fecha_resolucion:
                raise ValidationError("Una incidencia resuelta o cerrada debe tener fecha de resolución.")
            if not self.solucion:
                raise ValidationError("Una incidencia resuelta o cerrada debe tener solución registrada.")

        if self.estado == EstadoIncidencia.CERRADA and not self.fecha_cierre:
            raise ValidationError("Una incidencia cerrada debe tener fecha de cierre.")

        self.validar_fechas()

    def save(self, *args, **kwargs):
        self.sincronizar_desde_alerta()

        if not self.prioridad:
            self.prioridad = prioridad_por_severidad(self.severidad)

        if not self.sla:
            self.asignar_sla_por_severidad()

        if self.nodo_afectado and self.clientes_afectados_estimados == 0:
            self.calcular_clientes_afectados()

        self.evaluar_sla()
        self.full_clean()
        super().save(*args, **kwargs)
        self.registrar_afectaciones_automaticas()

    def registrar_afectaciones_automaticas(self):
        """
        Si cae el nodo completo, se registran como afectados todos sus componentes activos.
        Si cae un componente o sectorial, se registra solo el componente principal.
        """
        if self.tipo_afectacion == ImpactoPorCaida.NODO_COMPLETO:
            componentes = self.nodo_afectado.componentes_red.filter(activo=True)

            for componente in componentes:
                IncidenciaComponenteAfectado.objects.get_or_create(
                    incidencia=self,
                    componente_red=componente,
                    defaults={
                        "tipo_impacto": TipoImpacto.DIRECTO
                    }
                )

        elif self.componente_principal:
            IncidenciaComponenteAfectado.objects.get_or_create(
                incidencia=self,
                componente_red=self.componente_principal,
                defaults={
                    "tipo_impacto": TipoImpacto.DIRECTO
                }
            )

    @property
    def tiempo_registro_min(self):
        return calcular_minutos(self.fecha_deteccion, self.fecha_registro)

    @property
    def tiempo_asignacion_min(self):
        return calcular_minutos(self.fecha_registro, self.fecha_asignacion)

    @property
    def tiempo_inicio_atencion_min(self):
        return calcular_minutos(self.fecha_asignacion, self.fecha_inicio_atencion)

    @property
    def tiempo_resolucion_min(self):
        return calcular_minutos(self.fecha_deteccion, self.fecha_resolucion)

    @property
    def tiempo_cierre_min(self):
        return calcular_minutos(self.fecha_deteccion, self.fecha_cierre)


# =====================================================
# 10. INCIDENCIA COMPONENTE AFECTADO
# =====================================================

class IncidenciaComponenteAfectado(ModeloAuditoria):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name="componentes_afectados_detalle"
    )
    componente_red = models.ForeignKey(
        ComponenteRed,
        on_delete=models.PROTECT,
        related_name="afectaciones"
    )

    tipo_impacto = models.CharField(
        max_length=30,
        choices=TipoImpacto.choices,
        default=TipoImpacto.DIRECTO
    )

    observacion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Componente afectado"
        verbose_name_plural = "Componentes afectados"
        ordering = ["incidencia", "componente_red"]
        constraints = [
            models.UniqueConstraint(
                fields=["incidencia", "componente_red"],
                name="unique_componente_afectado_por_incidencia"
            )
        ]
        indexes = [
            models.Index(fields=["tipo_impacto"]),
        ]

    def clean(self):
        if self.componente_red.nodo_id != self.incidencia.nodo_afectado_id:
            raise ValidationError(
                "El componente afectado no pertenece al nodo de la incidencia."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.incidencia.codigo} - {self.componente_red.nombre}"


# =====================================================
# 11. ASIGNACION INCIDENCIA
# =====================================================

class AsignacionIncidencia(ModeloAuditoria):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name="asignaciones"
    )

    tecnico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones_recibidas"
    )

    asignado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="asignaciones_realizadas",
        blank=True,
        null=True
    )

    fecha_asignacion = models.DateTimeField(default=timezone.now)
    comentario = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Asignación de incidencia"
        verbose_name_plural = "Asignaciones de incidencias"
        ordering = ["-fecha_asignacion"]
        indexes = [
            models.Index(fields=["fecha_asignacion"]),
            models.Index(fields=["activo"]),
        ]

    def clean(self):
        if not self.incidencia_id:
            raise ValidationError(
                "La asignación debe estar asociada a una incidencia."
            )

        if not self.tecnico_id:
            raise ValidationError(
                "Debe seleccionar un técnico responsable."
            )

        if self.incidencia.estado in [
            EstadoIncidencia.CERRADA,
            EstadoIncidencia.CANCELADA,
        ]:
            raise ValidationError(
                "No se puede asignar una incidencia cerrada o cancelada."
            )

        # No se valida por RolUsuario. Basta con que el usuario esté activo.
        if not self.tecnico.is_active:
            raise ValidationError(
                "El usuario seleccionado se encuentra inactivo."
            )

        # Si existe perfil, se respetan únicamente sus banderas operativas.
        perfil = getattr(self.tecnico, "perfil_incidencias", None)

        if perfil:
            if not perfil.activo:
                raise ValidationError(
                    "El perfil del técnico se encuentra inactivo."
                )

            if not perfil.disponible:
                raise ValidationError(
                    "El técnico seleccionado no se encuentra disponible."
                )

    def save(self, *args, **kwargs):
        self.full_clean()

        incidencia = self.incidencia
        tecnico_anterior = incidencia.tecnico_asignado
        estado_anterior = incidencia.estado

        # Una sola asignación activa. Al reasignar, la anterior queda inactiva.
        if self.activo:
            AsignacionIncidencia.objects.filter(
                incidencia=incidencia,
                activo=True,
            ).exclude(pk=self.pk).update(activo=False)

        super().save(*args, **kwargs)

        incidencia.tecnico_asignado = self.tecnico

        # La fecha de asignación de Incidencia representa la primera asignación
        # para conservar correctamente los indicadores/SLA.
        if not incidencia.fecha_asignacion:
            incidencia.fecha_asignacion = self.fecha_asignacion

        # Asignar por primera vez significa comenzar la atención inmediatamente.
        if incidencia.estado in [
            EstadoIncidencia.DETECTADA,
            EstadoIncidencia.REGISTRADA,
            EstadoIncidencia.ASIGNADA,
        ]:
            incidencia.estado = EstadoIncidencia.EN_ATENCION

            if not incidencia.fecha_inicio_atencion:
                incidencia.fecha_inicio_atencion = self.fecha_asignacion

        if self.asignado_por:
            incidencia.actualizado_por = self.asignado_por

        incidencia.save()

        es_reasignacion = (
            tecnico_anterior is not None
            and tecnico_anterior.pk != self.tecnico.pk
        )

        if es_reasignacion:
            accion = AccionHistorial.REASIGNACION
            descripcion = (
                f"Incidencia reasignada de {tecnico_anterior} "
                f"a {self.tecnico}."
            )

            if self.comentario:
                descripcion += f" Motivo: {self.comentario}"
        else:
            accion = AccionHistorial.ASIGNACION
            descripcion = (
                f"Incidencia asignada a {self.tecnico}. "
                "La atención inicia con la asignación."
            )

            if self.comentario:
                descripcion += f" Observación: {self.comentario}"

        historial_kwargs = {
            "incidencia": incidencia,
            "usuario": self.asignado_por,
            "accion": accion,
            "descripcion": descripcion,
            "creado_por": self.asignado_por,
            "actualizado_por": self.asignado_por,
        }

        # En una reasignación normalmente el estado sigue EN_ATENCION; evitamos
        # mostrar una transición redundante EN_ATENCION -> EN_ATENCION.
        if estado_anterior != incidencia.estado:
            historial_kwargs["estado_anterior"] = estado_anterior
            historial_kwargs["estado_nuevo"] = incidencia.estado

        HistorialIncidencia.objects.create(**historial_kwargs)

    def __str__(self):
        return f"{self.incidencia.codigo} → {self.tecnico}"


# =====================================================
# 12. NOTIFICACION INCIDENCIA
# =====================================================

class NotificacionIncidencia(ModeloAuditoria):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name="notificaciones"
    )

    usuario_destino = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="notificaciones_incidencia",
        blank=True,
        null=True
    )

    medio = models.CharField(
        max_length=30,
        choices=MedioNotificacion.choices,
        default=MedioNotificacion.SISTEMA
    )

    destinatario = models.CharField(max_length=150, blank=True, null=True)
    mensaje = models.TextField()

    estado = models.CharField(
        max_length=30,
        choices=EstadoNotificacion.choices,
        default=EstadoNotificacion.PENDIENTE
    )

    fecha_envio = models.DateTimeField(blank=True, null=True)
    error = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Notificación de incidencia"
        verbose_name_plural = "Notificaciones de incidencias"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["medio"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha_envio"]),
        ]

    def clean(self):
        if self.estado == EstadoNotificacion.ENVIADA and not self.fecha_envio:
            self.fecha_envio = timezone.now()

        if self.estado == EstadoNotificacion.FALLIDA and not self.error:
            raise ValidationError(
                "Una notificación fallida debe registrar el error."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        HistorialIncidencia.objects.create(
            incidencia=self.incidencia,
            usuario=self.creado_por,
            accion=AccionHistorial.NOTIFICACION,
            descripcion=f"Notificación registrada por {self.get_medio_display()} con estado {self.get_estado_display()}."
        )

    def __str__(self):
        return f"{self.incidencia.codigo} - {self.medio} - {self.estado}"


# =====================================================
# 13. HISTORIAL INCIDENCIA
# =====================================================

class HistorialIncidencia(ModeloAuditoria):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name="historial"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="historial_incidencias",
        blank=True,
        null=True
    )

    accion = models.CharField(
        max_length=100,
        choices=AccionHistorial.choices
    )

    estado_anterior = models.CharField(
        max_length=30,
        choices=EstadoIncidencia.choices,
        blank=True,
        null=True
    )

    estado_nuevo = models.CharField(
        max_length=30,
        choices=EstadoIncidencia.choices,
        blank=True,
        null=True
    )

    campo_modificado = models.CharField(max_length=100, blank=True, null=True)
    valor_anterior = models.TextField(blank=True, null=True)
    valor_nuevo = models.TextField(blank=True, null=True)

    descripcion = models.TextField(blank=True, null=True)
    fecha_evento = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Historial de incidencia"
        verbose_name_plural = "Historial de incidencias"
        ordering = ["-fecha_evento"]
        indexes = [
            models.Index(fields=["accion"]),
            models.Index(fields=["estado_anterior"]),
            models.Index(fields=["estado_nuevo"]),
            models.Index(fields=["fecha_evento"]),
        ]

    def __str__(self):
        return f"{self.incidencia.codigo} - {self.accion}"


# =====================================================
# 14. COMENTARIO INCIDENCIA
# =====================================================

class ComentarioIncidencia(ModeloAuditoria):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name="comentarios"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="comentarios_incidencias",
        blank=True,
        null=True
    )

    comentario = models.TextField()

    tipo_comentario = models.CharField(
        max_length=30,
        choices=TipoComentario.choices,
        default=TipoComentario.SEGUIMIENTO
    )

    class Meta:
        verbose_name = "Comentario de incidencia"
        verbose_name_plural = "Comentarios de incidencias"
        ordering = ["-creado_en"]
        indexes = [
            models.Index(fields=["tipo_comentario"]),
            models.Index(fields=["creado_en"]),
        ]

    def clean(self):
        if not self.incidencia_id:
            raise ValidationError(
                "El comentario debe estar asociado a una incidencia."
            )

        if self.incidencia.estado in [
            EstadoIncidencia.CERRADA,
            EstadoIncidencia.CANCELADA,
        ]:
            raise ValidationError(
                "No se pueden agregar registros a una incidencia cerrada o cancelada."
            )

        if not (self.comentario or "").strip():
            raise ValidationError(
                "Debe ingresar el detalle del registro."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        accion = AccionHistorial.COMENTARIO

        if self.tipo_comentario == TipoComentario.DIAGNOSTICO:
            accion = AccionHistorial.DIAGNOSTICO

        HistorialIncidencia.objects.create(
            incidencia=self.incidencia,
            usuario=self.usuario,
            accion=accion,
            descripcion=(
                f"{self.get_tipo_comentario_display()}: "
                f"{self.comentario}"
            ),
            creado_por=self.usuario,
            actualizado_por=self.usuario,
        )

    def __str__(self):
        return f"{self.incidencia.codigo} - {self.tipo_comentario}"


# =====================================================
# 15. EVIDENCIA INCIDENCIA
# =====================================================

class EvidenciaIncidencia(ModeloAuditoria):
    incidencia = models.ForeignKey(
        Incidencia,
        on_delete=models.CASCADE,
        related_name="evidencias"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="evidencias_incidencias",
        blank=True,
        null=True
    )

    archivo = models.FileField(upload_to="evidencias_incidencias/%Y/%m/")
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Evidencia de incidencia"
        verbose_name_plural = "Evidencias de incidencias"
        ordering = ["-creado_en"]

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

        HistorialIncidencia.objects.create(
            incidencia=self.incidencia,
            usuario=self.usuario,
            accion=AccionHistorial.EVIDENCIA,
            descripcion="Se agregó una evidencia a la incidencia."
        )

    def __str__(self):
        return f"{self.incidencia.codigo} - Evidencia"


# =====================================================
# 16. LOG INTEGRACION ZABBIX
# =====================================================

class LogIntegracionZabbix(ModeloAuditoria):
    proceso = models.CharField(
        max_length=100,
        choices=ProcesoZabbix.choices
    )

    estado = models.CharField(
        max_length=30,
        choices=EstadoLogIntegracion.choices
    )

    mensaje = models.TextField(blank=True, null=True)

    total_alertas = models.PositiveIntegerField(default=0)
    total_procesadas = models.PositiveIntegerField(default=0)
    total_errores = models.PositiveIntegerField(default=0)

    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(blank=True, null=True)

    detalle_json = models.JSONField(blank=True, null=True)

    class Meta:
        verbose_name = "Log de integración Zabbix"
        verbose_name_plural = "Logs de integración Zabbix"
        ordering = ["-fecha_inicio"]
        indexes = [
            models.Index(fields=["proceso"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha_inicio"]),
        ]

    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError(
                "La fecha fin no puede ser menor que la fecha inicio."
            )

        if self.estado == EstadoLogIntegracion.ERROR and self.total_errores == 0:
            self.total_errores = 1

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duracion_segundos(self):
        if self.fecha_inicio and self.fecha_fin:
            return round((self.fecha_fin - self.fecha_inicio).total_seconds(), 2)
        return None

    def __str__(self):
        return f"{self.proceso} - {self.estado}"