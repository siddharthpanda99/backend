"""MCP tools for Universal Query Execution Engine (UDS Module 07).

Exposes session management, query execution, transactions,
and capabilities to agents.
"""

import logging

logger = logging.getLogger(__name__)


def register_query_execution_tools(mcp_server):
    """Register all Query Execution Engine MCP tools."""

    from common_lib.modules.db_studio.query_execution import (
        QueryExecutionService,
        ExecuteRequest,
        BatchExecuteRequest,
        TransactionBeginRequest,
        TransactionRequest,
        SessionCreate,
    )

    svc = QueryExecutionService()

    @mcp_server.tool()
    async def execution_run(connection_id: str, statement: str,
                             mode: str = "execute", timeout_seconds: int = 30,
                             max_rows: int = 1000, database_type: str = "postgresql"):
        """Execute a single SQL statement against a database connection."""
        req = ExecuteRequest(
            connection_id=connection_id,
            statement=statement,
            mode=mode,
            timeout_seconds=timeout_seconds,
            max_rows=max_rows,
            database_type=database_type,
        )
        result = svc.execute(req)
        return result.model_dump()

    @mcp_server.tool()
    async def execution_batch(connection_id: str, statements: list,
                               stop_on_error: bool = False,
                               database_type: str = "postgresql"):
        """Execute multiple SQL statements sequentially."""
        req = BatchExecuteRequest(
            connection_id=connection_id,
            statements=statements,
            stop_on_error=stop_on_error,
            database_type=database_type,
        )
        result = svc.batch_execute(req)
        return result.model_dump()

    @mcp_server.tool()
    async def execution_begin_transaction(connection_id: str,
                                           database_type: str = "postgresql"):
        """Begin a new database transaction."""
        req = TransactionBeginRequest(
            connection_id=connection_id,
            database_type=database_type,
        )
        result = svc.begin_transaction(req)
        return result.model_dump()

    @mcp_server.tool()
    async def execution_commit_transaction(transaction_id: str):
        """Commit an active transaction."""
        req = TransactionRequest(transaction_id=transaction_id)
        result = svc.commit_transaction(req)
        return result.model_dump()

    @mcp_server.tool()
    async def execution_rollback_transaction(transaction_id: str):
        """Rollback an active transaction."""
        req = TransactionRequest(transaction_id=transaction_id)
        result = svc.rollback_transaction(req)
        return result.model_dump()

    @mcp_server.tool()
    async def execution_get_capabilities(database_type: str = "postgresql"):
        """Get capabilities for a database type."""
        results = svc.get_capabilities(database_type)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def execution_list_history(connection_id: str = None,
                                      status: str = None, limit: int = 20):
        """List execution history."""
        results = svc.list_history(connection_id=connection_id, status=status, limit=limit)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def execution_list_statistics(connection_id: str = None, limit: int = 20):
        """List query execution statistics."""
        results = svc.list_statistics(connection_id=connection_id, limit=limit)
        return [r.model_dump() for r in results]

    @mcp_server.tool()
    async def execution_list_errors(connection_id: str = None, limit: int = 20):
        """List execution errors."""
        results = svc.list_errors(connection_id=connection_id, limit=limit)
        return [r.model_dump() for r in results]
