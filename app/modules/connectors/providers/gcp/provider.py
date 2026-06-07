from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "gcp"
    display_name = "GCP"
    base_url = "https://www.googleapis.com"
    endpoints = {
        "gcp.list_storage_buckets": ("GET", "/storage/v1/b"),
        "gcp.list_compute_instances": ("GET", "/compute/v1/projects/{project_id}/zones/{zone}/instances"),
    }
