from ..base import RESTProvider

class Provider(RESTProvider):
    provider_id = "slack"
    display_name = "Slack"
    base_url = "https://slack.com/api"
    endpoints = {
        "slack.post_message": ("POST", "/chat.postMessage"),
        "slack.list_channels": ("GET", "/conversations.list"),
        "slack.get_channel_history": ("GET", "/conversations.history"),
    }
