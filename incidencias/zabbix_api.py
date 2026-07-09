import requests


class ZabbixAPIError(Exception):
    pass


class ZabbixClient:
    def __init__(self, url_api, usuario=None, password=None, token_api=None, usar_token=False):
        self.url_api = url_api
        self.usuario = usuario
        self.password = password
        self.token_api = token_api
        self.usar_token = usar_token
        self.auth_token = token_api if usar_token else None

    def _request(self, method, params=None, auth=True):
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }

        if auth and self.auth_token:
            payload["auth"] = self.auth_token

        try:
            response = requests.post(
                self.url_api,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise ZabbixAPIError(f"Error de conexión HTTP: {exc}")

        data = response.json()

        if "error" in data:
            mensaje = data["error"].get("message", "Error desconocido")
            detalle = data["error"].get("data", "")
            raise ZabbixAPIError(f"{mensaje}. {detalle}")

        return data.get("result")

    def login(self):
        if self.usar_token:
            if not self.token_api:
                raise ZabbixAPIError("No se ingresó token API.")
            return self.token_api

        if not self.usuario or not self.password:
            raise ZabbixAPIError("Debe ingresar usuario y contraseña.")

        result = self._request(
            "user.login",
            {
                "username": self.usuario,
                "password": self.password,
            },
            auth=False
        )

        self.auth_token = result
        return result

    def probar_conexion(self):
        self.login()

        version = self._request(
            "apiinfo.version",
            {},
            auth=False
        )

        return {
            "ok": True,
            "version": version,
            "mensaje": f"Conexión exitosa con Zabbix. Versión API: {version}"
        }

    def obtener_hosts(self):
        """
        Consulta hosts registrados en Zabbix.
        Valida que el token o credenciales tengan permisos reales.
        """

        self.login()

        hosts = self._request(
            "host.get",
            {
                "output": [
                    "hostid",
                    "host",
                    "name",
                    "status"
                ],
                "selectInterfaces": [
                    "ip",
                    "dns",
                    "type",
                    "main",
                    "useip"
                ],
                "sortfield": "name"
            },
            auth=True
        )

        return hosts