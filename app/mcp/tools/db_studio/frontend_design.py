"""Module 30 — Frontend Architecture & Design System MCP tools."""
from typing import Any, Dict, List, Optional
from app.mcp.fastmcp_compat import FastMCP

from common_lib.modules.db_studio.frontend_design.service import DesignSystemService

svc = DesignSystemService()


def register_frontend_design_tools(mcp: FastMCP):
    """Register all frontend design tools with the MCP server."""

    @mcp.tool()
    async def ux_set_preference(
        user_id: str, category: str, key: str, value: str,
    ) -> Dict[str, Any]:
        """Set a user preference (upsert)"""
        from common_lib.modules.db_studio.frontend_design.schemas import UserPreferenceCreate
        req = UserPreferenceCreate(user_id=user_id, category=category, key=key, value=value)
        result = svc.set_preference(req)
        return result.model_dump()

    @mcp.tool()
    async def ux_get_preference(user_id: str, category: str, key: str) -> Optional[Dict[str, Any]]:
        """Get a specific user preference"""
        result = svc.get_preference(user_id, category, key)
        return result.model_dump() if result else None

    @mcp.tool()
    async def ux_list_preferences(
        user_id: Optional[str] = None, category: Optional[str] = None, limit: int = 100,
    ) -> Dict[str, Any]:
        """List user preferences"""
        items, total = svc.list_preferences(user_id=user_id, category=category, limit=limit)
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def ux_add_recent_item(
        user_id: str, item_type: str, item_id: str, item_name: str,
    ) -> Dict[str, Any]:
        """Add a recent item for a user"""
        from common_lib.modules.db_studio.frontend_design.schemas import RecentItemCreate
        req = RecentItemCreate(user_id=user_id, item_type=item_type, item_id=item_id, item_name=item_name)
        result = svc.add_recent_item(req)
        return result.model_dump()

    @mcp.tool()
    async def ux_list_recent_items(
        user_id: str, item_type: Optional[str] = None, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """List recent items for a user"""
        results = svc.list_recent_items(user_id, item_type=item_type, limit=limit)
        return [r.model_dump() for r in results]

    @mcp.tool()
    async def ux_set_ui_state(user_id: str, state_key: str, state_value: str) -> Dict[str, Any]:
        """Set UI state (upsert)"""
        from common_lib.modules.db_studio.frontend_design.schemas import UiStateCreate
        req = UiStateCreate(user_id=user_id, state_key=state_key, state_value=state_value)
        result = svc.set_ui_state(req)
        return result.model_dump()

    @mcp.tool()
    async def ux_get_ui_state(user_id: str, state_key: str) -> Optional[Dict[str, Any]]:
        """Get UI state by key"""
        result = svc.get_ui_state(user_id, state_key)
        return result.model_dump() if result else None

    @mcp.tool()
    async def ux_create_notification(
        user_id: str, title: str, message: Optional[str] = None,
        notification_type: str = "info",
    ) -> Dict[str, Any]:
        """Create a notification for a user"""
        from common_lib.modules.db_studio.frontend_design.schemas import NotificationCreate
        req = NotificationCreate(user_id=user_id, title=title, message=message, notification_type=notification_type)
        result = svc.create_notification(req)
        return result.model_dump()

    @mcp.tool()
    async def ux_list_notifications(
        user_id: str, is_read: Optional[bool] = None,
        notification_type: Optional[str] = None, limit: int = 50,
    ) -> Dict[str, Any]:
        """List notifications for a user"""
        items, total = svc.list_notifications(user_id=user_id, is_read=is_read, notification_type=notification_type, limit=limit)
        return {"total": total, "items": [i.model_dump() for i in items]}

    @mcp.tool()
    async def ux_mark_notification_read(notification_id: str) -> Optional[Dict[str, Any]]:
        """Mark a notification as read"""
        result = svc.mark_notification_read(notification_id)
        return result.model_dump() if result else None

    @mcp.tool()
    async def ux_mark_all_read(user_id: str) -> Dict[str, Any]:
        """Mark all notifications as read for a user"""
        count = svc.mark_all_read(user_id)
        return {"marked_read": count}

    @mcp.tool()
    async def ux_cache_query(
        user_id: str, query_text: str,
        result_json: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        ttl_seconds: int = 300,
    ) -> Dict[str, Any]:
        """Cache a query result"""
        from common_lib.modules.db_studio.frontend_design.schemas import CachedQueryCreate
        req = CachedQueryCreate(
            user_id=user_id, query_text=query_text, result_json=result_json,
            execution_time_ms=execution_time_ms, ttl_seconds=ttl_seconds,
        )
        result = svc.cache_query(req)
        return result.model_dump()

    @mcp.tool()
    async def ux_get_cached_query(query_hash: str) -> Optional[Dict[str, Any]]:
        """Get a cached query by hash"""
        result = svc.get_cached_query(query_hash)
        return result.model_dump() if result else None

    @mcp.tool()
    async def ux_purge_expired_queries() -> Dict[str, Any]:
        """Purge all expired cached queries"""
        count = svc.purge_expired_queries()
        return {"purged": count}

    @mcp.tool()
    async def ux_get_dashboard() -> Dict[str, Any]:
        """Get design system dashboard with aggregated stats"""
        dash = svc.get_dashboard()
        return dash.model_dump()
