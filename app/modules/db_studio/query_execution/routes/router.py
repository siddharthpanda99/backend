"""Universal Query Execution Engine API routes.
Thin wrapper — all logic in common_lib.modules.db_studio.query_execution.service.
"""

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.query_execution import (
    QueryExecutionService,
    SessionCreate, SessionOut,
    ExecuteRequest, ExecuteResponse,
    BatchExecuteRequest, BatchExecuteResponse,
    CancelRequest,
    TransactionBeginRequest, TransactionActionResponse, TransactionRequest,
    CapabilityOut,
    ExecutionHistoryOut, ExecutionErrorOut, QueryStatisticsOut, TransactionHistoryOut,
)

router = APIRouter(prefix="/api/v1/execution", tags=["Universal Query Execution Engine"])
svc = QueryExecutionService()


# ── Sessions ──────────────────────────────────────────────────────────

@router.post("/sessions", response_model=SessionOut)
def create_session(req: SessionCreate):
    return svc.create_session(req)


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(session_id: str):
    s = svc.get_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    return s


@router.delete("/sessions/{session_id}")
def close_session(session_id: str):
    if not svc.close_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    connection_id: str = None,
    status: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_sessions(connection_id, status, limit)


# ── Execution ─────────────────────────────────────────────────────────

@router.post("/run", response_model=ExecuteResponse)
def execute(req: ExecuteRequest):
    return svc.execute(req)


@router.post("/batch", response_model=BatchExecuteResponse)
def batch_execute(req: BatchExecuteRequest):
    return svc.batch_execute(req)


@router.post("/cancel", response_model=bool)
def cancel(req: CancelRequest):
    return svc.cancel(req)


# ── Transactions ──────────────────────────────────────────────────────

@router.post("/transaction/begin", response_model=TransactionActionResponse)
def begin_transaction(req: TransactionBeginRequest):
    return svc.begin_transaction(req)


@router.post("/transaction/commit", response_model=TransactionActionResponse)
def commit_transaction(req: TransactionRequest):
    return svc.commit_transaction(req)


@router.post("/transaction/rollback", response_model=TransactionActionResponse)
def rollback_transaction(req: TransactionRequest):
    return svc.rollback_transaction(req)


# ── Capabilities ──────────────────────────────────────────────────────

@router.get("/capabilities/{database_type}", response_model=list[CapabilityOut])
def get_capabilities(database_type: str):
    return svc.get_capabilities(database_type)


@router.post("/capabilities", response_model=CapabilityOut)
def register_capability(
    database_type: str,
    capability: str,
    supported: bool = True,
    version: str = None,
    notes: str = None,
):
    return svc.register_capability(database_type, capability, supported, version, notes)


# ── History ───────────────────────────────────────────────────────────

@router.get("/history", response_model=list[ExecutionHistoryOut])
def list_history(
    connection_id: str = None,
    status: str = None,
    session_id: str = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_history(connection_id, status, session_id, offset, limit)


@router.get("/errors", response_model=list[ExecutionErrorOut])
def list_errors(
    connection_id: str = None,
    category: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_errors(connection_id, category, limit)


@router.get("/statistics", response_model=list[QueryStatisticsOut])
def list_statistics(
    connection_id: str = None,
    statement_type: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_statistics(connection_id, statement_type, limit)


@router.get("/transaction-history", response_model=list[TransactionHistoryOut])
def list_transaction_history(
    connection_id: str = None,
    session_id: str = None,
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_transaction_history(connection_id, session_id, limit)
