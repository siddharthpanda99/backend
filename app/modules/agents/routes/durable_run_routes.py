"""Durable run routes — thin wrappers around DurableRunService (NEX-P5-002).

G1: no business logic here; every handler resolves the service from
``common_lib`` and serialises. G9: while ``agents.durable_runs.enabled``
is OFF every endpoint answers 404 so flag-off deployments see no new
surface (mirrors the capabilities batch route pattern).

Mounted under the agents router at ``/runs``; with the global ``/api/v1``
prefix this serves ``POST /api/v1/agents/runs`` — the item's
``POST /v1/agent-runs`` idempotent-start contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session as SQLSession

from common_lib.modules.agents.durable_runs.flags import DURABLE_RUNS_FLAG, is_enabled
from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)

router = APIRouter()


def _require_enabled() -> None:
    if not is_enabled(DURABLE_RUNS_FLAG):
        raise HTTPException(status_code=404, detail="Durable runs are disabled")


def _svc():
    from common_lib.modules.agents.durable_runs.service import DurableRunService

    return DurableRunService()


def _run_to_dict(run) -> dict:
    return {
        "id": run.id,
        "dedupe_key": run.dedupe_key,
        "agent_id": run.agent_id,
        "status": run.status,
        "input": run.input_json or {},
        "skill_ref": run.skill_ref,
        "current_step": run.current_step,
        "attempt_count": run.attempt_count,
        "max_attempts": run.max_attempts,
        "last_error": run.last_error,
        "deadline_at": run.deadline_at.isoformat() if run.deadline_at else None,
        "run_after": run.run_after.isoformat() if run.run_after else None,
        "next_retry_at": run.next_retry_at.isoformat() if run.next_retry_at else None,
        "metadata": run.metadata_json or {},
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "updated_at": run.updated_at.isoformat() if run.updated_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def _handle_run_error(e: ValueError):
    msg = str(e)
    if "not found" in msg.lower():
        raise HTTPException(status_code=404, detail=msg)
    raise HTTPException(status_code=409, detail=msg)


# ── Schemas ──────────────────────────────────────────────────────────────────


class CreateRunRequest(BaseModel):
    agent_id: str = Field(default="")
    dedupe_key: Optional[str] = Field(default=None)
    input: dict[str, Any] = Field(default_factory=dict)
    skill_ref: Optional[str] = Field(default=None)
    max_attempts: int = Field(default=3, ge=1, le=10)
    deadline_at: Optional[datetime] = Field(default=None)
    run_after: Optional[datetime] = Field(default=None)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransitionRequest(BaseModel):
    to_status: str


class CheckpointRequest(BaseModel):
    step_number: int = Field(ge=0)
    step_name: str = Field(default="")
    state: dict[str, Any] = Field(default_factory=dict)


class FailStepRequest(BaseModel):
    error: str = Field(default="")
    retryable: bool = Field(default=False)


class TaskRequest(BaseModel):
    title: str
    max_attempts: int = Field(default=3, ge=1, le=10)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExternalOpRequest(BaseModel):
    op_key: str
    op_kind: str = Field(default="")


class ArtifactRequest(BaseModel):
    kind: str = Field(default="file")
    name: str = Field(default="")
    uri: str = Field(default="")
    content_hash: Optional[str] = Field(default=None)
    size_bytes: int = Field(default=0, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/", response_model=dict)
def create_run(body: CreateRunRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        run = _svc().create_run(
            body.agent_id,
            dedupe_key=body.dedupe_key,
            input=body.input,
            skill_ref=body.skill_ref,
            max_attempts=body.max_attempts,
            deadline_at=body.deadline_at,
            run_after=body.run_after,
            metadata=body.metadata,
            db=db,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"success": True, "data": _run_to_dict(run)}


@router.get("/", response_model=dict)
def list_runs(
    status: Optional[str] = None,
    agent_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: SQLSession = Depends(get_db_session),
):
    _require_enabled()
    runs = _svc().list_runs(status=status, agent_id=agent_id, limit=limit, offset=offset, db=db)
    return {"success": True, "data": [_run_to_dict(r) for r in runs]}


@router.get("/{run_id}", response_model=dict)
def get_run(run_id: str, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    run = _svc().get_run(run_id, db=db)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"success": True, "data": _run_to_dict(run)}


@router.post("/{run_id}/transition", response_model=dict)
def transition_run(run_id: str, body: TransitionRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        run = _svc().transition(run_id, body.to_status, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": _run_to_dict(run)}


@router.post("/{run_id}/checkpoints", response_model=dict)
def save_checkpoint(run_id: str, body: CheckpointRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        ckpt = _svc().save_checkpoint(run_id, body.step_number, body.step_name, body.state, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {
        "success": True,
        "data": {
            "id": ckpt.id,
            "run_id": ckpt.run_id,
            "step_number": ckpt.step_number,
            "step_name": ckpt.step_name,
            "state": ckpt.state_json,
            "completed_op_keys": ckpt.completed_op_keys,
        },
    }


@router.get("/{run_id}/checkpoints", response_model=dict)
def list_checkpoints(run_id: str, limit: int = 20, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    ckpts = _svc().list_checkpoints(run_id, limit=limit, db=db)
    return {
        "success": True,
        "data": [
            {
                "id": c.id,
                "run_id": c.run_id,
                "step_number": c.step_number,
                "step_name": c.step_name,
                "completed_op_keys": c.completed_op_keys,
            }
            for c in ckpts
        ],
    }


@router.post("/{run_id}/resume", response_model=dict)
def resume_run(run_id: str, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        envelope = _svc().resume_from_checkpoint(run_id, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": envelope}


@router.post("/{run_id}/cancel", response_model=dict)
def cancel_run(run_id: str, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        out = _svc().cancel_run(run_id, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": out}


@router.post("/{run_id}/fail-step", response_model=dict)
def fail_step(run_id: str, body: FailStepRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        out = _svc().fail_step(run_id, body.error, retryable=body.retryable, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": out}


@router.post("/{run_id}/tasks", response_model=dict)
def add_task(run_id: str, body: TaskRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        task = _svc().add_task(run_id, body.title, max_attempts=body.max_attempts, metadata=body.metadata, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": {"id": task.id, "run_id": task.run_id, "title": task.title, "status": task.status}}


@router.get("/{run_id}/tasks", response_model=dict)
def list_run_tasks(run_id: str, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    tasks = _svc().list_tasks(run_id, db=db)
    return {
        "success": True,
        "data": [{"id": t.id, "title": t.title, "status": t.status, "resume_step": t.resume_step} for t in tasks],
    }


@router.post("/{run_id}/external-ops", response_model=dict)
def record_external_op(run_id: str, body: ExternalOpRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        op = _svc().record_external_op(run_id, body.op_key, body.op_kind, db=db)
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": {"id": op.id, "op_key": op.op_key, "status": op.status}}


@router.post("/{run_id}/artifacts", response_model=dict)
def record_artifact(run_id: str, body: ArtifactRequest, db: SQLSession = Depends(get_db_session)):
    _require_enabled()
    try:
        art = _svc().record_artifact(
            run_id, kind=body.kind, name=body.name, uri=body.uri,
            content_hash=body.content_hash, size_bytes=body.size_bytes,
            metadata=body.metadata, db=db,
        )
    except ValueError as e:
        _handle_run_error(e)
    return {"success": True, "data": {"id": art.id, "kind": art.kind, "name": art.name, "uri": art.uri}}
