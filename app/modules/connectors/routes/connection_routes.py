"""CRUD routes for user connections to connectors.

/api/v1/connections/ — manage user-specific connections
/api/v1/connections/{id}/test — test a connection
/api/v1/connectors/execute — execute a tool via a connection
/api/v1/connections/{id}/audit — connection changelog
"""

import uuid
import time
import logging
from typing import Optional, Any, Dict
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from sqlmodel import select
from sqlalchemy import func, or_

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.plugins.connectors.models.db import (
    ConnectorRecord,
    ConnectionRecord,
    ToolExecutionRecord,
    ConnectionAuditRecord,
)
from app.modules.connectors.schemas import (
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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["Connections"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a field-level diff between two dicts (old form_data vs new)."""
    diff: Dict[str, Any] = {}
    all_keys = set(list(before.keys()) + list(after.keys()))
    for key in all_keys:
        old_val = before.get(key)
        new_val = after.get(key)
        if old_val != new_val:
            diff[key] = {"old": old_val, "new": new_val}
    return diff


def _build_summary(action: str, diff: Dict[str, Any], record: ConnectionRecord) -> str:
    """Build a human-readable summary of what changed."""
    if action == "created":
        return f"Connection created — {record.connector_id}"
    if action == "deleted":
        return f"Connection deleted — {record.connector_id}"
    if action == "tested":
        return f"Connection tested — {record.connector_id}"
    if action == "updated":
        if not diff:
            return f"Connection updated — {record.connector_id}"
        changed_fields = list(diff.keys())
        if len(changed_fields) <= 3:
            return f"Updated {', '.join(changed_fields)}"
        return f"Updated {len(changed_fields)} fields"
    return f"{action} — {record.connector_id}"


def _record_audit(
    session: Any,
    connection_id: str,
    action: str,
    record: ConnectionRecord,
    diff: Optional[Dict[str, Any]] = None,
    changed_by: str = "default",
):
    """Insert a ConnectionAuditRecord entry."""
    audit = ConnectionAuditRecord(
        id=str(uuid.uuid4()),
        connection_id=connection_id,
        action=action,
        changed_by=changed_by,
        summary=_build_summary(action, diff or {}, record),
        diff=diff,
        metadata_json={
            "connector_id": record.connector_id,
            "status": record.status,
            "label": record.label,
        },
    )
    session.add(audit)


# ---------------------------------------------------------------------------
# CRUD Routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=ConnectionListResponse)
async def list_connections(
    user_id: Optional[str] = Query(None),
    connector_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    with next(get_session()) as session:
        stmt = select(ConnectionRecord)
        count_stmt = select(func.count()).select_from(ConnectionRecord)

        if user_id:
            stmt = stmt.where(ConnectionRecord.user_id == user_id)
            count_stmt = count_stmt.where(ConnectionRecord.user_id == user_id)

        if connector_id:
            stmt = stmt.where(ConnectionRecord.connector_id == connector_id)
            count_stmt = count_stmt.where(ConnectionRecord.connector_id == connector_id)

        if status:
            stmt = stmt.where(ConnectionRecord.status == status)
            count_stmt = count_stmt.where(ConnectionRecord.status == status)

        if search:
            pattern = f"%{search}%"
            filter_expr = or_(
                ConnectionRecord.label.ilike(pattern),
                ConnectionRecord.connector_id.ilike(pattern),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total = session.execute(count_stmt).scalar() or 0
        results = (
            session.execute(
                stmt.order_by(ConnectionRecord.updated_at.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return ConnectionListResponse(
            items=[ConnectionResponse.model_validate(r) for r in results],
            total=total,
        )


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: str):
    with next(get_session()) as session:
        record = session.get(ConnectionRecord, connection_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connection '{connection_id}' not found"
            )
        return ConnectionResponse.model_validate(record)


@router.post("/", response_model=ConnectionResponse, status_code=201)
async def create_connection(data: ConnectionCreate, user_id: str = "default"):
    """Create a new connection to a connector."""
    with next(get_session()) as session:
        connector = session.get(ConnectorRecord, data.connector_id)
        if not connector:
            raise HTTPException(
                status_code=404,
                detail=f"Connector '{data.connector_id}' not found. Create it first.",
            )

        connection_id = str(uuid.uuid4())
        record = ConnectionRecord(
            id=connection_id,
            connector_id=data.connector_id,
            user_id=user_id,
            auth_scheme=data.auth_scheme,
            key_id=data.key_id,
            status="active",
            label=data.label or f"{connector.name} connection",
            form_data=data.form_data or {},
            metadata_json=data.metadata_json or {},
        )
        session.add(record)

        # Audit: creation
        _record_audit(session, connection_id, "created", record, changed_by=user_id)

        session.commit()
        session.refresh(record)
        return ConnectionResponse.model_validate(record)


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(connection_id: str, data: ConnectionUpdate, user_id: str = "default"):
    with next(get_session()) as session:
        record = session.get(ConnectionRecord, connection_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connection '{connection_id}' not found"
            )

        update_data = data.model_dump(exclude_unset=True)

        # Capture before state for diff
        old_form_data = dict(record.form_data or {})
        old_label = record.label
        old_status = record.status

        for field, value in update_data.items():
            setattr(record, field, value)
        record.updated_at = datetime.utcnow()

        # Build diff for label + form_data changes
        diff: Dict[str, Any] = {}
        if "label" in update_data and update_data["label"] != old_label:
            diff["label"] = {"old": old_label, "new": update_data["label"]}
        if "form_data" in update_data:
            form_diff = _compute_diff(old_form_data, update_data["form_data"] or {})
            if form_diff:
                diff["form_data"] = form_diff
        if "status" in update_data and update_data["status"] != old_status:
            diff["status"] = {"old": old_status, "new": update_data["status"]}

        session.add(record)

        if diff:
            _record_audit(session, connection_id, "updated", record, diff=diff, changed_by=user_id)

        session.commit()
        session.refresh(record)
        return ConnectionResponse.model_validate(record)


@router.delete("/{connection_id}")
async def delete_connection(connection_id: str, user_id: str = "default"):
    with next(get_session()) as session:
        record = session.get(ConnectionRecord, connection_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connection '{connection_id}' not found"
            )

        # Audit: deletion (before deleting the record)
        _record_audit(session, connection_id, "deleted", record, changed_by=user_id)

        # Move audit records orphan — keep them in the log even after connection is deleted
        # No cascade needed, just let the audit entries remain as historical records

        session.delete(record)
        session.commit()
        return {"status": "success", "message": f"Connection '{connection_id}' deleted"}


@router.post("/{connection_id}/test", response_model=ConnectionTestResponse)
async def test_connection(connection_id: str, user_id: str = "default"):
    """Test a connection by resolving its API key and checking connectivity.
    Returns HTTP 200 on success (status="success") or HTTP 400 on failure (status="error").
    """
    from common_lib.modules.plugins.connectors.keys import get_connector_key_manager
    from common_lib.modules.plugins.connectors.models.connection import (
        Connection,
        ConnectionStatus,
    )

    with next(get_session()) as session:
        record = session.get(ConnectionRecord, connection_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connection '{connection_id}' not found"
            )

        conn = Connection(
            id=record.id,
            connector_id=record.connector_id,
            user_id=record.user_id,
            auth_scheme=record.auth_scheme,
            key_id=record.key_id,
            status=ConnectionStatus(record.status)
            if record.status
            else ConnectionStatus.ACTIVE,
            label=record.label,
        )

        key_manager = get_connector_key_manager()
        start = time.monotonic()

        try:
            key_value = key_manager.resolve(conn)
            if not key_value:
                raise ValueError("No key resolved")

            elapsed = (time.monotonic() - start) * 1000
            record.status = "active"
            record.error_message = None
            session.add(record)

            _record_audit(session, connection_id, "tested", record, changed_by=user_id)

            session.commit()

            return ConnectionTestResponse(
                status="success",
                message=f"Connection to '{record.connector_id}' verified",
                latency_ms=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            record.status = "failed"
            record.error_message = str(e)
            session.add(record)

            _record_audit(session, connection_id, "tested", record, diff={"error": str(e)}, changed_by=user_id)

            session.commit()

            return JSONResponse(
                status_code=400,
                content=ConnectionTestResponse(
                    status="error",
                    message=str(e),
                    latency_ms=round(elapsed, 1),
                ).model_dump(),
            )


@router.post("/{connection_id}/execute", response_model=ToolExecuteResponse)
async def execute_tool_on_connection(connection_id: str, request: ToolExecuteRequest):
    """Execute a connector tool using a specific connection."""
    from common_lib.modules.plugins.connectors.models.connection import (
        Connection as ConnModel,
        ConnectionStatus,
    )
    from app.modules.connectors.execute_engine import get_execution_engine

    with next(get_session()) as session:
        record = session.get(ConnectionRecord, connection_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Connection '{connection_id}' not found"
            )

        if record.status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Connection '{connection_id}' is not active (status: {record.status})",
            )

        conn = ConnModel(
            id=record.id,
            connector_id=record.connector_id,
            user_id=record.user_id,
            auth_scheme=record.auth_scheme,
            key_id=record.key_id,
            status=ConnectionStatus(record.status),
            label=record.label,
            form_data=record.form_data or {},
        )

        exec_id = str(uuid.uuid4())
        start = time.monotonic()
        try:
            eng = get_execution_engine()

            # Merge override_base_url into form_data if provided
            form_data = dict(record.form_data or {})
            if request.override_base_url:
                form_data["instance_url"] = request.override_base_url.rstrip("/")

            # Merge extra query_params into params so they flow through
            # as remaining query parameters (GET) or JSON body (POST)
            exec_params = dict(request.params)
            if request.query_params:
                exec_params.update(request.query_params)

            # TODO: wire request.headers into the HTTP request once the
            # engine signature supports per-request header overrides

            raw_result = eng.execute(
                connector_id=record.connector_id,
                tool_id=request.tool_id,
                params=exec_params,
                connection=conn,
                form_data=form_data,
            )

            http_status = None
            response_headers = None
            result = raw_result
            if isinstance(raw_result, dict) and "__exec_result__" in raw_result:
                http_status = raw_result.get("__http_status__")
                response_headers = raw_result.get("__response_headers__")
                result = raw_result["__exec_result__"]

            elapsed = (time.monotonic() - start) * 1000

            exec_record = ToolExecutionRecord(
                id=exec_id,
                connection_id=connection_id,
                connector_id=record.connector_id,
                tool_id=request.tool_id,
                params=request.params,
                result=result,
                status="success",
                duration_ms=round(elapsed, 1),
            )
            session.add(exec_record)
            session.commit()

            return ToolExecuteResponse(
                id=exec_id,
                status="success",
                result=result,
                duration_ms=round(elapsed, 1),
                http_status=http_status,
                response_headers=response_headers,
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            error_msg = str(e)

            exec_record = ToolExecutionRecord(
                id=exec_id,
                connection_id=connection_id,
                connector_id=record.connector_id,
                tool_id=request.tool_id,
                params=request.params,
                result=None,
                status="error",
                error_message=error_msg,
                duration_ms=round(elapsed, 1),
            )
            session.add(exec_record)
            session.commit()

            return ToolExecuteResponse(
                id=exec_id,
                status="error",
                error=error_msg,
                duration_ms=round(elapsed, 1),
            )


# ---------------------------------------------------------------------------
# Execution History
# ---------------------------------------------------------------------------


@router.get(
    "/{connection_id}/execute/history",
    response_model=ExecutionHistoryListResponse,
)
async def get_execution_history(
    connection_id: str,
    tool_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
):
    """List past tool executions for a connection, newest first."""
    with next(get_session()) as session:
        stmt = select(ToolExecutionRecord).where(
            ToolExecutionRecord.connection_id == connection_id
        )
        count_stmt = (
            select(func.count())
            .select_from(ToolExecutionRecord)
            .where(ToolExecutionRecord.connection_id == connection_id)
        )

        if tool_id:
            stmt = stmt.where(ToolExecutionRecord.tool_id == tool_id)
            count_stmt = count_stmt.where(ToolExecutionRecord.tool_id == tool_id)

        total = session.execute(count_stmt).scalar() or 0
        results = (
            session.execute(
                stmt.order_by(ToolExecutionRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return ExecutionHistoryListResponse(
            items=[ExecutionHistoryResponse.model_validate(r) for r in results],
            total=total,
        )


# ---------------------------------------------------------------------------
# Connection Audit / Changelog
# ---------------------------------------------------------------------------


@router.get(
    "/{connection_id}/audit",
    response_model=AuditListResponse,
)
async def get_connection_audit_log(
    connection_id: str,
    action: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List audit entries for a connection, newest first."""
    with next(get_session()) as session:
        stmt = select(ConnectionAuditRecord).where(
            ConnectionAuditRecord.connection_id == connection_id
        )
        count_stmt = (
            select(func.count())
            .select_from(ConnectionAuditRecord)
            .where(ConnectionAuditRecord.connection_id == connection_id)
        )

        if action:
            stmt = stmt.where(ConnectionAuditRecord.action == action)
            count_stmt = count_stmt.where(ConnectionAuditRecord.action == action)

        total = session.execute(count_stmt).scalar() or 0
        results = (
            session.execute(
                stmt.order_by(ConnectionAuditRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            .scalars()
            .all()
        )

        return AuditListResponse(
            items=[AuditEntryResponse.model_validate(r) for r in results],
            total=total,
        )


# ---------------------------------------------------------------------------
# Alternative execute endpoint under /connectors/execute
# ---------------------------------------------------------------------------

_execute_router = APIRouter(prefix="/connectors", tags=["Connectors"])


@_execute_router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool(request: ToolExecuteRequest):
    """Execute a tool by connection_id (alternative path)."""
    return await execute_tool_on_connection(request.connection_id, request)
