"""Backend Messaging Adapters — register Slack/Email dispatch with the gateway.

These adapters bridge the pure common_lib MessagingGateway to the
backend-specific ConnectorExecutionEngine and are registered during
application startup (e.g., in main.py's lifespan).

Usage (in app startup):
    from app.modules.messaging.adapters import register_messaging_adapters
    register_messaging_adapters()
"""

import logging
from typing import Dict, Any

from common_lib.modules.notification.messaging import (
    get_messaging_gateway,
    MessageChannel,
    Message,
    DispatchResult,
)

logger = logging.getLogger(__name__)


async def _slack_adapter(msg: Message) -> DispatchResult:
    """Dispatch a message to Slack via ConnectorExecutionEngine."""
    try:
        from app.modules.connectors.execute_engine import ConnectorExecutionEngine
        from common_lib.modules.plugins.connectors.models.connection import (
            Connection,
        )

        engine = ConnectorExecutionEngine()
        connection = Connection(
            id=msg.metadata.get("connection_id", "__gateway_slack__"),
            auth_scheme=msg.metadata.get("auth_scheme", "bearer_token"),
            connector_id="slack",
        )

        result = engine.execute(
            connector_id="slack",
            tool_id="slack.post_message",
            params={
                "channel": msg.recipient,
                "text": f"*{msg.subject}*\n\n{msg.body}",
            },
            connection=connection,
            form_data=msg.metadata.get("form_data", {}),
        )
        return DispatchResult(
            success=True, channel=msg.channel,
            provider_response=result,
        )
    except Exception as e:
        logger.error(f"Slack adapter failed: {e}")
        return DispatchResult(
            success=False, channel=msg.channel,
            error=f"Slack dispatch failed: {e}",
        )


async def _email_adapter(msg: Message) -> DispatchResult:
    """Dispatch a message as email via ConnectorExecutionEngine (SendGrid)."""
    try:
        from app.modules.connectors.execute_engine import ConnectorExecutionEngine
        from common_lib.modules.plugins.connectors.models.connection import (
            Connection,
        )

        engine = ConnectorExecutionEngine()
        connection = Connection(
            id=msg.metadata.get("connection_id", "__gateway_sendgrid__"),
            auth_scheme=msg.metadata.get("auth_scheme", "bearer_token"),
            connector_id="sendgrid",
        )

        result = engine.execute(
            connector_id="sendgrid",
            tool_id="sendgrid.send_email",
            params={
                "personalizations": [{"to": [{"email": msg.recipient}]}],
                "from": {"email": msg.metadata.get("from_email", "notifications@platform.local")},
                "subject": msg.subject,
                "content": [{"type": "text/plain", "value": msg.body}],
            },
            connection=connection,
            form_data=msg.metadata.get("form_data", {}),
        )
        return DispatchResult(
            success=True, channel=msg.channel,
            provider_response=result,
        )
    except Exception as e:
        logger.error(f"Email adapter failed: {e}")
        return DispatchResult(
            success=False, channel=msg.channel,
            error=f"Email dispatch failed: {e}",
        )


def register_messaging_adapters():
    """Register all backend-specific messaging adapters at startup.

    Call this once during application bootstrap (e.g., in lifespan).
    """
    gateway = get_messaging_gateway()

    gateway.register_adapter(
        MessageChannel.SLACK, _slack_adapter,
        name="Slack via Connectors",
    )
    gateway.register_adapter(
        MessageChannel.EMAIL, _email_adapter,
        name="Email via SendGrid",
    )

    logger.info(
        "Messaging adapters registered: slack, email — "
        "%d total external adapters",
        len(gateway.get_registered_adapters()),
    )
