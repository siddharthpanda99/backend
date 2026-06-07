from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "paypal"
    display_name = "PayPal"
    base_url = ""
    endpoints = {
        "paypal.create_order": ("POST", "/v2/checkout/orders"),
        "paypal.capture_order": ("POST", "/v2/checkout/orders/{order_id}/capture"),
    }

    def get_base_url(self, form_data: Dict[str, Any]) -> str:
        mode = form_data.get("mode", "sandbox")
        return "https://api-m.paypal.com" if mode == "live" else "https://api-m.sandbox.paypal.com"
