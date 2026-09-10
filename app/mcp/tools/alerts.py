"""``app.mcp.tools.alerts`` — MCP tool registrations for Alerts module.

Registers all @node wrappers as MCP tools following the platform pattern.
"""

from __future__ import annotations

import logging
from typing import Any

from app.mcp.fastmcp_compat import FastMCP
from common_lib.modules.knowledge_engine.alerts import nodes as _nodes
from common_lib.modules.plugins.node import get_node_metadata

logger = logging.getLogger(__name__)


def register_alerts_tools(mcp: FastMCP) -> None:
    """Register all Alerts @node wrappers as MCP tools.

    Each @node wrapper becomes an MCP tool with the same name,
    description, and input/output schemas.
    """

    @mcp.tool()
    async def alerts_create_rule(
        kb_id: str,
        name: str,
        trigger: str,
        description: str = "",
        condition: dict[str, Any] | None = None,
        severity: str = "info",
        cooldown_seconds: int = 3600,
        channels: list[dict[str, Any]] | None = None,
        created_by: str = "system",
    ) -> dict[str, Any]:
        """Create a new alert rule with condition, severity, cooldown, and channels."""
        return _nodes.alerts_create_rule(
            kb_id=kb_id,
            name=name,
            trigger=trigger,
            description=description,
            condition=condition,
            severity=severity,
            cooldown_seconds=cooldown_seconds,
            channels=channels,
            created_by=created_by,
        )

    @mcp.tool()
    async def alerts_get_rule(kb_id: str, rule_id: str) -> dict[str, Any]:
        """Fetch an alert rule by ID."""
        return _nodes.alerts_get_rule(kb_id=kb_id, rule_id=rule_id)

    @mcp.tool()
    async def alerts_list_rules(
        kb_id: str,
        trigger: str | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List alert rules for a KB with optional filters."""
        return _nodes.alerts_list_rules(
            kb_id=kb_id,
            trigger=trigger,
            enabled=enabled,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    async def alerts_update_rule(
        kb_id: str,
        rule_id: str,
        name: str | None = None,
        description: str | None = None,
        condition: dict[str, Any] | None = None,
        severity: str | None = None,
        cooldown_seconds: int | None = None,
        channels: list[dict[str, Any]] | None = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        """Update an alert rule."""
        return _nodes.alerts_update_rule(
            kb_id=kb_id,
            rule_id=rule_id,
            name=name,
            description=description,
            condition=condition,
            severity=severity,
            cooldown_seconds=cooldown_seconds,
            channels=channels,
            enabled=enabled,
        )

    @mcp.tool()
    async def alerts_delete_rule(kb_id: str, rule_id: str) -> dict[str, Any]:
        """Delete an alert rule."""
        return _nodes.alerts_delete_rule(kb_id=kb_id, rule_id=rule_id)

    @mcp.tool()
    async def alerts_get_alert(kb_id: str, alert_id: str) -> dict[str, Any]:
        """Fetch an alert by ID."""
        return _nodes.alerts_get_alert(kb_id=kb_id, alert_id=alert_id)

    @mcp.tool()
    async def alerts_list_alerts(
        kb_id: str,
        rule_id: str | None = None,
        status: str | None = None,
        entity_id: str | None = None,
        fact_id: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List alerts with filters."""
        return _nodes.alerts_list_alerts(
            kb_id=kb_id,
            rule_id=rule_id,
            status=status,
            entity_id=entity_id,
            fact_id=fact_id,
            since=since,
            until=until,
            limit=limit,
            offset=offset,
        )

    @mcp.tool()
    async def alerts_acknowledge_alert(
        kb_id: str,
        alert_id: str,
        acknowledged_by: str = "system",
    ) -> dict[str, Any]:
        """Acknowledge an alert."""
        return _nodes.alerts_acknowledge_alert(
            kb_id=kb_id, alert_id=alert_id, acknowledged_by=acknowledged_by
        )

    @mcp.tool()
    async def alerts_resolve_alert(
        kb_id: str,
        alert_id: str,
        resolved_by: str = "system",
    ) -> dict[str, Any]:
        """Resolve an alert."""
        return _nodes.alerts_resolve_alert(
            kb_id=kb_id, alert_id=alert_id, resolved_by=resolved_by
        )

    @mcp.tool()
    async def alerts_dismiss_alert(kb_id: str, alert_id: str) -> dict[str, Any]:
        """Dismiss an alert."""
        return _nodes.alerts_dismiss_alert(kb_id=kb_id, alert_id=alert_id)

    @mcp.tool()
    async def alerts_evaluate(
        kb_id: str,
        trigger: str,
        payload: dict[str, Any],
        entity_id: str | None = None,
        fact_id: str | None = None,
    ) -> dict[str, Any]:
        """Evaluate all rules matching a trigger and fire alerts."""
        return _nodes.alerts_evaluate(
            kb_id=kb_id,
            trigger=trigger,
            payload=payload,
            entity_id=entity_id,
            fact_id=fact_id,
        )

    @mcp.tool()
    async def alerts_dispatch_alert(kb_id: str, alert_id: str) -> dict[str, Any]:
        """Manually dispatch a specific alert (retry failed dispatch)."""
        return _nodes.alerts_dispatch_alert(kb_id=kb_id, alert_id=alert_id)

    logger.info(
        "mcp.tools.alerts.registered",
        extra={"count": 12},
    )


__all__ = ["register_alerts_tools"]
