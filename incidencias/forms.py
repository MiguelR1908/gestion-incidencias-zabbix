from django import forms
from django.contrib.auth.models import User

from .models import PerfilUsuario, RolUsuario, Ubicacion, Nodo, ComponenteRed


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={
            "placeholder": "Ingrese una contraseña"
        }),
        required=False,
        help_text="Solo complete este campo si desea crear o cambiar la contraseña."
    )

    rol = forms.ChoiceField(
        label="Rol",
        choices=RolUsuario.choices
    )

    telefono = forms.CharField(
        label="Teléfono",
        required=False,
        max_length=20
    )

    cargo = forms.CharField(
        label="Cargo",
        required=False,
        max_length=100
    )

    area = forms.CharField(
        label="Área",
        required=False,
        max_length=100
    )

    disponible = forms.BooleanField(
        label="Disponible",
        required=False,
        initial=True
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
        ]

        labels = {
            "username": "Usuario",
            "first_name": "Nombres",
            "last_name": "Apellidos",
            "email": "Correo electrónico",
            "is_active": "Usuario activo",
        }

    def __init__(self, *args, **kwargs):
        self.perfil = kwargs.pop("perfil", None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

        if self.instance and self.instance.pk:
            self.fields["password"].required = False

            if self.perfil:
                self.fields["rol"].initial = self.perfil.rol
                self.fields["telefono"].initial = self.perfil.telefono
                self.fields["cargo"].initial = self.perfil.cargo
                self.fields["area"].initial = self.perfil.area
                self.fields["disponible"].initial = self.perfil.disponible
        else:
            self.fields["password"].required = True

    def clean_username(self):
        username = self.cleaned_data.get("username")

        qs = User.objects.filter(username=username)

        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError("Ya existe un usuario con este nombre.")

        return username

    def clean_email(self):
        email = self.cleaned_data.get("email")

        if email:
            qs = User.objects.filter(email=email)

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Ya existe un usuario con este correo.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)

        password = self.cleaned_data.get("password")

        if password:
            user.set_password(password)

        rol = self.cleaned_data.get("rol")

        if rol in [
            RolUsuario.ADMINISTRADOR,
            RolUsuario.GESTOR_NOC,
            RolUsuario.SUPERVISOR,
        ]:
            user.is_staff = True
        else:
            user.is_staff = False

        if rol == RolUsuario.ADMINISTRADOR:
            user.is_superuser = True
        else:
            user.is_superuser = False

        if commit:
            user.save()

            perfil, created = PerfilUsuario.objects.get_or_create(user=user)

            perfil.rol = rol
            perfil.telefono = self.cleaned_data.get("telefono")
            perfil.cargo = self.cleaned_data.get("cargo")
            perfil.area = self.cleaned_data.get("area")
            perfil.disponible = self.cleaned_data.get("disponible")
            perfil.activo = user.is_active
            perfil.save()

        return user
    

class UbicacionForm(forms.ModelForm):
    class Meta:
        model = Ubicacion
        fields = [
            "nombre",
            "departamento",
            "provincia",
            "distrito",
            "direccion_referencia",
            "descripcion",
            "activo",
        ]

        labels = {
            "nombre": "Nombre de la ubicación",
            "departamento": "Departamento",
            "provincia": "Provincia",
            "distrito": "Distrito",
            "direccion_referencia": "Dirección o referencia",
            "descripcion": "Descripción",
            "activo": "Ubicación activa",
        }

        widgets = {
            "nombre": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Chilca"
            }),
            "departamento": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Junín"
            }),
            "provincia": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Huancayo"
            }),
            "distrito": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Chilca"
            }),
            "direccion_referencia": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Zona operativa Fiber Z"
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Descripción de la ubicación"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})




