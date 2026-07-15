import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("mcp.tools.database_connections")


def register_database_connections_tools(mcp: FastMCP):
    """Register all Database Connections (UDS Module 01) tools for agents & microservices."""

    @mcp.tool()
    async def database_list_connections(
        workspace_id: Optional[str] = None,
        environment: Optional[str] = None,
        db_type: Optional[str] = None,
        search: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List all database connections, optionally filtered by workspace, environment, db_type, or search text."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService, DatabaseConnectionCreate

        svc = DatabaseConnectionService()
        result = svc.list_connections(
            workspace_id=workspace_id,
            environment=environment or "development",
            db_type=db_type,
            search=search,
        )
        return result.model_dump()

    @mcp.tool()
    async def database_get_connection(connection_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific database connection by ID."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        conn = svc.get_connection(connection_id)
        return conn.model_dump() if conn else None

    @mcp.tool()
    async def database_create_connection(
        name: str,
        db_type: str,
        host: str = "localhost",
        port: Optional[int] = None,
        database: str = "",
        username: str = "",
        password: str = "",
        ssl: bool = False,
        environment: str = "development",
    ) -> Dict[str, Any]:
        """Create a new database connection profile."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService, DatabaseConnectionCreate, DBTypeId

        svc = DatabaseConnectionService()
        req = DatabaseConnectionCreate(
            name=name,
            db_type=DBTypeId(db_type),
            host=host,
            port=port,
            database=database,
            username=username,
            password=password,
            ssl=ssl,
            environment=environment,
        )
        return svc.create_connection(req).model_dump()

    @mcp.tool()
    async def database_delete_connection(connection_id: str) -> bool:
        """Delete a database connection by ID."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return svc.delete_connection(connection_id)

    @mcp.tool()
    async def database_test_connection(connection_id: str) -> Dict[str, Any]:
        """Test a database connection and record health check."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        result = svc.test_connection(connection_id)
        return {"success": result.success, "message": result.message}

    @mcp.tool()
    async def database_list_workspaces() -> List[Dict[str, Any]]:
        """List all connection workspaces."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return [w.model_dump() for w in svc.list_workspaces()]

    @mcp.tool()
    async def database_create_workspace(name: str, description: Optional[str] = None, environment: str = "development") -> Dict[str, Any]:
        """Create a new connection workspace."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService, WorkspaceCreate

        svc = DatabaseConnectionService()
        req = WorkspaceCreate(name=name, description=description, environment=environment)
        return svc.create_workspace(req).model_dump()

    @mcp.tool()
    async def database_list_tags() -> List[Dict[str, Any]]:
        """List all database connection tags."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return [t.model_dump() for t in svc.list_tags()]

    @mcp.tool()
    async def database_create_tag(name: str, color: str = "#6b7280") -> Dict[str, Any]:
        """Create a new tag for database connections."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService, TagCreate

        svc = DatabaseConnectionService()
        req = TagCreate(name=name, color=color)
        return svc.create_tag(req).model_dump()

    @mcp.tool()
    async def database_get_health_history(connection_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get health check history for a database connection."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return [h.model_dump() for h in svc.get_health_history(connection_id, limit=limit)]

    @mcp.tool()
    async def database_get_audit_log(connection_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get audit log entries, optionally filtered by connection ID."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return [a.model_dump() for a in svc.get_audit_log(connection_id=connection_id, limit=limit)]

    @mcp.tool()
    async def database_get_tables(connection_id: str) -> List[Dict[str, Any]]:
        """Get table metadata for a database connection."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return [t.model_dump() for t in svc.get_tables(connection_id)]

    @mcp.tool()
    async def database_get_collections(connection_id: str) -> List[Dict[str, Any]]:
        """Get collection metadata for a NoSQL database connection."""
        from common_lib.modules.db_studio.database_connections import DatabaseConnectionService

        svc = DatabaseConnectionService()
        return [c.model_dump() for c in svc.get_collections(connection_id)]
