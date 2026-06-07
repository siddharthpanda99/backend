from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "sendgrid"
    display_name = "SendGrid"
    base_url = "https://api.sendgrid.com"
    endpoints = {
        "sendgrid.send_email": ("POST", "/v3/mail/send"),
    }
