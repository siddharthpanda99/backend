"""Auto-Remediation — MCP Tool Registration.

Registers auto-remediation management tools for agent consumption:
- drift_auto_remediation_config: View and update auto-remediation settings
- drift_auto_remediation_history: View recent auto-remediation events

Allows agents to programmatically manage the automatic drift remediation
system that fires when areas exceed thresholds across consecutive scans.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


def register_drift_remediation_tools(mcp: FastMCP) -> None:
    """Register all Auto-Remediation tools with the MCP server."""

    @mcp.tool()
    async def drift_auto_remediation_config(
        enabled: bool | None = None,
        min_consecutive_alerts: int | None = None,
        cooldown_minutes: int | None = None,
        auto_calibrate: bool | None = None,
        affected_areas_only: bool | None = None,
    ) -> str:
        """View or update the auto-remediation configuration.

        Auto-remediation automatically runs calibration when a drift area
        exceeds its alert threshold for N consecutive scans. This prevents
        drift accumulation without manual intervention.

        Args:
            enabled: Enable or disable auto-remediation globally. Omit to
                     just view current config.
            min_consecutive_alerts: Number of consecutive scans above
                                   threshold before remediation fires (1-20).
                                   Lower = more aggressive. Default 3.
            cooldown_minutes: Minutes to wait between remediation actions
                             (5-120). Default 30.
            auto_calibrate: Whether to run calibration automatically when
                           remediation fires. Default True.
            affected_areas_only: Only calibrate areas that triggered the
                                remediation vs full system reset. Default True.

        Returns:
            Current auto-remediation configuration and status.
        """
        try:
            from app.modules.orchestration.drift_routes import (
                get_auto_remediation_store,
                UpdateAutoRemediationRequest,
            )

            store = get_auto_remediation_store()

            # Update if any params provided
            has_updates = any(
                v is not None
                for v in [enabled, min_consecutive_alerts, cooldown_minutes,
                          auto_calibrate, affected_areas_only]
            )

            if has_updates:
                req = UpdateAutoRemediationRequest(
                    enabled=enabled,
                    min_consecutive_alerts=min_consecutive_alerts,
                    cooldown_minutes=cooldown_minutes,
                    auto_calibrate=auto_calibrate,
                    affected_areas_only=affected_areas_only,
                )
                store.update_config(req)

            config = store.get_config()

            lines = ["### Auto-Remediation Configuration\n"]
            lines.append(f"**Enabled:** {'✅ Yes' if config.enabled else '⏸️ No'}")
            lines.append(f"**Min Consecutive Alerts:** {config.min_consecutive_alerts}")
            lines.append(f"**Cooldown:** {config.cooldown_minutes} minutes")
            lines.append(f"**Auto-Calibrate:** {'Yes' if config.auto_calibrate else 'No'}")
            lines.append(f"**Affected Areas Only:** {'Yes' if config.affected_areas_only else 'No'}")
            lines.append("")
            lines.append(f"> When an area exceeds its threshold **{config.min_consecutive_alerts}x** consecutively,")
            lines.append(f"> calibration runs automatically with a **{config.cooldown_minutes}min** cooldown.")

            if has_updates:
                status = "enabled" if config.enabled else "disabled"
                lines.append(f"\n✅ Auto-remediation config updated — now **{status}**.")

            return "\n".join(lines)

        except Exception as exc:
            logger.error("drift_auto_remediation_config error: %s", exc)
            return f"Error retrieving/configuring auto-remediation: {exc}"

    @mcp.tool()
    async def drift_auto_remediation_history(limit: int = 20) -> str:
        """View recent auto-remediation events.

        Returns a list of automatic remediation actions triggered by
        consistent drift detection, including which area triggered it,
        the score, number of consecutive alerts, and whether the
        remediation succeeded.

        Args:
            limit: Maximum number of events to return. Default 20.

        Returns:
            Formatted list of recent auto-remediation events.
        """
        try:
            from app.modules.orchestration.drift_routes import get_auto_remediation_store

            store = get_auto_remediation_store()
            history = store.get_history(limit)

            if not history:
                config = store.get_config()
            if not history:
                status = "enabled" if store.get_config().enabled else "disabled"
                return (
                    f"No auto-remediation events recorded yet. "
                    f"Auto-remediation is **{status}** — "
                    f"events will appear here when consistent drift triggers automatic calibration."
                )

            lines = ["### Auto-Remediation History\n"]
            for h in reversed(history):
                icon = "🔄" if h.success else "⚠️"
                status = "✅ Completed" if h.success else "❌ Failed"
                lines.append(
                    f"{icon} **{h.trigger_label}** — {h.action} [{status}]"
                )
                lines.append(
                    f"   Score: {(h.trigger_score * 100):.1f}% | "
                    f"Consecutive: {h.consecutive_alerts} | "
                    f"🕐 {h.timestamp}"
                )
                lines.append(f"   {h.details[:120]}")

            return "\n".join(lines)

        except Exception as exc:
            logger.error("drift_auto_remediation_history error: %s", exc)
            return f"Error retrieving auto-remediation history: {exc}"

    @mcp.tool()
    async def drift_auto_remediation_reset() -> str:
        """Reset auto-remediation state.

        Clears the consecutive alert counters, remediation history, and
        cooldown timer. Use this after manual intervention to allow the
        system to start fresh.

        Returns:
            Confirmation message.
        """
        try:
            from app.modules.orchestration.drift_routes import get_auto_remediation_store

            store = get_auto_remediation_store()
            store.clear_history()
            return (
                "✅ Auto-remediation state reset. "
                "All consecutive counters cleared, history removed, "
                "and cooldown timer reset."
            )
        except Exception as exc:
            logger.error("drift_auto_remediation_reset error: %s", exc)
            return f"Error resetting auto-remediation: {exc}"

    logger.info("Drift Remediation: MCP tools registered (config, history, reset)")


__all__ = ["register_drift_remediation_tools"]
