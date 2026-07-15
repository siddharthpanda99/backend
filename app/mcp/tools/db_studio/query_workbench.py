import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.query_workbench")


def register_query_workbench_tools(mcp: FastMCP):
    """Register all Query Workbench (UDS Module 02) tools for agents & microservices."""

    @mcp.tool()
    async def query_execute(
        connection_id: str,
        sql: str,
        timeout_seconds: int = 30,
        max_rows: int = 1000,
    ) -> Dict[str, Any]:
        """Execute a SQL query against a connected database and return results."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService, QueryExecuteRequest

        svc = QueryWorkbenchService()
        req = QueryExecuteRequest(
            connection_id=connection_id,
            sql=sql,
            timeout_seconds=timeout_seconds,
            max_rows=max_rows,
        )
        return svc.execute_query(req).model_dump()

    @mcp.tool()
    async def query_explain(connection_id: str, sql: str) -> Dict[str, Any]:
        """Run EXPLAIN ANALYZE on a SQL query to get the query plan."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService, ExplainRequest

        svc = QueryWorkbenchService()
        req = ExplainRequest(connection_id=connection_id, sql=sql, analyze=True)
        return svc.explain_query(req).model_dump()

    @mcp.tool()
    async def query_batch(
        connection_id: str,
        statements: List[str],
        timeout_seconds: int = 60,
        stop_on_error: bool = False,
    ) -> Dict[str, Any]:
        """Execute multiple SQL statements sequentially against a connected database."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService, BatchExecuteRequest

        svc = QueryWorkbenchService()
        req = BatchExecuteRequest(
            connection_id=connection_id,
            statements=statements,
            timeout_seconds=timeout_seconds,
            stop_on_error=stop_on_error,
        )
        return svc.batch_execute(req).model_dump()

    @mcp.tool()
    async def saved_queries_list(
        search: Optional[str] = None,
        folder: Optional[str] = None,
        database_type: Optional[str] = None,
        favorites_only: bool = False,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List saved queries, optionally filtered by search text, folder, database type, or favorites."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.list_saved_queries(
            search=search,
            folder=folder,
            database_type=database_type,
            favorites_only=favorites_only,
            limit=limit,
        ).model_dump()

    @mcp.tool()
    async def saved_queries_create(
        name: str,
        sql: str,
        description: Optional[str] = None,
        connection_id: Optional[str] = None,
        database_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder: Optional[str] = None,
        is_favorite: bool = False,
    ) -> Dict[str, Any]:
        """Save a query for later reuse."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService, SavedQueryCreate

        svc = QueryWorkbenchService()
        req = SavedQueryCreate(
            name=name,
            sql=sql,
            description=description,
            connection_id=connection_id,
            database_type=database_type,
            tags=tags or [],
            folder=folder,
            is_favorite=is_favorite,
        )
        return svc.create_saved_query(req).model_dump()

    @mcp.tool()
    async def saved_queries_delete(query_id: str) -> bool:
        """Delete a saved query by ID."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.delete_saved_query(query_id)

    @mcp.tool()
    async def snippets_list(
        search: Optional[str] = None,
        category: Optional[str] = None,
        database_type: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List reusable code snippets, optionally filtered by search text, category, or database type."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.list_snippets(
            search=search,
            category=category,
            database_type=database_type,
            limit=limit,
        ).model_dump()

    @mcp.tool()
    async def snippets_create(
        name: str,
        prefix: str,
        code: str,
        description: Optional[str] = None,
        category: str = "general",
        database_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a reusable code snippet for the query workbench."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService, SnippetCreate

        svc = QueryWorkbenchService()
        req = SnippetCreate(
            name=name,
            prefix=prefix,
            code=code,
            description=description,
            category=category,
            database_type=database_type,
            tags=tags or [],
        )
        return svc.create_snippet(req).model_dump()

    @mcp.tool()
    async def snippets_delete(snippet_id: str) -> bool:
        """Delete a snippet by ID."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.delete_snippet(snippet_id)

    @mcp.tool()
    async def templates_list(
        search: Optional[str] = None,
        category: Optional[str] = None,
        database_type: Optional[str] = None,
        builtin_only: bool = False,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List query templates, optionally filtered by search, category, database type, or builtin-only."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.list_templates(
            search=search,
            category=category,
            database_type=database_type,
            builtin_only=builtin_only,
            limit=limit,
        ).model_dump()

    @mcp.tool()
    async def templates_apply(template_id: str, params: Dict[str, Any]) -> str:
        """Apply a query template with parameters to generate executable SQL."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        sql = svc.apply_template(template_id, params)
        if sql is None:
            raise ValueError(f"Template '{template_id}' not found")
        return sql

    @mcp.tool()
    async def history_list(
        connection_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List query execution history, optionally filtered by connection, status, or search text."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.list_history(
            connection_id=connection_id,
            status=status,
            search=search,
            limit=limit,
        ).model_dump()

    @mcp.tool()
    async def history_clear(connection_id: Optional[str] = None) -> int:
        """Clear query execution history, optionally filtered by connection ID."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return svc.clear_history(connection_id=connection_id)

    @mcp.tool()
    async def query_list_connections() -> List[Dict[str, Any]]:
        """List all available database connections for the query workbench toolbar."""
        from common_lib.modules.db_studio.query_workbench import QueryWorkbenchService

        svc = QueryWorkbenchService()
        return [c.model_dump() for c in svc.list_connections_brief()]
