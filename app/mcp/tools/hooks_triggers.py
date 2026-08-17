"""MCP tools for hooks, triggers, and the integration event bus.

Registered under the Cognitive Orchestrator MCP server.
These tools enable agents to interact with the event-driven runtime layer.
"""

import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from common_lib.modules.governance.hitl.service import get_hitl_service

logger = logging.getLogger("mcp.tools.hooks_triggers")


def register_hooks_triggers_tools(mcp: FastMCP):
    """Register tools for hooks, triggers, and the integration event bus."""

    # =========================================================================
    # HOOKS (event handlers registered to respond to specific events)
    # =========================================================================

    @mcp.tool()
    async def list_hooks() -> List[Dict[str, Any]]:
        """List all registered hooks in the governance system."""
        svc = get_hitl_service()
        hooks = svc.list_hooks()
        return [
            {
                "id": getattr(h, "id", ""),
                "name": getattr(h, "name", ""),
                "event": getattr(h, "event", ""),
                "enabled": getattr(h, "enabled", True),
            }
            for h in hooks
        ]

    @mcp.tool()
    async def register_hook(hook_id: str, name: str, event: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Register a new event hook in the governance system."""
        svc = get_hitl_service()
        body = {
            "id": hook_id,
            "name": name,
            "event": event,
            "enabled": True,
            "config": config or {},
        }
        result = svc.define_hook(body)
        return {
            "id": getattr(result, "id", hook_id),
            "name": getattr(result, "name", name),
            "status": "registered",
        }

    @mcp.tool()
    async def get_hook(hook_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific hook."""
        svc = get_hitl_service()
        result = svc.get_hook(hook_id)
        if not result:
            return {"status": "error", "message": "Hook not found"}
        return result.to_dict() if hasattr(result, "to_dict") else {"id": hook_id}

    @mcp.tool()
    async def update_hook(hook_id: str, name: Optional[str] = None, event: Optional[str] = None, enabled: Optional[bool] = None) -> Dict[str, Any]:
        """Update an existing hook's name, event, or enabled status."""
        svc = get_hitl_service()
        existing = svc.get_hook(hook_id)
        if not existing:
            return {"status": "error", "message": "Hook not found"}

        body = {"id": hook_id}
        if name is not None:
            body["name"] = name
        if event is not None:
            body["event"] = event
        if enabled is not None:
            body["enabled"] = enabled
        result = svc.define_hook(body)
        return {
            "id": hook_id,
            "status": "updated",
        }

    @mcp.tool()
    async def delete_hook(hook_id: str) -> Dict[str, Any]:
        """Delete a hook from the governance system."""
        svc = get_hitl_service()
        success = svc.delete_hook(hook_id)
        return {"status": "deleted" if success else "error"}

    @mcp.tool()
    async def toggle_hook(hook_id: str, enabled: bool) -> Dict[str, Any]:
        """Enable or disable a hook."""
        svc = get_hitl_service()
        existing = svc.get_hook(hook_id)
        if not existing:
            return {"status": "error", "message": "Hook not found"}
        body = {"id": hook_id, "enabled": enabled}
        # Merge with existing data to preserve other fields
        if hasattr(existing, "to_dict"):
            existing_data = existing.to_dict()
            for k, v in existing_data.items():
                if k not in body and k != "id":
                    body[k] = v
        svc.define_hook(body)
        return {"id": hook_id, "enabled": enabled, "status": "updated"}

    # =========================================================================
    # TRIGGERS (event conditions that fire hooks/rules/policies)
    # =========================================================================

    @mcp.tool()
    async def list_triggers() -> List[Dict[str, Any]]:
        """List all registered triggers in the governance system."""
        svc = get_hitl_service()
        triggers = svc.list_triggers()
        return [
            {
                "id": getattr(t, "id", ""),
                "name": getattr(t, "name", ""),
                "event": getattr(t, "event", ""),
                "condition": getattr(t, "condition", ""),
                "enabled": getattr(t, "enabled", True),
            }
            for t in triggers
        ]

    @mcp.tool()
    async def create_trigger(trigger_id: str, name: str, event: str, condition: str = "true") -> Dict[str, Any]:
        """Register a new trigger that fires when an event matches the condition."""
        svc = get_hitl_service()
        body = {
            "id": trigger_id,
            "name": name,
            "event": event,
            "condition": condition,
            "enabled": True,
        }
        result = svc.define_trigger(body)
        return {
            "id": getattr(result, "id", trigger_id) if hasattr(result, "id") else trigger_id,
            "name": name,
            "status": "created",
        }

    @mcp.tool()
    async def evaluate_trigger(trigger_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate whether a trigger's condition is met given the current context."""
        svc = get_hitl_service()
        trigger = svc.get_trigger(trigger_id)
        if not trigger:
            return {"status": "error", "message": "Trigger not found"}

        condition = getattr(trigger, "condition", "true")
        # Simple condition evaluation: check if all keys in condition exist in context
        # For production, this would use a proper expression evaluator
        matched = True
        if condition and condition != "true":
            matched = context.get("event") == condition or context.get("type") == condition

        return {
            "trigger_id": trigger_id,
            "matched": matched,
            "condition": condition,
        }

    @mcp.tool()
    async def delete_trigger(trigger_id: str) -> Dict[str, Any]:
        """Delete a trigger from the governance system."""
        svc = get_hitl_service()
        success = svc.delete_trigger(trigger_id)
        return {"status": "deleted" if success else "error"}

    # =========================================================================
    # APPROVAL POLICIES (combine hooks + triggers + approvers)
    # =========================================================================

    @mcp.tool()
    async def list_approval_policies() -> List[Dict[str, Any]]:
        """List all approval policies that combine triggers, hooks, and approvers."""
        svc = get_hitl_service()
        policies = svc.list_approval_policies()
        result = []
        for p in policies:
            d = {}
            for attr in [
                "approval_policy_id", "name", "description",
                "trigger_conditions", "approvers", "timeout",
                "escalation", "trigger_ids", "hook_ids",
            ]:
                if hasattr(p, attr):
                    d[attr] = getattr(p, attr)
            result.append(d)
        return result

    # =========================================================================
    # INTERCEPTORS (approval policy interceptors)
    # =========================================================================

    @mcp.tool()
    async def list_interceptors() -> List[Dict[str, Any]]:
        """List all interceptors that gate actions based on policies."""
        svc = get_hitl_service()
        interceptors = svc.list_interceptors()
        return [i.to_dict() for i in interceptors]

    # =========================================================================
    # INTEGRATION EVENT BUS
    # =========================================================================

    @mcp.tool()
    async def fire_event(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Fire an event through the integration event bus. Triggers matching hooks and triggers."""
        try:
            from common_lib.modules.integration import get_event_router

            router = get_event_router()
            result = await router.fire_event(
                event_type=event_type,
                data=payload,
                channel="global",
                priority="normal",
            )
            return {
                "event_type": event_type,
                "actions_taken": result.get("actions_taken", []),
                "errors": result.get("errors", []),
                "status": "fired",
            }
        except Exception as e:
            logger.error(f"Fire event failed: {e}")
            return {
                "event_type": event_type,
                "actions_taken": [],
                "errors": [str(e)],
                "status": "error",
            }

    @mcp.tool()
    async def get_event_history(limit: int = 100) -> Dict[str, Any]:
        """Get recent event routing history from the integration event bus."""
        try:
            from common_lib.modules.integration import get_event_router

            router = get_event_router()
            history = router.get_event_history(limit)
            return {
                "events": history,
                "count": len(history),
            }
        except Exception as e:
            logger.error(f"Get event history failed: {e}")
            return {"events": [], "count": 0, "error": str(e)}
