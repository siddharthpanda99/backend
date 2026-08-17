"""Module 28 — API Layer, WebSocket & MCP Integration MCP tools."""
from typing import Any, Dict, List, Optional
from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.db_studio.api_integration.service import ApiIntegrationService

svc = ApiIntegrationService()


def register_api_integration_tools(mcp: FastMCP):
    """Register all API integration tools with the MCP server."""

    @mcp.tool()
    async def api_create_api_key(
        name: str,
        rate_limit: int = 1000,
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Create a new API key"""
        from datetime import datetime, timedelta, timezone
        from common_lib.modules.db_studio.api_integration.schemas import ApiKeyCreate
        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        req = ApiKeyCreate(name=name, rate_limit=rate_limit, expires_at=expires_at)
        result = svc.create_api_key(req)
        return result.model_dump()

    @mcp.tool()
    async def api_list_api_keys(
        is_active: Optional[bool] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List API keys"""
        results = svc.list_api_keys(is_active=is_active, limit=limit)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def api_revoke_api_key(key_id: str) -> Dict[str, bool]:
        """Revoke an API key"""
        ok = svc.revoke_api_key(key_id)
        return {"ok": ok}

    @mcp.tool()
    async def api_create_webhook(
        name: str, url: str, events: List[str],
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """Create a webhook subscription"""
        from common_lib.modules.db_studio.api_integration.schemas import WebhookSubscriptionCreate
        req = WebhookSubscriptionCreate(
            name=name, url=url, events=events, retry_count=retry_count,
        )
        result = svc.create_webhook(req)
        return result.model_dump()

    @mcp.tool()
    async def api_list_webhooks(
        is_active: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """List webhook subscriptions"""
        results = svc.list_webhooks(is_active=is_active)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def api_register_mcp_tool(
        name: str, category: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register an MCP tool in the registry"""
        from common_lib.modules.db_studio.api_integration.schemas import McpToolCreate
        req = McpToolCreate(name=name, category=category, description=description)
        result = svc.register_mcp_tool(req)
        return result.model_dump()

    @mcp.tool()
    async def api_list_mcp_tools(
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List MCP tools in the registry"""
        results = svc.list_mcp_tools(category=category)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def api_register_mcp_resource(
        name: str, resource_type: str, uri_pattern: str,
        description: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register an MCP resource"""
        from common_lib.modules.db_studio.api_integration.schemas import McpResourceCreate
        req = McpResourceCreate(
            name=name, resource_type=resource_type, uri_pattern=uri_pattern,
            description=description,
        )
        result = svc.register_mcp_resource(req)
        return result.model_dump()

    @mcp.tool()
    async def api_list_mcp_resources(
        resource_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List MCP resources"""
        results = svc.list_mcp_resources(resource_type=resource_type)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def api_get_dashboard() -> Dict[str, Any]:
        """Get API integration dashboard with aggregated stats"""
        dash = svc.get_dashboard()
        return dash.model_dump()
