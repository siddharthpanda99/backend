"""RBAC Permission Check API routes — SSOT 17, 18, 26."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/permissions", tags=["rbac-permissions"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CheckReq(BaseModel):
    user_id: int
    resource: str
    action: str
    resource_id: Optional[str] = None
    org_id: Optional[str] = None

class CheckManyReq(BaseModel):
    user_id: int; checks: List[dict]

@router.post("/check")
def check(req: CheckReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        return PermissionCheckService(session).check(user_id=req.user_id, resource=req.resource, action=req.action, resource_id=req.resource_id, org_id=req.org_id)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/check-many")
def check_many(req: CheckManyReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        results = PermissionCheckService(session).check_many(user_id=req.user_id, checks=req.checks)
        return {"results": results, "total": len(results)}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/simulate")
def simulate(user_id: int, resource: str, action: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        return PermissionCheckService(session).simulate(user_id=user_id, resource=resource, action=action)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/explain")
def explain(user_id: int, resource: str, action: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        return PermissionCheckService(session).explain(user_id=user_id, resource=resource, action=action)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/matrix")
def matrix(role_ids: Optional[str] = None, resource_filter: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.api.service import PermissionCheckService
        rids = [int(x) for x in role_ids.split(",")] if role_ids else None
        return PermissionCheckService(session).get_permission_matrix(role_ids=rids, resource_filter=resource_filter)
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
