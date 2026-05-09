import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import resolve_notification_service

logger = logging.getLogger("mcp.tools.notifications")

def register_notification_tools(mcp: FastMCP):
    """Register tools for system communications and user notifications."""

    @mcp.tool()
    async def notify_send(
        title: str,
        message: str,
        user_id: Optional[str] = None,
        type: str = "info",
        severity: str = "medium"
    ) -> Dict[str, Any]:
        """
        Send a notification to a specific user or the system-wide notification tray.
        'type' can be 'info', 'success', 'warning', or 'error'.
        """
        bridge = resolve_notification_service()
        notify_func = bridge["notify"]
        try:
            # We use the notify helper which handles DB persistence and real-time push
            alert = await notify_func(
                title=title,
                message=message,
                user_id=user_id,
                alert_type=type,
                severity=severity
            )
            return {"status": "success", "alert_id": str(alert.id) if hasattr(alert, "id") else "sent"}
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def notify_broadcast(
        message: str,
        title: str = "System Announcement"
    ) -> Dict[str, Any]:
        """Broadcast a critical message to all active users and agent sessions."""
        bridge = resolve_notification_service()
        event_bus = bridge["event_bus"]
        try:
            # Publish to the global event bus
            event_bus.publish("system_broadcast", {"title": title, "message": message})
            # Also send a system-level notification
            await bridge["notify"](title=title, message=message, alert_type="system")
            return {"status": "broadcasted"}
        except Exception as e:
            logger.error(f"Broadcast failed: {e}")
            return {"status": "error", "message": str(e)}
