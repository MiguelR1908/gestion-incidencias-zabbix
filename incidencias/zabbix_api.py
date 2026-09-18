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

        headers = {
            "Content-Type": "application/json-rpc",
        }

        if auth and self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        try:
            response = requests.post(
                self.url_api,
                json=payload,
                timeout=10,
                headers=headers,
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
        Obtiene los hosts registrados en Zabbix junto con sus
        interfaces, grupos, templates y tags.
        """

        self.login()

        return self._request(
            "host.get",
            {
                "output": [
                    "hostid",
                    "host",
                    "name",
                    "status",
                ],
                "selectInterfaces": [
                    "interfaceid",
                    "type",
                    "main",
                    "useip",
                    "ip",
                    "dns",
                    "port",
                    "available",
                    "error",
                ],
                "selectHostGroups": [
                    "groupid",
                    "name",
                ],
                "selectParentTemplates": [
                    "templateid",
                    "host",
                    "name",
                ],
                "selectTags": "extend",
                "sortfield": "name",
                "sortorder": "ASC",
            },
            auth=True,
        )

    def obtener_problemas_activos(self):
        """
        Consulta problemas activos desde Zabbix.
        Primero obtiene los problemas con problem.get.
        Luego obtiene los hosts asociados usando trigger.get.
        """

        self.login()

        problemas = self._request(
            "problem.get",
            {
                "output": [
                    "eventid",
                    "objectid",
                    "name",
                    "severity",
                    "clock",
                    "acknowledged"
                ],
                "selectTags": "extend",
                "recent": False,
                "sortfield": "eventid",
                "sortorder": "DESC"
            },
            auth=True
        )

        if not problemas:
            return []

        trigger_ids = []

        for problema in problemas:
            objectid = problema.get("objectid")

            if objectid:
                trigger_ids.append(objectid)

        triggers = self._request(
            "trigger.get",
            {
                "output": [
                    "triggerid",
                    "description"
                ],
                "triggerids": trigger_ids,
                "selectHosts": [
                    "hostid",
                    "host",
                    "name"
                ]
            },
            auth=True
        )

        mapa_triggers = {}

        for trigger in triggers:
            mapa_triggers[trigger.get("triggerid")] = trigger

        for problema in problemas:
            trigger_id = problema.get("objectid")
            trigger = mapa_triggers.get(trigger_id)

            if trigger:
                problema["hosts"] = trigger.get("hosts", [])
            else:
                problema["hosts"] = []

        return problemas