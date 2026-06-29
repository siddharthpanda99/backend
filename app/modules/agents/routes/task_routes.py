"""Task Queue routes — thin wrappers around TaskQueueService."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session as SQLSession

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.models.task_models import TaskStatus
from common_lib.modules.agents.services.task_queue_service import TaskQueueService

router = APIRouter()
svc = TaskQueueService()


def _or_404(result, detail="Resource not found"):
    if result is None:
        raise HTTPException(status_code=404, detail=detail)
    return result


def _handle_task_error(e: ValueError):
    msg = str(e)
    if "not found" in msg.lower():
        raise HTTPException(status_code=404, detail=msg)
    raise HTTPException(status_code=409, detail=msg)


# ── Request / Response schemas ──────────────────────────────────────────────────


class CreateTaskRequest(BaseModel):
    title: str
    description: str = ""
    agent_id: str = ""
    priority: int = 0
    parent_task_id: Optional[str] = None
    concurrency_key: str = ""
    tags: List[str] = []
    metadata: dict = {}
    max_attempts: int = 3


class ClaimTaskRequest(BaseModel):
    agent_id: str
    max_concurrent: int = 5


class StartTaskRequest(BaseModel):
    agent_id: str
    session_id: Optional[str] = None
    work_dir: Optional[str] = None


class CompleteTaskRequest(BaseModel):
    agent_id: str
    result_summary: str = ""


class FailTaskRequest(BaseModel):
    agent_id: str
    error_message: str = ""
    failure_type: str = "logic"


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    priority: int
    agent_id: str
    assigned_by: str
    session_id: Optional[str]
    work_dir: Optional[str]
    parent_task_id: Optional[str]
    attempt_count: int
    max_attempts: int
    last_failure_reason: Optional[str]
    last_failure_type: Optional[str]
    concurrency_key: str
    tags: list
    metadata_json: dict
    created_at: Optional[str]
    updated_at: Optional[str]
    claimed_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class AttemptResponse(BaseModel):
    id: str
    task_id: str
    attempt_number: int
    status: str
    failure_type: Optional[str]
    session_id: Optional[str]
    work_dir: Optional[str]
    result_summary: Optional[str]
    error_message: Optional[str]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


def _task_to_response(t) -> TaskResponse:
    return TaskResponse(
        id=t.id,
        title=t.title,
        description=t.description or "",
        status=t.status,
        priority=t.priority,
        agent_id=t.agent_id or "",
        assigned_by=t.assigned_by or "",
        session_id=t.session_id,
        work_dir=t.work_dir,
        parent_task_id=t.parent_task_id,
        attempt_count=t.attempt_count,
        max_attempts=t.max_attempts,
        last_failure_reason=t.last_failure_reason,
        last_failure_type=t.last_failure_type,
        concurrency_key=t.concurrency_key or "",
        tags=t.tags or [],
        metadata_json=t.metadata_json or {},
        created_at=t.created_at.isoformat() if t.created_at else None,
        updated_at=t.updated_at.isoformat() if t.updated_at else None,
        claimed_at=t.claimed_at.isoformat() if t.claimed_at else None,
        started_at=t.started_at.isoformat() if t.started_at else None,
        completed_at=t.completed_at.isoformat() if t.completed_at else None,
    )


def _attempt_to_response(a) -> AttemptResponse:
    return AttemptResponse(
        id=a.id,
        task_id=a.task_id,
        attempt_number=a.attempt_number,
        status=a.status,
        failure_type=a.failure_type,
        session_id=a.session_id,
        work_dir=a.work_dir,
        result_summary=a.result_summary,
        error_message=a.error_message,
        created_at=a.created_at.isoformat() if a.created_at else None,
        started_at=a.started_at.isoformat() if a.started_at else None,
        completed_at=a.completed_at.isoformat() if a.completed_at else None,
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/", response_model=dict)
def create_task(
    body: CreateTaskRequest,
    db: SQLSession = Depends(get_db_session),
):
    task = svc.create_task(
        title=body.title,
        description=body.description,
        agent_id=body.agent_id,
        assigned_by="",
        priority=body.priority,
        parent_task_id=body.parent_task_id,
        concurrency_key=body.concurrency_key,
        tags=body.tags,
        metadata=body.metadata,
        max_attempts=body.max_attempts,
        db=db,
    )
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.get("/", response_model=dict)
def list_tasks(
    status: Optional[str] = Query(None),
    agent_id: Optional[str] = Query(None),
    parent_task_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: SQLSession = Depends(get_db_session),
):
    tasks = svc.list_tasks(
        status=status,
        agent_id=agent_id,
        parent_task_id=parent_task_id,
        limit=limit,
        offset=offset,
        db=db,
    )
    return {"success": True, "data": [_task_to_response(t).model_dump() for t in tasks]}


@router.get("/{task_id}", response_model=dict)
def get_task(
    task_id: str,
    db: SQLSession = Depends(get_db_session),
):
    task = _or_404(svc.get_task(task_id, db=db), f"Task {task_id} not found")
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.post("/{task_id}/claim", response_model=dict)
def claim_task(
    task_id: str,
    body: ClaimTaskRequest,
    db: SQLSession = Depends(get_db_session),
):
    try:
        task = svc.claim_task(
            task_id, body.agent_id, max_concurrent=body.max_concurrent, db=db
        )
    except ValueError as e:
        _handle_task_error(e)
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.post("/{task_id}/start", response_model=dict)
def start_task(
    task_id: str,
    body: StartTaskRequest,
    db: SQLSession = Depends(get_db_session),
):
    try:
        task = svc.start_task(
            task_id,
            body.agent_id,
            session_id=body.session_id,
            work_dir=body.work_dir,
            db=db,
        )
    except ValueError as e:
        _handle_task_error(e)
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.post("/{task_id}/complete", response_model=dict)
def complete_task(
    task_id: str,
    body: CompleteTaskRequest,
    db: SQLSession = Depends(get_db_session),
):
    try:
        task = svc.complete_task(
            task_id, body.agent_id, result_summary=body.result_summary, db=db
        )
    except ValueError as e:
        _handle_task_error(e)
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.post("/{task_id}/fail", response_model=dict)
def fail_task(
    task_id: str,
    body: FailTaskRequest,
    db: SQLSession = Depends(get_db_session),
):
    try:
        task = svc.fail_task(
            task_id,
            body.agent_id,
            error_message=body.error_message,
            failure_type=body.failure_type,
            db=db,
        )
    except ValueError as e:
        _handle_task_error(e)
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.post("/{task_id}/cancel", response_model=dict)
def cancel_task(
    task_id: str,
    db: SQLSession = Depends(get_db_session),
):
    try:
        task = svc.cancel_task(task_id, db=db)
    except ValueError as e:
        _handle_task_error(e)
    return {"success": True, "data": _task_to_response(task).model_dump()}


@router.get("/{task_id}/attempts", response_model=dict)
def get_attempts(
    task_id: str,
    db: SQLSession = Depends(get_db_session),
):
    task = _or_404(svc.get_task(task_id, db=db), f"Task {task_id} not found")
    attempts = svc.get_attempts(task_id, db=db)
    return {
        "success": True,
        "data": [_attempt_to_response(a).model_dump() for a in attempts],
    }


@router.get("/agent/{agent_id}/active-count", response_model=dict)
def get_active_count(
    agent_id: str,
    db: SQLSession = Depends(get_db_session),
):
    count = svc.get_agent_active_count(agent_id, db=db)
    return {"success": True, "data": {"agent_id": agent_id, "active_count": count}}


# ── Concurrency Slot Endpoints ─────────────────────────────────────────────────


class SetSlotLimitRequest(BaseModel):
    max_slots: int


@router.get("/agent/{agent_id}/slots", response_model=dict)
def get_slot_usage(
    agent_id: str,
    db: SQLSession = Depends(get_db_session),
):
    from common_lib.modules.agents.services.concurrency_service import (
        ConcurrencyService,
    )

    cs = ConcurrencyService()
    usage = cs.get_slot_usage(agent_id, db=db)
    return {"success": True, "data": usage}


@router.put("/agent/{agent_id}/slots", response_model=dict)
def set_slot_limit(
    agent_id: str,
    body: SetSlotLimitRequest,
    db: SQLSession = Depends(get_db_session),
):
    from common_lib.modules.agents.services.concurrency_service import (
        ConcurrencyService,
    )

    cs = ConcurrencyService()
    slot = cs.set_slot_limit(agent_id, body.max_slots, db=db)
    return {
        "success": True,
        "data": {
            "agent_id": slot.agent_id,
            "max_slots": slot.max_slots,
            "current_slots": slot.current_slots,
        },
    }


@router.post("/agent/{agent_id}/slots/acquire", response_model=dict)
def acquire_slot(
    agent_id: str,
    db: SQLSession = Depends(get_db_session),
):
    from common_lib.modules.agents.services.concurrency_service import (
        ConcurrencyService,
    )

    cs = ConcurrencyService()
    acquired = cs.acquire_slot(agent_id, db=db)
    if not acquired:
        raise HTTPException(
            status_code=409, detail=f"Concurrency budget exhausted for {agent_id}"
        )
    usage = cs.get_slot_usage(agent_id, db=db)
    return {"success": True, "data": usage}


@router.post("/agent/{agent_id}/slots/release", response_model=dict)
def release_slot(
    agent_id: str,
    db: SQLSession = Depends(get_db_session),
):
    from common_lib.modules.agents.services.concurrency_service import (
        ConcurrencyService,
    )

    cs = ConcurrencyService()
    released = cs.release_slot(agent_id, db=db)
    if not released:
        raise HTTPException(
            status_code=409, detail=f"No slots to release for {agent_id}"
        )
    usage = cs.get_slot_usage(agent_id, db=db)
    return {"success": True, "data": usage}


# ── Retry History Endpoint ─────────────────────────────────────────────────────


@router.get("/{task_id}/retry-history", response_model=dict)
def get_retry_history(
    task_id: str,
    db: SQLSession = Depends(get_db_session),
):
    task = _or_404(svc.get_task(task_id, db=db), f"Task {task_id} not found")
    from common_lib.modules.agents.services.retry_policy_service import (
        RetryPolicyService,
    )

    rps = RetryPolicyService()
    history = rps.get_retry_history(task_id, db=db)
    return {"success": True, "data": history}


@router.post("/{task_id}/classify-failure", response_model=dict)
def classify_failure(
    task_id: str,
    body: FailTaskRequest,
):
    from common_lib.modules.agents.services.retry_policy_service import (
        RetryPolicyService,
    )

    rps = RetryPolicyService()
    classification = rps.classify_failure(body.error_message, body.failure_type)
    should_retry = rps.should_retry(
        body.failure_type,
        attempt_count=1,
        max_attempts=3,
        error_message=body.error_message,
    )
    return {
        "success": True,
        "data": {
            "classification": classification,
            "should_retry": should_retry,
        },
    }
