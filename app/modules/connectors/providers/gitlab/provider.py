from typing import Any, Dict

from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "gitlab"
    display_name = "GitLab"
    base_url = ""
    endpoints = {
        "gitlab.list_projects": ("GET", "/projects"),
        "gitlab.list_issues": ("GET", "/projects/{project_id}/issues"),
        "gitlab.create_issue": ("POST", "/projects/{project_id}/issues"),
        "gitlab.list_pipelines": ("GET", "/projects/{project_id}/pipelines"),
    }

    def get_base_url(self, form_data: Dict[str, Any]) -> str:
        base = form_data.get("instance_url", "https://gitlab.com").rstrip("/")
        return f"{base}/api/v4"

    def build_auth_headers(self, auth_scheme: str, key_value: str, form_data: Dict[str, Any]) -> Dict[str, str]:
        if auth_scheme == "api_key":
            return {"PRIVATE-TOKEN": key_value}
        return {"Authorization": f"Bearer {key_value}"}
