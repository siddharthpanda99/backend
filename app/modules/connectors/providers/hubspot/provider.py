from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "hubspot"
    display_name = "HubSpot"
    base_url = "https://api.hubapi.com"
    endpoints = {
        "hubspot.list_contacts": ("GET", "/crm/v3/objects/contacts"),
        "hubspot.create_contact": ("POST", "/crm/v3/objects/contacts"),
        "hubspot.list_deals": ("GET", "/crm/v3/objects/deals"),
    }
