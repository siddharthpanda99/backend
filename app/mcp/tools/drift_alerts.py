"""Drift Alert Configuration — MCP Tool Registration.

Registers drift alert management tools for agent consumption:
- drift_alert_get_config: View alert thresholds and notification settings
- drift_alert_set_threshold: Update a specific area's alert threshold
- drift_alert_history: View recent alert firing events

Allows agents to programmatically manage drift alert thresholds and
review alert history.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_drift_alert_tools(mcp: FastMCP) -> None:
    """Register all Drift Alert tools with the MCP server."""

    @mcp.tool()
    async def drift_alert_get_config() -> str:
        """View the current drift alert configuration.

        Returns per-area alert thresholds, global enabled state,
        notification channel, recipient, and cooldown period.

        Use this to inspect what thresholds are set before deciding
        whether to adjust them.
        """
        try:
            from app.modules.orchestration.drift_routes import get_alert_store

            store = get_alert_store()
            config = store.get_config()

            lines = ["### Drift Alert Configuration\n"]
            lines.append(f"**Global Alerts:** {'Enabled' if config.global_enabled else 'Disabled'}")
            lines.append(f"**Notification Channel:** {config.notification_channel}")
            lines.append(f"**Notification Recipient:** {config.notification_recipient}")
            lines.append(f"**Cooldown:** {config.cooldown_minutes} minutes\n")
            lines.append("**Area Thresholds:**")

            for t in config.thresholds:
                status = "✅" if t.enabled else "⛔"
                lines.append(f"  {status} **{t.label}**: {(t.threshold * 100):.0f}% threshold")

            return "\n".join(lines)

        except Exception as exc:
            logger.error("drift_alert_get_config error: %s", exc)
            return f"Error retrieving alert config: {exc}"

    @mcp.tool()
    async def drift_alert_set_threshold(
        area_id: str = "context",
        threshold_pct: float = 30.0,
        enabled: bool = True,
    ) -> str:
        """Update the alert threshold for a specific drift detection area.

        When a drift area's score exceeds its threshold, an alert is fired
        and a notification is sent via the Messaging Gateway.

        Args:
            area_id: Drift area to configure — one of: context, performance,
                    semantic, behavioral
            threshold_pct: Alert threshold as a percentage (0–100). Default 30.
                          e.g., 30 means alert when drift score exceeds 30%.
            enabled: Whether alerts are enabled for this area. Default true.

        Returns:
            Confirmation of the updated threshold.
        """
        valid_areas = {"context", "performance", "semantic", "behavioral"}
        if area_id not in valid_areas:
            return (
                f"❌ Invalid area_id '{area_id}'. "
                f"Valid areas: {', '.join(sorted(valid_areas))}"
            )

        if threshold_pct < 0 or threshold_pct > 100:
            return "❌ threshold_pct must be between 0 and 100."

        try:
            from app.modules.orchestration.drift_routes import get_alert_store

            store = get_alert_store()
            config = store.get_config()

            # Update the specific area
            updated_thresholds = []
            for t in config.thresholds:
                if t.area_id == area_id:
                    updated_thresholds.append({
                        "area_id": area_id,
                        "label": t.label,
                        "threshold": round(threshold_pct / 100, 2),
                        "enabled": enabled,
                    })
                else:
                    updated_thresholds.append({
                        "area_id": t.area_id,
                        "label": t.label,
                        "threshold": t.threshold,
                        "enabled": t.enabled,
                    })

            from pydantic import BaseModel

            class _UpdateReq(BaseModel):
                thresholds: Optional[List[Dict[str, Any]]] = None
                global_enabled: Optional[bool] = None
                notification_channel: Optional[str] = None
                notification_recipient: Optional[str] = None
                cooldown_minutes: Optional[int] = None

            req = _UpdateReq(thresholds=updated_thresholds)
            store.update_config(req)

            status = "enabled" if enabled else "disabled"
            return (
                f"✅ **{area_id.title()}** alert threshold updated to "
                f"**{threshold_pct:.0f}%** ({status}). "
                f"Alerts will fire when this area's drift score exceeds "
                f"{threshold_pct:.0f}%."
            )

        except Exception as exc:
            logger.error("drift_alert_set_threshold error: %s", exc)
            return f"Error updating threshold: {exc}"

    @mcp.tool()
    async def drift_alert_history(limit: int = 20) -> str:
        """View recent drift alert firing events.

        Returns recent alerts with timestamps, drift area, score,
        threshold, and whether a notification was sent.

        Args:
            limit: Maximum number of recent alerts to return. Default 20.

        Returns:
            Formatted list of recent alert events.
        """
        try:
            from app.modules.orchestration.drift_routes import get_alert_store

            store = get_alert_store()
            history = store.get_history(limit)

            if not history:
                return "No drift alerts have been fired yet."

            lines = ["### Recent Drift Alerts\n"]
            for h in reversed(history):
                icon = "🔔" if h.notification_sent else "⚠️"
                status = "Sent" if h.notification_sent else "Logged"
                error = f" — Error: {h.notification_error}" if h.notification_error else ""
                lines.append(
                    f"{icon} **{h.label}**: {(h.score * 100):.1f}% "
                    f"(threshold: {(h.threshold * 100):.1f}%) — "
                    f"[{status}]{error}"
                )
                lines.append(f"   🕐 {h.timestamp}")

            return "\n".join(lines)

        except Exception as exc:
            logger.error("drift_alert_history error: %s", exc)
            return f"Error retrieving alert history: {exc}"

    @mcp.tool()
    async def drift_alert_toggle_global(enabled: bool = True) -> str:
        """Enable or disable all drift alerts globally.

        When disabled, no drift alerts will fire regardless of area-level
        thresholds. Use this to silence alerts during maintenance.

        Args:
            enabled: True to enable alerts, False to disable. Default true.

        Returns:
            Confirmation of the updated state.
        """
        try:
            from app.modules.orchestration.drift_routes import get_alert_store, UpdateAlertConfigRequest

            store = get_alert_store()
            store.update_config(UpdateAlertConfigRequest(global_enabled=enabled))

            status = "enabled" if enabled else "disabled"
            return f"✅ Drift alerts are now **{status}** globally."

        except Exception as exc:
            logger.error("drift_alert_toggle_global error: %s", exc)
            return f"Error toggling alerts: {exc}"

    logger.info("Drift Alerts: MCP tools registered (config, set threshold, history, toggle)")


__all__ = ["register_drift_alert_tools"]
