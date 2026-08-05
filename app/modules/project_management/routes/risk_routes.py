"""Risk, RAID, Change, Decision & Escalation REST Routes — Domain 09."""
import logging
from datetime import date
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management.schemas import (
    RiskCreate, RiskUpdate, ChangeRequestCreate, ChangeRequestUpdate,
    DecisionCreate, DecisionUpdate, RAIDLogCreate, EscalationCreate,
)
from common_lib.modules.project_management.risk.service import RiskService

logger = logging.getLogger(__name__)
router = APIRouter()


# --- Risks ---
@router.post("/risks", tags=["PM Risk"])
async def create_risk(data: RiskCreate, _perm: None = require_permission("risk.create", "*", "risk")):
    return RiskService.create_risk(data)


@router.get("/risks/{risk_id}", tags=["PM Risk"])
async def get_risk(risk_id: str, _perm: None = require_permission("risk.read", "*", "risk")):
    risk = RiskService.get_risk(risk_id)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    return risk


@router.get("/risks", tags=["PM Risk"])
async def list_risks(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("risk.read", "*", "risk"),
):
    return RiskService.list_risks(project_id=project_id, status=status, risk_level=risk_level, limit=limit, offset=offset)


@router.patch("/risks/{risk_id}", tags=["PM Risk"])
async def update_risk(risk_id: str, data: RiskUpdate, _perm: None = require_permission("risk.update", "*", "risk")):
    risk = RiskService.update_risk(risk_id, data)
    if not risk:
        raise HTTPException(status_code=404, detail="Risk not found")
    return risk


@router.delete("/risks/{risk_id}", tags=["PM Risk"])
async def delete_risk(risk_id: str, _perm: None = require_permission("risk.delete", "*", "risk")):
    if not RiskService.delete_risk(risk_id):
        raise HTTPException(status_code=404, detail="Risk not found")
    return {"ok": True}


# --- Risk Mitigations ---
@router.post("/risks/{risk_id}/mitigations", tags=["PM Risk"])
async def create_mitigation(
    risk_id: str,
    description: str = Query(...),
    action_type: str = Query("mitigate"),
    assignee: Optional[str] = None,
    due_date: Optional[str] = None,
    _perm: None = require_permission("risk.update", "*", "risk"),
):
    d = date.fromisoformat(due_date) if due_date else None
    mitigation = RiskService.create_mitigation(risk_id, description, action_type, assignee, d)
    if not mitigation:
        raise HTTPException(status_code=404, detail="Risk not found")
    return mitigation


@router.get("/risks/{risk_id}/mitigations", tags=["PM Risk"])
async def list_mitigations(risk_id: str, _perm: None = require_permission("risk.read", "*", "risk")):
    return RiskService.list_mitigations(risk_id)


# --- Risk Analytics ---
@router.get("/risks/analytics", tags=["PM Risk"])
async def get_risk_analytics(project_id: Optional[str] = None, _perm: None = require_permission("risk.read", "*", "risk")):
    return RiskService.get_risk_analytics(project_id)


# --- Change Requests ---
@router.post("/change-requests", tags=["PM Risk"])
async def create_change_request(data: ChangeRequestCreate, _perm: None = require_permission("risk.create", "*", "risk")):
    return RiskService.create_change_request(data)


@router.get("/change-requests", tags=["PM Risk"])
async def list_change_requests(
    project_id: str = Query(...),
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("risk.read", "*", "risk"),
):
    return RiskService.list_change_requests(project_id, status=status, limit=limit, offset=offset)


@router.patch("/change-requests/{cr_id}", tags=["PM Risk"])
async def update_change_request(cr_id: str, data: ChangeRequestUpdate, _perm: None = require_permission("risk.update", "*", "risk")):
    cr = RiskService.update_change_request(cr_id, data)
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")
    return cr


# --- Decisions ---
@router.post("/decisions", tags=["PM Risk"])
async def create_decision(data: DecisionCreate, _perm: None = require_permission("risk.create", "*", "risk")):
    return RiskService.create_decision(data)


@router.get("/decisions", tags=["PM Risk"])
async def list_decisions(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("risk.read", "*", "risk"),
):
    return RiskService.list_decisions(project_id=project_id, status=status, limit=limit, offset=offset)


@router.patch("/decisions/{dec_id}", tags=["PM Risk"])
async def update_decision(dec_id: str, data: DecisionUpdate, _perm: None = require_permission("risk.update", "*", "risk")):
    dec = RiskService.update_decision(dec_id, data)
    if not dec:
        raise HTTPException(status_code=404, detail="Decision not found")
    return dec


# --- RAID Logs ---
@router.post("/raid-logs", tags=["PM Risk"])
async def create_raid_entry(data: RAIDLogCreate, _perm: None = require_permission("risk.create", "*", "risk")):
    return RiskService.create_raid_entry(data)


@router.get("/raid-logs", tags=["PM Risk"])
async def list_raid_logs(
    project_id: str = Query(...),
    entry_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("risk.read", "*", "risk"),
):
    return RiskService.list_raid_logs(project_id, entry_type=entry_type, status=status, limit=limit, offset=offset)


@router.get("/raid-logs/summary", tags=["PM Risk"])
async def get_raid_summary(project_id: str = Query(...), _perm: None = require_permission("risk.read", "*", "risk")):
    return RiskService.get_raid_summary(project_id)


# --- Escalations ---
@router.post("/escalations", tags=["PM Risk"])
async def create_escalation(data: EscalationCreate, _perm: None = require_permission("risk.create", "*", "risk")):
    return RiskService.create_escalation(data)


@router.get("/escalations", tags=["PM Risk"])
async def list_escalations(
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("risk.read", "*", "risk"),
):
    return RiskService.list_escalations(project_id=project_id, status=status, limit=limit, offset=offset)


@router.post("/escalations/{esc_id}/resolve", tags=["PM Risk"])
async def resolve_escalation(esc_id: str, resolution: str = Query(...), _perm: None = require_permission("risk.update", "*", "risk")):
    esc = RiskService.resolve_escalation(esc_id, resolution)
    if not esc:
        raise HTTPException(status_code=404, detail="Escalation not found")
    return esc
