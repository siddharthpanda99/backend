"""Auth Sessions — FastAPI routes for session management.

Provides listing active sessions, revoking sessions, and cleanup.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.auth.dependencies import get_current_active_user
from common_lib.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/sessions", tags=["auth-sessions"])


class RevokeRequest(BaseModel):
    reason: Optional[str] = None


@router.get("")
def list_active_sessions(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    include_revoked: bool = Query(False),
):
    """List all sessions for the current user."""
    from common_lib.modules.auth.sessions.service import SessionManagementService
    svc = SessionManagementService(session)
    items = svc.list_sessions(str(current_user.id), include_revoked=include_revoked)
    return {"sessions": items, "total": len(items)}


@router.get("/active")
def list_active_only(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """List only active sessions for the current user."""
    from common_lib.modules.auth.sessions.service import SessionManagementService
    svc = SessionManagementService(session)
    items = svc.list_active_sessions(str(current_user.id))
    return {"sessions": items, "total": len(items)}


@router.post("/{session_id}/revoke")
def revoke_session(
    session_id: str,
    data: RevokeRequest = RevokeRequest(),
    current_user: User = Depends(get_current_active_user),
    db_session: Session = Depends(get_session),
):
    """Revoke a specific session."""
    from common_lib.modules.auth.sessions.service import SessionManagementService
    svc = SessionManagementService(db_session)
    ok = svc.revoke_session(session_id, reason=data.reason)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "message": "Session revoked"}


@router.post("/revoke-all")
def revoke_all_sessions(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    reason: str = Query(None),
):
    """Revoke all sessions for the current user (force logout from everywhere)."""
    from common_lib.modules.auth.sessions.service import SessionManagementService
    svc = SessionManagementService(session)
    count = svc.revoke_all_user_sessions(str(current_user.id), reason=reason)
    return {"revoked_count": count, "message": f"Revoked {count} sessions"}


@router.post("/cleanup-expired")
def cleanup_expired_sessions(
    session: Session = Depends(get_session),
):
    """Clean up expired sessions. Admin endpoint."""
    from common_lib.modules.auth.sessions.service import SessionManagementService
    svc = SessionManagementService(session)
    count = svc.cleanup_expired_sessions()
    return {"cleaned_count": count, "message": f"Cleaned {count} expired sessions"}
