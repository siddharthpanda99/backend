"""FastAPI routes for RBAC Guest Access — SSOT 23.11."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/guests", tags=["rbac-guests"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class GuestGrantRequest(BaseModel):
    user_id: int
    workspace_id: str
    granted_by: Optional[int] = None
    expires_in_days: int = 30


class GuestRevokeRequest(BaseModel):
    user_id: int
    revoked_by: Optional[int] = None
    reason: Optional[str] = None


@router.post("/grant")
async def grant_guest_access(request: GuestGrantRequest) -> Dict[str, Any]:
    """Grant guest-level access to a user in a workspace."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.guest_access_service import GuestAccessService
        svc = GuestAccessService(session)
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)
        result = svc.grant_guest_access(
            user_id=request.user_id,
            workspace_id=request.workspace_id,
            granted_by=request.granted_by,
            expires_at=expires_at,
        )
        return {
            "user_id": result.user_id,
            "role": "guest",
            "expires_at": result.expires_at.isoformat() if result.expires_at else "never",
            "message": "Guest access granted",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.post("/revoke")
async def revoke_guest_access(request: GuestRevokeRequest) -> Dict[str, Any]:
    """Revoke guest access for a user."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.guest_access_service import GuestAccessService
        svc = GuestAccessService(session)
        success = svc.revoke_guest_access(
            user_id=request.user_id,
            revoked_by=request.revoked_by,
            reason=request.reason,
        )
        return {"success": success, "message": "Guest access revoked" if success else "Not found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/{workspace_id}")
async def list_guest_users(workspace_id: str, include_expired: bool = False) -> Dict[str, Any]:
    """List all guest users in a workspace."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.guest_access_service import GuestAccessService
        svc = GuestAccessService(session)
        guests = svc.list_guest_users(workspace_id=workspace_id, include_expired=include_expired)
        return {"guests": guests, "count": len(guests)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/check/{user_id}")
async def check_guest_status(user_id: int) -> Dict[str, Any]:
    """Check if a user has guest status."""
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.guest_access_service import GuestAccessService
        svc = GuestAccessService(session)
        is_guest = svc.is_guest_user(user_id=user_id)
        return {"user_id": user_id, "is_guest": is_guest}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
