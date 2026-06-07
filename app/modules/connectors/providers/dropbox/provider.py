from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "dropbox"
    display_name = "Dropbox"
    base_url = "https://api.dropboxapi.com"
    endpoints = {
        "dropbox.list_files": ("POST", "/files/list_folder"),
        "dropbox.download_file": ("POST", "/files/download"),
    }
