"""RBAC Resource Ownership API routes — SSOT 09."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ownership", tags=["rbac-ownership"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class RegisterOwnershipReq(BaseModel):
    resource_type: str
    resource_id: str
    owner_user_id: Optional[int] = None
    owner_team_id: Optional[str] = None
    owner_org_id: Optional[str] = None

@router.post("/register")
def register(req: RegisterOwnershipReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        o = OwnershipService(session).register(req.resource_type, req.resource_id, req.owner_user_id, req.owner_team_id, req.owner_org_id)
        return {"id": o.id, "resource_type": o.resource_type, "resource_id": o.resource_id}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.get("/{rtype}/{rid}")
def get_ownership(rtype: str, rid: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        o = OwnershipService(session).get_owner(rtype, rid)
        if not o:
            raise HTTPException(404, "Ownership record not found")
        return {"resource_type": o.resource_type, "resource_id": o.resource_id, "owner_user_id": o.owner_user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/{rtype}/{rid}/transfer")
def transfer(rtype: str, rid: str, new_owner_user_id: Optional[int] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        o = OwnershipService(session).transfer(rtype, rid, new_owner_user_id=new_owner_user_id)
        if not o:
            raise HTTPException(404, "Ownership record not found")
        return {"success": True, "owner_user_id": o.owner_user_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.delete("/{rtype}/{rid}")
def delete_ownership(rtype: str, rid: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.ownership_service import OwnershipService
        OwnershipService(session).delete(rtype, rid)
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
