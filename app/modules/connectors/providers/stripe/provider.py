from typing import Any, Dict, Optional

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "stripe"
    display_name = "Stripe"
    base_url = "https://api.stripe.com"
    endpoints = {
        "stripe.list_charges": ("GET", "/v1/charges"),
        "stripe.list_customers": ("GET", "/v1/customers"),
        "stripe.create_customer": ("POST", "/v1/customers"),
        "stripe.create_payment_intent": ("POST", "/v1/payment_intents"),
    }

    def build_body(self, tool_id: str, method: str, params: Dict[str, Any], form_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return None  # Stripe uses form-urlencoded, not JSON

    def execute(self, tool_id: str, params: Dict[str, Any], connection: Any, form_data: Dict[str, Any]) -> Any:
        import base64
        endpoint = self.endpoints.get(tool_id)
        if not endpoint:
            raise Exception(f"No endpoint for {tool_id}")
        method, path = endpoint
        url = f"{self.base_url}{path}"
        key = self._resolve_key(connection)
        encoded = base64.b64encode(f"{key}:".encode()).decode()
        headers = {"Authorization": f"Basic {encoded}", "Content-Type": "application/x-www-form-urlencoded"}
        query = params if method == "GET" else None
        body = params if method in ("POST",) else None
        return self._request(method, url, headers, query, body)
