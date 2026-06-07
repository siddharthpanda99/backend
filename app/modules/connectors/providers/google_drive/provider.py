from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "google_drive"
    display_name = "Google Drive"
    base_url = "https://www.googleapis.com/drive/v3"
    endpoints = {
        "google_drive.list_files": ("GET", "/files"),
        "google_drive.get_file": ("GET", "/files/{file_id}"),
        "google_drive.upload_file": ("POST", "/files"),
    }
