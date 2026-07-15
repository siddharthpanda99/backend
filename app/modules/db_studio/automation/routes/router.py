"""Thin FastAPI router for Scheduler, Jobs & Automation (UDS Module 22)."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.automation import (
    AutomationService,
    ScheduledJobCreate, ScheduledJobUpdate, ScheduledJobOut,
    JobRunOut,
    WorkflowDefinitionCreate, WorkflowDefinitionUpdate, WorkflowDefinitionOut,
    WorkflowRunCreate, WorkflowRunOut,
    TriggerCreate, TriggerUpdate, TriggerOut,
    QueueCreate, QueueOut,
    RetryHistoryOut, AutomationNotificationOut,
    AutomationDashboardOut,
)

router = APIRouter(prefix="/api/v1/automation", tags=["Scheduler, Jobs & Automation"])
svc = AutomationService()


# ── Jobs ───────────────────────────────────────────────────────────────

@router.post("/jobs", response_model=ScheduledJobOut)
def create_job(req: ScheduledJobCreate):
    return svc.create_job(req)


@router.get("/jobs", response_model=List[ScheduledJobOut])
def list_jobs(
    job_type: Optional[str] = None,
    is_paused: Optional[bool] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_jobs(job_type, is_paused, workspace_id, limit)


@router.get("/jobs/{job_id}", response_model=ScheduledJobOut)
def get_job(job_id: str):
    j = svc.get_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@router.put("/jobs/{job_id}", response_model=ScheduledJobOut)
def update_job(job_id: str, req: ScheduledJobUpdate):
    j = svc.update_job(job_id, req)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    if not svc.delete_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"ok": True}


@router.post("/jobs/{job_id}/pause", response_model=ScheduledJobOut)
def pause_job(job_id: str):
    j = svc.pause_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@router.post("/jobs/{job_id}/resume", response_model=ScheduledJobOut)
def resume_job(job_id: str):
    j = svc.resume_job(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    return j


@router.post("/jobs/{job_id}/run", response_model=JobRunOut)
def run_job(job_id: str, trigger_type: str = "manual", triggered_by: Optional[str] = None):
    return svc.run_job(job_id, trigger_type, triggered_by)


@router.get("/runs", response_model=List[JobRunOut])
def list_runs(job_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    return svc.list_job_runs(job_id, status, limit)


# ── Workflows ──────────────────────────────────────────────────────────

@router.post("/workflows", response_model=WorkflowDefinitionOut)
def create_workflow(req: WorkflowDefinitionCreate):
    return svc.create_workflow(req)


@router.get("/workflows", response_model=List[WorkflowDefinitionOut])
def list_workflows(workspace_id: Optional[str] = None, limit: int = 50):
    return svc.list_workflows(workspace_id, limit)


@router.get("/workflows/{workflow_id}", response_model=WorkflowDefinitionOut)
def get_workflow(workflow_id: str):
    w = svc.get_workflow(workflow_id)
    if not w:
        raise HTTPException(404, "Workflow not found")
    return w


@router.put("/workflows/{workflow_id}", response_model=WorkflowDefinitionOut)
def update_workflow(workflow_id: str, req: WorkflowDefinitionUpdate):
    w = svc.update_workflow(workflow_id, req)
    if not w:
        raise HTTPException(404, "Workflow not found")
    return w


@router.delete("/workflows/{workflow_id}")
def delete_workflow(workflow_id: str):
    if not svc.delete_workflow(workflow_id):
        raise HTTPException(404, "Workflow not found")
    return {"ok": True}


@router.post("/workflows/{workflow_id}/run", response_model=WorkflowRunOut)
def run_workflow(workflow_id: str, req: Optional[WorkflowRunCreate] = None):
    return svc.run_workflow(workflow_id, req or WorkflowRunCreate())


@router.get("/workflow-runs", response_model=List[WorkflowRunOut])
def list_workflow_runs(
    workflow_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_workflow_runs(workflow_id, status, limit)


# ── Triggers ───────────────────────────────────────────────────────────

@router.post("/triggers", response_model=TriggerOut)
def create_trigger(req: TriggerCreate):
    return svc.create_trigger(req)


@router.get("/triggers", response_model=List[TriggerOut])
def list_triggers(
    trigger_type: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_triggers(trigger_type, workspace_id, limit)


@router.put("/triggers/{trigger_id}", response_model=TriggerOut)
def update_trigger(trigger_id: str, req: TriggerUpdate):
    t = svc.update_trigger(trigger_id, req)
    if not t:
        raise HTTPException(404, "Trigger not found")
    return t


@router.delete("/triggers/{trigger_id}")
def delete_trigger(trigger_id: str):
    if not svc.delete_trigger(trigger_id):
        raise HTTPException(404, "Trigger not found")
    return {"ok": True}


# ── Queues ─────────────────────────────────────────────────────────────

@router.post("/queues", response_model=QueueOut)
def create_queue(req: QueueCreate):
    return svc.create_queue(req)


@router.get("/queues", response_model=List[QueueOut])
def list_queues(workspace_id: Optional[str] = None, limit: int = 50):
    return svc.list_queues(workspace_id, limit)


# ── Retries / Notifications ────────────────────────────────────────────

@router.get("/retries", response_model=List[RetryHistoryOut])
def list_retries(job_id: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    return svc.list_retries(job_id, status, limit)


@router.get("/notifications", response_model=List[AutomationNotificationOut])
def list_notifications(
    notification_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_notifications(notification_type, status, limit)


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=AutomationDashboardOut)
def automation_dashboard():
    return svc.get_dashboard()
