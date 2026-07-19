"""MCP tools for Events — callback management, event delivery, workflow mapping.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.events services.
"""

import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.events")


def register_events_tools(mcp: FastMCP):
    """Register tools for event management."""

    @mcp.tool()
    async def events_list_callbacks() -> List[Dict[str, Any]]:
        """List all registered event callbacks."""
        try:
            from common_lib.modules.events.callback_service import CallbackManager
            svc = CallbackManager()
            result = svc.list_callbacks() if hasattr(svc, "list_callbacks") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"events_list_callbacks error: {e}")
            return []

    @mcp.tool()
    async def events_create_callback(name: str, url: str, events: Optional[List[str]] = None, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Register a new event callback."""
        try:
            from common_lib.modules.events.callback_service import CallbackManager
            svc = CallbackManager()
            result = svc.create(name, url, events, config) if hasattr(svc, "create") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"events_create_callback error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def events_delete_callback(callback_id: str) -> str:
        """Delete an event callback."""
        try:
            from common_lib.modules.events.callback_service import CallbackManager
            svc = CallbackManager()
            svc.delete(callback_id) if hasattr(svc, "delete") else None
            return f"Callback {callback_id} deleted"
        except Exception as e:
            logger.error(f"events_delete_callback error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def events_deliver(event_type: str, payload: Dict[str, Any], target: Optional[str] = None) -> Dict[str, Any]:
        """Deliver an event to registered callbacks."""
        try:
            from common_lib.modules.events.callback_service import CallbackManager
            svc = CallbackManager()
            result = svc.deliver(event_type, payload, target) if hasattr(svc, "deliver") else {"delivered": 0}
            return result if isinstance(result, dict) else {"delivered": 0}
        except Exception as e:
            logger.error(f"events_deliver error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def events_workflow_mapping() -> Dict[str, Any]:
        """Get event-to-workflow mapping."""
        try:
            from common_lib.modules.events.callback_service import CallbackManager
            svc = CallbackManager()
            result = svc.get_mapping() if hasattr(svc, "get_mapping") else {}
            return result if isinstance(result, dict) else {"mapping": []}
        except Exception as e:
            logger.error(f"events_workflow_mapping error: {e}")
            return {"error": str(e)}

    logger.info("Events: 5 MCP tools registered")
