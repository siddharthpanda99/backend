import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.schema_browser")


def register_schema_browser_tools(mcp: FastMCP):
    """Register all Schema Browser (UDS Module 03) tools for agents & microservices."""

    @mcp.tool()
    async def schema_browse(
        connection_id: str,
        parent_id: Optional[str] = None,
        object_type: Optional[str] = None,
        schema_name: Optional[str] = None,
        refresh: bool = False,
    ) -> Dict[str, Any]:
        """Browse the schema tree for a database connection. Root level returns schemas, drill-down returns tables then columns."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, TreeBrowseRequest

        svc = SchemaBrowserService()
        req = TreeBrowseRequest(
            connection_id=connection_id,
            parent_id=parent_id,
            object_type=object_type,
            schema_name=schema_name,
            refresh=refresh,
        )
        return svc.browse(req).model_dump()

    @mcp.tool()
    async def schema_object_detail(
        connection_id: str,
        object_type: str,
        object_name: str,
        schema_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get detailed metadata for a schema object (table columns, constraints, indexes, etc.)."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, ObjectDetailRequest

        svc = SchemaBrowserService()
        req = ObjectDetailRequest(
            connection_id=connection_id,
            object_type=object_type,
            object_name=object_name,
            schema_name=schema_name or "public",
        )
        return svc.get_object_detail(req).model_dump()

    @mcp.tool()
    async def schema_search(
        connection_id: str,
        query: str,
        object_types: Optional[List[str]] = None,
        schema_name: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Search across cached metadata objects by name or description."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, SearchRequest

        svc = SchemaBrowserService()
        req = SearchRequest(
            connection_id=connection_id,
            query=query,
            object_types=object_types,
            schema_name=schema_name,
            limit=limit,
        )
        return svc.search(req).model_dump()

    @mcp.tool()
    async def schema_refresh_cache(
        connection_id: str,
        schema_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Refresh cached metadata from the live database connection."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, RefreshRequest

        svc = SchemaBrowserService()
        req = RefreshRequest(connection_id=connection_id, schema_name=schema_name)
        return svc.refresh_metadata(req).model_dump()

    @mcp.tool()
    async def schema_list_favorites(connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List favorite/pinned schema objects."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService

        svc = SchemaBrowserService()
        return [f.model_dump() for f in svc.list_favorites(connection_id=connection_id)]

    @mcp.tool()
    async def schema_add_favorite(
        connection_id: str,
        object_type: str,
        object_path: str,
        label: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a schema object to favorites for quick access."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, FavoriteCreate

        svc = SchemaBrowserService()
        req = FavoriteCreate(
            connection_id=connection_id,
            object_type=object_type,
            object_path=object_path,
            label=label,
            notes=notes,
        )
        return svc.add_favorite(req).model_dump()

    @mcp.tool()
    async def schema_remove_favorite(favorite_id: str) -> bool:
        """Remove a favorite schema object."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService

        svc = SchemaBrowserService()
        return svc.remove_favorite(favorite_id)

    @mcp.tool()
    async def schema_list_recent(connection_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List recently viewed schema objects."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService

        svc = SchemaBrowserService()
        return [r.model_dump() for r in svc.list_recent(connection_id=connection_id, limit=limit)]

    @mcp.tool()
    async def schema_create_snapshot(
        connection_id: str,
        label: str,
        schema_name: str = "public",
        environment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a point-in-time schema snapshot for comparison."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, SnapshotCreateRequest

        svc = SchemaBrowserService()
        req = SnapshotCreateRequest(
            connection_id=connection_id,
            label=label,
            schema_name=schema_name,
            environment=environment,
        )
        return svc.create_snapshot(req).model_dump()

    @mcp.tool()
    async def schema_list_snapshots(connection_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List schema snapshots."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService

        svc = SchemaBrowserService()
        return [s.model_dump() for s in svc.list_snapshots(connection_id=connection_id)]

    @mcp.tool()
    async def schema_compare(
        connection_id: str,
        schema_name: str = "public",
        snapshot_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Compare a schema against a snapshot or another schema to find differences."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, CompareRequest

        svc = SchemaBrowserService()
        req = CompareRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            snapshot_id=snapshot_id,
        )
        return svc.compare(req).model_dump()

    @mcp.tool()
    async def schema_generate_ddl(
        connection_id: str,
        schema_name: str,
        object_name: str,
        object_type: str = "table",
    ) -> Dict[str, Any]:
        """Generate DDL (CREATE TABLE/INDEX) for a schema object."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, DDLRequest

        svc = SchemaBrowserService()
        req = DDLRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            object_name=object_name,
            object_type=object_type,
        )
        return svc.generate_ddl(req).model_dump()

    @mcp.tool()
    async def schema_list_comments(
        connection_id: Optional[str] = None,
        object_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List documentation comments/annotations for schema objects."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService

        svc = SchemaBrowserService()
        return [c.model_dump() for c in svc.list_comments(connection_id=connection_id, object_type=object_type)]

    @mcp.tool()
    async def schema_add_comment(
        connection_id: str,
        object_type: str,
        object_path: str,
        content: str,
        title: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Add a documentation comment to a schema object."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService, CommentCreate

        svc = SchemaBrowserService()
        req = CommentCreate(
            connection_id=connection_id,
            object_type=object_type,
            object_path=object_path,
            content=content,
            title=title,
            tags=tags or [],
        )
        return svc.add_comment(req).model_dump()

    @mcp.tool()
    async def schema_delete_comment(comment_id: str) -> bool:
        """Delete a documentation comment."""
        from common_lib.modules.db_studio.schema_browser import SchemaBrowserService

        svc = SchemaBrowserService()
        return svc.delete_comment(comment_id)
