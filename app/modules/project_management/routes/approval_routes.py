"""PM Approvals — FastAPI routes (FC §1.17)."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.modules.project_management.deps import get_pm_session

from common_lib.modules.project_management.approvals.service import ApprovalService

router = APIRouter()


@router.get("/approvals/workflows", summary="List approval workflows")
def list_workflows(project_id: Optional[str] = None, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    return svc.list_workflows(project_id=project_id)


@router.post("/approvals/workflows", summary="Create approval workflow")
def create_workflow(body: dict, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    return svc.create_workflow(**body)


@router.get("/approvals/workflows/{workflow_id}", summary="Get approval workflow")
def get_workflow(workflow_id: str, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    result = svc.get_workflow(workflow_id)
    if not result:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return result


@router.delete("/approvals/workflows/{workflow_id}", summary="Delete approval workflow")
def delete_workflow(workflow_id: str, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    if not svc.delete_workflow(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"ok": True}


@router.post("/approvals/requests", summary="Create approval request")
def create_request(body: dict, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    return svc.create_request(**body)


@router.get("/approvals/requests", summary="List approval requests")
def list_requests(
    issue_id: Optional[str] = None,
    status: Optional[str] = None,
    session: Session = Depends(get_pm_session),
):
    svc = ApprovalService(session)
    return svc.list_requests(issue_id=issue_id, status=status)


@router.get("/approvals/requests/{request_id}", summary="Get approval request")
def get_request(request_id: str, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    result = svc.get_request(request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found")
    return result


@router.post("/approvals/steps/{step_id}/approve", summary="Approve step")
def approve_step(step_id: str, body: dict, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    result = svc.approve_step(step_id, **body)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot approve this step")
    return result


@router.post("/approvals/steps/{step_id}/reject", summary="Reject step")
def reject_step(step_id: str, body: dict, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    result = svc.reject_step(step_id, **body)
    if not result:
        raise HTTPException(status_code=400, detail="Cannot reject this step")
    return result


@router.get("/approvals/requests/{request_id}/history", summary="Get approval history")
def get_history(request_id: str, session: Session = Depends(get_pm_session)):
    svc = ApprovalService(session)
    return svc.get_history(request_id=request_id)
