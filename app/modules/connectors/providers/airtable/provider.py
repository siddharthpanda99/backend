from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "airtable"
    display_name = "Airtable"
    base_url = "https://api.airtable.com/v0"
    endpoints = {
        "airtable.list_records": ("GET", "/{base_id}/{table_name}"),
        "airtable.create_record": ("POST", "/{base_id}/{table_name}"),
        "airtable.update_record": ("PATCH", "/{base_id}/{table_name}/{record_id}"),
    }
