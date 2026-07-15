import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.data_browser")


def register_data_browser_tools(mcp: FastMCP):
    """Register all Data Browser (UDS Module 04) tools for agents & microservices."""

    @mcp.tool()
    async def data_query(
        connection_id: str,
        table: str,
        schema_name: str = "public",
        page: int = 1,
        page_size: int = 50,
        sort_column: Optional[str] = None,
        sort_direction: str = "ASC",
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch paginated data from a table with optional sorting and search."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, DataQueryRequest

        svc = DataBrowserService()
        req = DataQueryRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            table=table,
            page=page,
            page_size=page_size,
            sort_column=sort_column,
            sort_direction=sort_direction,
            search=search,
        )
        return svc.query_data(req).model_dump()

    @mcp.tool()
    async def data_preview_row(
        connection_id: str,
        table: str,
        primary_key: Dict[str, Any],
        schema_name: str = "public",
    ) -> Dict[str, Any]:
        """Fetch a single row by primary key for inspection."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, RowPreviewRequest

        svc = DataBrowserService()
        req = RowPreviewRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            table=table,
            primary_key=primary_key,
        )
        return svc.preview_row(req).model_dump()

    @mcp.tool()
    async def data_insert_row(
        connection_id: str,
        table: str,
        data: Dict[str, Any],
        schema_name: str = "public",
    ) -> Dict[str, Any]:
        """Insert a new row into a table."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, RowInsertRequest

        svc = DataBrowserService()
        req = RowInsertRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            table=table,
            data=data,
        )
        return svc.insert_row(req).model_dump()

    @mcp.tool()
    async def data_update_row(
        connection_id: str,
        table: str,
        primary_key: Dict[str, Any],
        data: Dict[str, Any],
        schema_name: str = "public",
    ) -> Dict[str, Any]:
        """Update a row by primary key."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, RowUpdateRequest

        svc = DataBrowserService()
        req = RowUpdateRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            table=table,
            primary_key=primary_key,
            data=data,
        )
        return svc.update_row(req).model_dump()

    @mcp.tool()
    async def data_delete_row(
        connection_id: str,
        table: str,
        primary_key: Dict[str, Any],
        schema_name: str = "public",
    ) -> Dict[str, Any]:
        """Delete a row by primary key."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, RowDeleteRequest

        svc = DataBrowserService()
        req = RowDeleteRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            table=table,
            primary_key=primary_key,
        )
        return svc.delete_row(req).model_dump()

    @mcp.tool()
    async def data_save_filter(
        connection_id: str,
        name: str,
        table_name: str,
        filters: List[Dict[str, Any]],
        schema_name: str = "public",
    ) -> Dict[str, Any]:
        """Save a filter preset for future reuse."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, SavedFilterCreate, FilterDef

        svc = DataBrowserService()
        filter_defs = [FilterDef(**f) for f in filters]
        req = SavedFilterCreate(
            connection_id=connection_id,
            name=name,
            schema_name=schema_name,
            table_name=table_name,
            filters=filter_defs,
        )
        return svc.save_filter(req).model_dump()

    @mcp.tool()
    async def data_list_filters(
        connection_id: Optional[str] = None,
        table: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List saved filter presets."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService

        svc = DataBrowserService()
        return [f.model_dump() for f in svc.list_saved_filters(connection_id=connection_id, table_name=table)]

    @mcp.tool()
    async def data_save_view(
        connection_id: str,
        name: str,
        table_name: str,
        columns: List[Dict[str, Any]],
        schema_name: str = "public",
        sort_column: Optional[str] = None,
        sort_direction: str = "ASC",
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """Save a column layout view preset."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, SavedViewCreate, ColumnViewDef

        svc = DataBrowserService()
        col_defs = [ColumnViewDef(**c) for c in columns]
        req = SavedViewCreate(
            connection_id=connection_id,
            name=name,
            schema_name=schema_name,
            table_name=table_name,
            columns=col_defs,
            sort_column=sort_column,
            sort_direction=sort_direction,
            page_size=page_size,
        )
        return svc.save_view(req).model_dump()

    @mcp.tool()
    async def data_list_views(
        connection_id: Optional[str] = None,
        table: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List saved column layout view presets."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService

        svc = DataBrowserService()
        return [v.model_dump() for v in svc.list_saved_views(connection_id=connection_id, table_name=table)]

    @mcp.tool()
    async def data_export(
        connection_id: str,
        table_name: str,
        format: str = "csv",
        schema_name: str = "public",
        max_rows: int = 10000,
    ) -> Dict[str, Any]:
        """Export table data (csv, json, or xlsx)."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService, ExportRequest

        svc = DataBrowserService()
        req = ExportRequest(
            connection_id=connection_id,
            schema_name=schema_name,
            table_name=table_name,
            format=format,
            max_rows=max_rows,
        )
        return svc.export_data(req).model_dump()

    @mcp.tool()
    async def data_change_history(
        connection_id: Optional[str] = None,
        table: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List recent data change history (inserts, updates, deletes)."""
        from common_lib.modules.db_studio.data_browser import DataBrowserService

        svc = DataBrowserService()
        return [c.model_dump() for c in svc.list_change_history(connection_id=connection_id, table_name=table, limit=limit)]
