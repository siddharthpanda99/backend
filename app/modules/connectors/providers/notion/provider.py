from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "notion"
    display_name = "Notion"
    base_url = "https://api.notion.com/v1"
    endpoints = {
        "notion.search": ("POST", "/search"),
        "notion.retrieve_page": ("GET", "/pages/{page_id}"),
        "notion.create_page": ("POST", "/pages"),
        "notion.query_database": ("POST", "/databases/{database_id}/query"),
    }

    def build_auth_headers(self, auth_scheme: str, key_value: str, form_data: Dict[str, Any]) -> Dict[str, str]:
        headers = super().build_auth_headers(auth_scheme, key_value, form_data)
        headers["Notion-Version"] = "2022-06-28"
        return headers
