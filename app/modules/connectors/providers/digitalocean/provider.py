from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "digitalocean"
    display_name = "DigitalOcean"
    base_url = "https://api.digitalocean.com"
    endpoints = {
        "digitalocean.list_droplets": ("GET", "/v2/droplets"),
        "digitalocean.create_droplet": ("POST", "/v2/droplets"),
        "digitalocean.list_kubernetes_clusters": ("GET", "/v2/kubernetes/clusters"),
    }

    def build_auth_headers(self, auth_scheme: str, key_value: str, form_data: Dict[str, Any]) -> Dict[str, str]:
        headers = super().build_auth_headers(auth_scheme, key_value, form_data)
        headers["Content-Type"] = "application/json"
        return headers
