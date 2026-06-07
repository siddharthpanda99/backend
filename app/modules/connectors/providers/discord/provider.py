from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "discord"
    display_name = "Discord"
    base_url = "https://discord.com/api/v10"
    endpoints = {
        "discord.send_message": ("POST", "/channels/{channel_id}/messages"),
        "discord.get_channel_messages": ("GET", "/channels/{channel_id}/messages"),
    }
