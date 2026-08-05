"""RBAC Hardening API routes — SSOT 28."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/hardening", tags=["rbac-hardening"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class EscalationCheckReq(BaseModel):
    actor_user_id: int
    target_user_id: int
    role_ids: list[int]

@router.post("/check-escalation")
def check_escalation(req: EscalationCheckReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import PrivilegeEscalationGuard
        r = PrivilegeEscalationGuard(session).check_escalation(req.actor_user_id, req.target_user_id, req.role_ids)
        return {"allowed": r.allowed, "reason": r.reason, "severity": r.severity}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/threats")
def list_threats():
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.hardening.service import ThreatDetectionService
        threats = ThreatDetectionService(session).list_threats()
        return {"threats": threats, "total": len(threats)}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
