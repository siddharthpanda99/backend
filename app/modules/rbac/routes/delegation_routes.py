"""RBAC Delegation API routes — SSOT 13."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/delegations", tags=["rbac-delegations"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CreateDelegationReq(BaseModel):
    delegator_user_id: int
    delegatee_user_id: int
    expires_at: str
    scope_type: str = "all"
    reason: Optional[str] = None

@router.post("")
def create_delegation(req: CreateDelegationReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        r = DelegationService(session).create_delegation(
            req.delegator_user_id, req.delegatee_user_id,
            datetime.fromisoformat(req.expires_at), req.scope_type, reason=req.reason)
        return {"delegation_id": r.delegation_id, "expires_at": r.expires_at.isoformat()}
    except ValueError as e: raise HTTPException(400, str(e))
    finally: session.close()

@router.get("/active/{user_id}")
def active_delegations(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        rs = DelegationService(session).get_active_delegations_for_user(user_id)
        return {"delegations": [{"id": r.delegation_id, "from": r.delegator_user_id, "expires": r.expires_at.isoformat()} for r in rs], "total": len(rs)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/{did}/revoke")
def revoke_delegation(did: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import DelegationService
        DelegationService(session).revoke_delegation(did)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/impersonations")
def start_impersonation(admin_user_id: int, target_user_id: int, reason: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        log = ImpersonationService(session).start_impersonation(admin_user_id, target_user_id, reason)
        return {"session_id": log.session_id}
    except ValueError as e: raise HTTPException(400, str(e))
    finally: session.close()

@router.post("/impersonations/end")
def end_impersonation(session_id: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.delegation.service import ImpersonationService
        ImpersonationService(session).end_impersonation(session_id)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally: session.close()
