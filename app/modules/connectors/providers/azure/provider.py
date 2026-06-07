from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "azure"
    display_name = "Azure"
    base_url = ""
    endpoints = {
        "azure.list_resource_groups": ("GET", "/subscriptions/{subscription_id}/resourcegroups"),
        "azure.list_vms": ("GET", "/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines"),
    }

    def get_base_url(self, form_data: Dict[str, Any]) -> str:
        return "https://management.azure.com"
