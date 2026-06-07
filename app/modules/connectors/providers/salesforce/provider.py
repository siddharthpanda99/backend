from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "salesforce"
    display_name = "Salesforce"
    base_url = ""
    endpoints = {
        "salesforce.soql_query": ("GET", "/services/data/v{api_version}/query"),
        "salesforce.describe_object": ("GET", "/services/data/v{api_version}/sobjects/{object_name}/describe"),
        "salesforce.create_record": ("POST", "/services/data/v{api_version}/sobjects/{object_name}"),
    }

    def get_base_url(self, form_data: Dict[str, Any]) -> str:
        return (form_data.get("instance_url") or "").rstrip("/")
