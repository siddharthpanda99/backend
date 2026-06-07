from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "twilio"
    display_name = "Twilio"
    base_url = "https://api.twilio.com"
    endpoints = {
        "twilio.send_sms": ("POST", "/2010-04-01/Accounts/{account_sid}/Messages.json"),
    }

    def execute(self, tool_id: str, params: Dict[str, Any], connection: Any, form_data: Dict[str, Any]) -> Any:
        import base64
        endpoint = self.endpoints.get(tool_id)
        if not endpoint:
            raise Exception(f"No endpoint for {tool_id}")
        method, path_template = endpoint
        from ..base import substitute_path_params
        path, remaining = substitute_path_params(path_template, params, form_data)
        url = f"{self.base_url}{path}"
        key = self._resolve_key(connection)
        encoded = base64.b64encode(f"{key}:".encode()).decode()
        headers = {"Authorization": f"Basic {encoded}", "Content-Type": "application/x-www-form-urlencoded"}
        return self._request(method, url, headers, remaining, None)
