"""Daemon routes — thin wrappers around daemon_service.

Endpoints:
    POST /register              — register daemon
    POST /{daemon_id}/heartbeat — heartbeat
    DELETE /{daemon_id}         — deregister
    GET  /                      — list daemons
    GET  /{daemon_id}/tasks     — poll for tasks
    POST /{daemon_id}/tasks/{task_id}/result — report result
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from common_lib.modules.agents.services.daemon_service import daemon_service

router = APIRouter()


class DaemonRegisterRequest(BaseModel):
    agent_id: str
    hostname: str
    available_clis: Optional[list[str]] = None
    capabilities: Optional[list[str]] = None


class DaemonResultRequest(BaseModel):
    status: str
    output: Optional[dict] = None
    error_message: Optional[str] = None


class DaemonResponse(BaseModel):
    success: bool
    data: dict | list
    message: str


def _daemon_to_dict(daemon) -> dict:
    return {
        "id": daemon.id,
        "agent_id": daemon.agent_id,
        "hostname": daemon.hostname,
        "available_clis": daemon.available_clis,
        "capabilities": daemon.capabilities,
        "status": daemon.status,
        "last_heartbeat": daemon.last_heartbeat.isoformat()
        if daemon.last_heartbeat
        else None,
        "registered_at": daemon.registered_at.isoformat()
        if daemon.registered_at
        else None,
    }


def _task_to_dict(task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "agent_id": task.agent_id,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "metadata_json": task.metadata_json,
        "last_failure_reason": task.last_failure_reason,
        "last_failure_type": task.last_failure_type,
        "retry_count": task.attempt_count,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.post("/register", response_model=DaemonResponse)
def register_daemon(
    req: DaemonRegisterRequest,
    session: Session = Depends(get_db_session),
):
    daemon = daemon_service.register_daemon(
        session=session,
        agent_id=req.agent_id,
        hostname=req.hostname,
        available_clis=req.available_clis,
        capabilities=req.capabilities,
    )
    return DaemonResponse(
        success=True,
        data=_daemon_to_dict(daemon),
        message="Daemon registered",
    )


@router.post("/{daemon_id}/heartbeat", response_model=DaemonResponse)
def heartbeat(daemon_id: str, session: Session = Depends(get_db_session)):
    daemon = daemon_service.heartbeat(session, daemon_id)
    if not daemon:
        raise HTTPException(status_code=404, detail="Daemon not found")
    return DaemonResponse(
        success=True,
        data=_daemon_to_dict(daemon),
        message="Heartbeat recorded",
    )


@router.delete("/{daemon_id}", response_model=DaemonResponse)
def deregister_daemon(daemon_id: str, session: Session = Depends(get_db_session)):
    daemon = daemon_service.deregister_daemon(session, daemon_id)
    if not daemon:
        raise HTTPException(status_code=404, detail="Daemon not found")
    return DaemonResponse(
        success=True,
        data=_daemon_to_dict(daemon),
        message="Daemon deregistered",
    )


@router.get("/", response_model=DaemonResponse)
def list_daemons(
    status: Optional[str] = None,
    session: Session = Depends(get_db_session),
):
    daemons = daemon_service.list_daemons(session, status=status)
    return DaemonResponse(
        success=True,
        data=[_daemon_to_dict(d) for d in daemons],
        message=f"Found {len(daemons)} daemons",
    )


@router.get("/{daemon_id}/tasks", response_model=DaemonResponse)
def poll_tasks(daemon_id: str, session: Session = Depends(get_db_session)):
    tasks = daemon_service.poll_tasks(session, daemon_id)
    return DaemonResponse(
        success=True,
        data=[_task_to_dict(t) for t in tasks],
        message=f"Found {len(tasks)} tasks",
    )


@router.post("/{daemon_id}/tasks/{task_id}/result", response_model=DaemonResponse)
def report_result(
    daemon_id: str,
    task_id: str,
    req: DaemonResultRequest,
    session: Session = Depends(get_db_session),
):
    task = daemon_service.report_result(
        session=session,
        daemon_id=daemon_id,
        task_id=task_id,
        status=req.status,
        output=req.output,
        error_message=req.error_message,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Daemon or task not found")
    return DaemonResponse(
        success=True,
        data=_task_to_dict(task),
        message="Result recorded",
    )