class NodoForm(forms.ModelForm):
    class Meta:
        model = Nodo
        fields = [
            "codigo",
            "nombre",
            "ubicacion",
            "descripcion",
            "direccion_referencia",
            "estado",
            "criticidad",
            "clientes_estimados",
            "activo",
        ]

        labels = {
            "codigo": "Código del nodo",
            "nombre": "Nombre del nodo",
            "ubicacion": "Ubicación",
            "descripcion": "Descripción",
            "direccion_referencia": "Dirección o referencia",
            "estado": "Estado",
            "criticidad": "Criticidad",
            "clientes_estimados": "Clientes estimados",
            "activo": "Nodo activo",
        }

        widgets = {
            "codigo": forms.TextInput(attrs={
                "placeholder": "Ejemplo: NODO-CHILCA-01"
            }),
            "nombre": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Nodo Chilca Principal"
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Descripción operativa del nodo"
            }),
            "direccion_referencia": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Torre principal zona Chilca"
            }),
            "clientes_estimados": forms.NumberInput(attrs={
                "min": 0,
                "placeholder": "Ejemplo: 100"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["ubicacion"].queryset = Ubicacion.objects.filter(activo=True).order_by("nombre")

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo")

        if codigo:
            codigo = codigo.upper().strip()

            qs = Nodo.objects.filter(codigo=codigo)

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Ya existe un nodo con este código.")

        return codigo
    
class NodoForm(forms.ModelForm):
    class Meta:
        model = Nodo
        fields = [
            "codigo",
            "nombre",
            "ubicacion",
            "descripcion",
            "direccion_referencia",
            "estado",
            "criticidad",
            "clientes_estimados",
            "activo",
        ]

        labels = {
            "codigo": "Código del nodo",
            "nombre": "Nombre del nodo",
            "ubicacion": "Ubicación",
            "descripcion": "Descripción",
            "direccion_referencia": "Dirección o referencia",
            "estado": "Estado",
            "criticidad": "Criticidad",
            "clientes_estimados": "Clientes estimados",
            "activo": "Nodo activo",
        }

        widgets = {
            "codigo": forms.TextInput(attrs={
                "placeholder": "Ejemplo: NODO-CHILCA-01"
            }),
            "nombre": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Nodo Chilca Principal"
            }),
            "descripcion": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": "Descripción operativa del nodo"
            }),
            "direccion_referencia": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Torre principal zona Chilca"
            }),
            "clientes_estimados": forms.NumberInput(attrs={
                "min": 0,
                "placeholder": "Ejemplo: 100"
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["ubicacion"].queryset = Ubicacion.objects.filter(activo=True).order_by("nombre")

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo")

        if codigo:
            codigo = codigo.upper().strip()

            qs = Nodo.objects.filter(codigo=codigo)

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise forms.ValidationError("Ya existe un nodo con este código.")

        return codigo
    


class ComponenteRedForm(forms.ModelForm):
    class Meta:
        model = ComponenteRed
        fields = [
            "nodo",
            "codigo",
            "nombre",
            "tipo",
            "funcion",
            "ip_gestion",
            "mac_address",
            "fabricante",
            "modelo",
            "numero_serie",
            "host_id_zabbix",
            "es_monitoreado_zabbix",
            "impacto_por_caida",
            "estado_operativo",
            "criticidad",
            "clientes_estimados",
            "datos_tecnicos_json",
            "activo",
        ]

        labels = {
            "nodo": "Nodo asociado",
            "codigo": "Código del componente",
            "nombre": "Nombre del componente",
            "tipo": "Tipo de componente",
            "funcion": "Función",
            "ip_gestion": "IP de gestión",
            "mac_address": "Dirección MAC",
            "fabricante": "Fabricante",
            "modelo": "Modelo",
            "numero_serie": "Número de serie",
            "host_id_zabbix": "Host ID Zabbix",
            "es_monitoreado_zabbix": "Monitoreado por Zabbix",
            "impacto_por_caida": "Impacto por caída",
            "estado_operativo": "Estado operativo",
            "criticidad": "Criticidad",
            "clientes_estimados": "Clientes estimados",
            "datos_tecnicos_json": "Datos técnicos adicionales",
            "activo": "Componente activo",
        }

        widgets = {
            "codigo": forms.TextInput(attrs={
                "placeholder": "Ejemplo: RTR-HYO-01"
            }),
            "nombre": forms.TextInput(attrs={
                "placeholder": "Ejemplo: Router principal Huancayo"
            }),
            "ip_gestion": forms.TextInput(attrs={
                "placeholder": "Ejemplo: 10.10.10.1"
            }),
            "mac_address": forms.TextInput(attrs={
                "placeholder": "Ejemplo: AA:BB:CC:DD:EE:FF"
            }),
            "fabricante": forms.TextInput(attrs={
                "placeholder": "Ejemplo: MikroTik, Cambium, Huawei"
            }),
            "modelo": forms.TextInput(attrs={
                "placeholder": "Ejemplo: CCR, ePMP, S5735"
            }),
            "numero_serie": forms.TextInput(attrs={
                "placeholder": "Número de serie del equipo"
            }),
            "host_id_zabbix": forms.TextInput(attrs={
                "placeholder": "Ejemplo: 10084"
            }),
            "clientes_estimados": forms.NumberInput(attrs={
                "min": 0,
                "placeholder": "Ejemplo: 80"
            }),
            "datos_tecnicos_json": forms.Textarea(attrs={
                "rows": 4,
                "placeholder": '{ "puerto": "ether1", "enlace": "principal" }'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["nodo"].queryset = Nodo.objects.filter(
            activo=True
        ).order_by("codigo")

        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def clean_codigo(self):
        codigo = self.cleaned_data.get("codigo")

        if codigo:
            codigo = codigo.upper().strip()

        return codigo

    def clean_mac_address(self):
        mac = self.cleaned_data.get("mac_address")

        if mac:
            mac = mac.upper().strip()

        return mac

    def clean(self):
        cleaned_data = super().clean()

        nodo = cleaned_data.get("nodo")
        codigo = cleaned_data.get("codigo")
        es_monitoreado_zabbix = cleaned_data.get("es_monitoreado_zabbix")
        host_id_zabbix = cleaned_data.get("host_id_zabbix")
        impacto_por_caida = cleaned_data.get("impacto_por_caida")
        funcion = cleaned_data.get("funcion")

        if nodo and codigo:
            qs = ComponenteRed.objects.filter(
                nodo=nodo,
                codigo=codigo
            )

            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                self.add_error(
                    "codigo",
                    "Ya existe un componente con este código dentro del nodo seleccionado."
                )

        if es_monitoreado_zabbix and not host_id_zabbix:
            self.add_error(
                "host_id_zabbix",
                "Si el componente es monitoreado por Zabbix, debe ingresar el Host ID."
            )

        if impacto_por_caida == "NODO_COMPLETO" and funcion != "NODO_PRINCIPAL":
            self.add_error(
                "funcion",
                "Un componente que afecta al nodo completo debe tener función 'Nodo principal'."
            )

        if funcion == "SECTORIAL" and impacto_por_caida != "SECTORIAL":
            self.add_error(
                "impacto_por_caida",
                "Un componente con función sectorial debe tener impacto por caída 'Sectorial'."
            )

        return cleaned_data