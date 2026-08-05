"""RBAC Session/MFA API routes — SSOT 11 & 12."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["rbac-sessions"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


class CreateSessionReq(BaseModel):
    user_id: int
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_info: Optional[dict] = None
    expires_in_hours: int = 24

@router.post("")
def create_session(req: CreateSessionReq):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        s, tok = SessionService(session).create_session(
            user_id=req.user_id, ip_address=req.ip_address, user_agent=req.user_agent,
            device_info=req.device_info, expires_in_hours=req.expires_in_hours)
        return {"session_id": s.id, "token": tok, "expires_at": s.expires_at.isoformat()}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/validate")
def validate_session(token: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        s = SessionService(session).validate_session(token)
        if not s: raise HTTPException(401, "Invalid session")
        return {"valid": True, "user_id": s.user_id, "session_id": s.id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/{sid}/revoke")
def revoke_session(sid: int, reason: str = "user_request"):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import SessionService
        SessionService(session).revoke_session(sid, reason)
        return {"success": True}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/mfa/setup")
def mfa_setup(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        secret, uri = MFAService(session).setup_totp(user_id)
        return {"secret": secret, "uri": uri}
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.post("/mfa/verify")
def mfa_verify(user_id: int, code: str):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        ok = MFAService(session).verify_totp(user_id, code)
        return {"verified": ok}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()

@router.get("/mfa/status/{user_id}")
def mfa_status(user_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.session_mfa_service import MFAService
        return {"user_id": user_id, "enabled": MFAService(session).is_enabled(user_id)}
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        session.close()


# ===========================================================================
# Break Glass Emergency Access — SSOT 12
# ===========================================================================

@router.post("/break-glass/grant")
def break_glass_grant(user_id: int, role_name: str, reason: str, ticket_ref: Optional[str] = None, duration_minutes: int = 30):
    """Grant emergency break glass access to a user."""
    try:
        from common_lib.modules.rbac.sessions.break_glass import BreakGlassService
        result = BreakGlassService().grant_access(
            user_id=user_id, role_name=role_name, reason=reason,
            ticket_ref=ticket_ref, duration_minutes=duration_minutes,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

@router.post("/break-glass/{session_id}/revoke")
def break_glass_revoke(session_id: str, revoke_reason: str = "Manual revocation"):
    """Revoke a break glass session."""
    try:
        from common_lib.modules.rbac.sessions.break_glass import BreakGlassService
        ok = BreakGlassService().revoke_access(session_id, revoke_reason)
        if not ok:
            raise HTTPException(404, "Break glass session not found or already revoked")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/break-glass/active")
def break_glass_list_active(user_id: Optional[int] = None):
    """List active break glass sessions."""
    try:
        from common_lib.modules.rbac.sessions.break_glass import BreakGlassService
        sessions = BreakGlassService().list_active_sessions(user_id=user_id)
        return {"sessions": sessions, "total": len(sessions)}
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/break-glass/{session_id}")
def break_glass_get_session(session_id: str):
    """Get details of a specific break glass session."""
    try:
        from common_lib.modules.rbac.sessions.break_glass import BreakGlassService
        s = BreakGlassService().get_active_session(session_id)
        if not s:
            raise HTTPException(404, "Break glass session not found")
        return s
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))

@router.get("/break-glass/audit")
def break_glass_audit_log(limit: int = 50, user_id: Optional[int] = None):
    """Get break glass audit trail."""
    try:
        from common_lib.modules.rbac.sessions.break_glass import BreakGlassService
        log = BreakGlassService().get_audit_log(limit=limit, user_id=user_id)
        return {"entries": log, "total": len(log)}
    except Exception as e:
        raise HTTPException(500, str(e))
