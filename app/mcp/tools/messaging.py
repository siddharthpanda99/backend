"""Messaging Gateway — MCP Tool Registration.

Registers unified messaging tools that agents can call to send messages
across any channel (notification, slack, email, webhook, log) without
needing to know the underlying provider.
"""

import logging
from typing import Optional, Dict, Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.messaging")


def register_messaging_tools(mcp: FastMCP):
    """Register all Messaging Gateway tools with the MCP server."""

    @mcp.tool()
    async def messaging_send(
        channel: str,
        recipient: str,
        subject: str,
        body: str,
        priority: str = "normal",
        source: str = "",
    ) -> str:
        """Send a message through any available channel.

        Channels:
        - 'notification' — in-app notification (SSE, no config needed)
        - 'slack' — send to a Slack channel (requires Slack connector)
        - 'email' — send an email (requires SendGrid connector)
        - 'webhook' — POST to a webhook URL
        - 'log' — structured log output (dev/debug)

        Args:
            channel: Target channel (notification, slack, email, webhook, log).
            recipient: Channel-specific recipient (user ID, #channel, email, URL).
            subject: Message subject or title.
            body: Message body content.
            priority: Priority level (low, normal, high, critical). Default normal.
            source: Optional source system name.

        Returns:
            Status message with dispatch result.
        """
        try:
            from common_lib.modules.messaging import (
                get_messaging_gateway,
                MessageChannel,
                MessagePriority,
            )

            gateway = get_messaging_gateway()
            chan = MessageChannel(channel)
            prio = MessagePriority(priority)

            result = await gateway.send(
                channel=chan,
                recipient=recipient,
                subject=subject,
                body=body,
                priority=prio,
                source=source,
            )

            if result.success:
                return (
                    f"✅ Message sent via '{channel}' to '{recipient}'. "
                    f"Subject: {subject[:80]}"
                )
            else:
                return f"❌ Failed to send message: {result.error}"

        except ValueError as e:
            return f"❌ Invalid channel or priority: {e}"
        except Exception as e:
            logger.error(f"Messaging send error: {e}")
            return f"❌ Error: {e}"

    @mcp.tool()
    async def messaging_list_channels() -> str:
        """List all available messaging channels with descriptions.

        Returns a formatted list of channels that can be used with messaging_send.
        """
        try:
            from common_lib.modules.messaging import get_messaging_gateway

            gateway = get_messaging_gateway()
            channels = gateway.get_channels()

            if not channels:
                return "No messaging channels available."

            lines = ["### Available Messaging Channels\n"]
            for ch in channels:
                config = ""
                if ch.get("requires_config"):
                    config = f" ⚠️ {ch.get('config_hint', 'Requires configuration')}"
                lines.append(
                    f"- **{ch['name']}** (`{ch['id']}`): "
                    f"{ch['description']}{config}"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"List channels error: {e}")
            return f"Error listing channels: {e}"

    @mcp.tool()
    async def messaging_history(limit: int = 10) -> str:
        """View recent message dispatch history.

        Args:
            limit: Number of recent messages to show (max 50). Default 10.

        Returns:
            Formatted list of recent messages and their dispatch status.
        """
        try:
            from common_lib.modules.messaging import get_messaging_gateway

            gateway = get_messaging_gateway()
            messages = gateway.get_recent_messages(limit=min(limit, 50))

            if not messages:
                return "No messages in history."

            lines = ["### Recent Messages\n"]
            for m in messages:
                lines.append(
                    f"- [{m.channel.value}] {m.subject[:60]} → {m.recipient[:40]} "
                    f"({m.priority.value})"
                )

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"History error: {e}")
            return f"Error retrieving history: {e}"

    logger.info("Messaging Gateway: 3 MCP tools registered")
