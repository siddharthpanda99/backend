"""CRUD routes for user connections to connectors.

/api/v1/connections/ — manage user-specific connections
/api/v1/connections/{id}/test — test a connection
/api/v1/connectors/execute — execute a tool via a connection
/api/v1/connections/{id}/audit — connection changelog

All logic delegated to common_lib.modules.connectors.connection_service.ConnectionService.
Execution engine is injected from Backend to avoid circular dependencies.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.connectors.schemas import (
    ConnectionCreate,
    ConnectionUpdate,
    ConnectionResponse,
    ConnectionListResponse,
    ConnectionTestResponse,
    ToolExecuteRequest,
    ToolExecuteResponse,
    ExecutionHistoryResponse,
    ExecutionHistoryListResponse,
    AuditEntryResponse,
    AuditListResponse,
)
from common_lib.modules.connectors.connection_service import ConnectionService
from app.modules.connectors.execute_engine import get_execution_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["Connections"])

# Alternative execute endpoint router
_execute_router = APIRouter(prefix="/connectors", tags=["Connectors"])


@router.get("/", response_model=ConnectionListResponse)
async def list_connections(
    user_id: Optional[str] = Query(None),
    connector_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return ConnectionService.list_connections(
        user_id=user_id, connector_id=connector_id, status=status,
        search=search, offset=offset, limit=limit,
    )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: str):
    return ConnectionService.get_connection(connection_id)


@router.post("/", response_model=ConnectionResponse, status_code=201)
async def create_connection(data: ConnectionCreate, user_id: str = "default"):
    return ConnectionService.create_connection(data, user_id)


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(connection_id: str, data: ConnectionUpdate, user_id: str = "default"):
    return ConnectionService.update_connection(connection_id, data, user_id)


@router.delete("/{connection_id}")
async def delete_connection(connection_id: str, user_id: str = "default"):
    return ConnectionService.delete_connection(connection_id, user_id)


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(connection_id: str, user_id: str = "default"):
    return ConnectionService.test_connection(connection_id, user_id)


@router.post("/{connection_id}/execute", response_model=ToolExecuteResponse)
async def execute_tool_on_connection(connection_id: str, request: ToolExecuteRequest):
    eng = get_execution_engine()
    return ConnectionService.execute_tool_on_connection(
        connection_id, request, eng.execute,
    )


# ---------------------------------------------------------------------------
# Execution History
# ---------------------------------------------------------------------------


@router.get("/{connection_id}/execute/history", response_model=ExecutionHistoryListResponse)
async def get_execution_history(
    connection_id: str,
    tool_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
):
    return ConnectionService.get_execution_history(connection_id, tool_id, offset, limit)


# ---------------------------------------------------------------------------
# Connection Audit / Changelog
# ---------------------------------------------------------------------------


@router.get("/{connection_id}/audit", response_model=AuditListResponse)
async def get_connection_audit_log(
    connection_id: str,
    action: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return ConnectionService.get_connection_audit_log(connection_id, action, offset, limit)


# ---------------------------------------------------------------------------
# Alternative execute endpoint under /connectors/execute
# ---------------------------------------------------------------------------


@_execute_router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest):
    """Execute a tool by connection_id (alternative path)."""
    return await execute_tool_on_connection(request.connection_id, request)
