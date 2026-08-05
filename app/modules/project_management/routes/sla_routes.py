"""PM SLA Management — FastAPI routes (Module 13)."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from app.modules.project_management.deps import get_pm_session

from common_lib.modules.project_management.sla.service import SLAService

router = APIRouter()


@router.get("/sla/configs", summary="List SLA configurations")
def list_sla_configs(
    project_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    session: Session = Depends(get_pm_session),
):
    svc = SLAService(session)
    return svc.list_configs(project_id=project_id, workspace_id=workspace_id)


@router.post("/sla/configs", summary="Create SLA configuration")
def create_sla_config(
    body: dict,
    session: Session = Depends(get_pm_session),
):
    svc = SLAService(session)
    return svc.create_config(**body)


@router.get("/sla/configs/{config_id}", summary="Get SLA config")
def get_sla_config(config_id: str, session: Session = Depends(get_pm_session)):
    svc = SLAService(session)
    result = svc.get_config(config_id)
    if not result:
        raise HTTPException(status_code=404, detail="SLA config not found")
    return result


@router.put("/sla/configs/{config_id}", summary="Update SLA config")
def update_sla_config(config_id: str, body: dict, session: Session = Depends(get_pm_session)):
    svc = SLAService(session)
    result = svc.update_config(config_id, body)
    if not result:
        raise HTTPException(status_code=404, detail="SLA config not found")
    return result


@router.delete("/sla/configs/{config_id}", summary="Delete SLA config")
def delete_sla_config(config_id: str, session: Session = Depends(get_pm_session)):
    svc = SLAService(session)
    if not svc.delete_config(config_id):
        raise HTTPException(status_code=404, detail="SLA config not found")
    return {"ok": True}


@router.get("/sla/violations", summary="List SLA violations")
def list_sla_violations(
    issue_id: Optional[str] = None,
    unresolved_only: bool = False,
    session: Session = Depends(get_pm_session),
):
    svc = SLAService(session)
    return svc.list_violations(issue_id=issue_id, unresolved_only=unresolved_only)


@router.post("/sla/check-breach", summary="Check and record SLA breach")
def check_sla_breach(body: dict, session: Session = Depends(get_pm_session)):
    svc = SLAService(session)
    return svc.check_and_record_breach(**body)


@router.get("/sla/report", summary="SLA compliance report")
def sla_compliance_report(
    project_id: Optional[str] = None,
    days: int = 30,
    session: Session = Depends(get_pm_session),
):
    svc = SLAService(session)
    return svc.get_compliance_report(project_id=project_id, days=days)


@router.get("/sla/issue/{issue_id}/status", summary="Issue SLA status")
def issue_sla_status(issue_id: str, session: Session = Depends(get_pm_session)):
    svc = SLAService(session)
    return svc.get_issue_sla_status(issue_id=issue_id)
