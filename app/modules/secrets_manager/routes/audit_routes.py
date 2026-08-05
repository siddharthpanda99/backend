"""Secrets Manager Audit API routes — SSOT 14: Audit & Forensics.

Thin routing layer for audit log querying, filtering, export, and statistics.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["secrets-manager-audit"])


def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    action: str
    actor: str
    resource: str
    success: bool = True
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AuditQueryRequest(BaseModel):
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    actor: Optional[str] = None
    action: Optional[str] = None
    success: Optional[bool] = None
    limit: int = 100
    offset: int = 0


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/log")
def log_audit_entry(request: AuditLogEntry) -> Dict[str, Any]:
    """Log an audit entry for a secret access or management action."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.audit.service import AuditService

        svc = AuditService(session=session)
        entry = svc.log(
            action=request.action,
            actor=request.actor,
            resource=request.resource,
            success=request.success,
            target_type=request.target_type,
            target_id=request.target_id,
            ip_address=request.ip_address,
            user_agent=request.user_agent,
            metadata=request.metadata,
        )
        return {
            "id": entry.id,
            "action": entry.action,
            "actor": entry.actor,
            "resource": entry.resource,
            "success": entry.success,
            "created_at": entry.created_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/entries")
def query_audit_entries(
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query audit log entries with filters and pagination."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.audit.service import AuditService

        svc = AuditService(session=session)
        return svc.query(
            target_type=target_type,
            target_id=target_id,
            actor=actor,
            action=action,
            success=success,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/export")
def export_audit_log(
    target_type: Optional[str] = None,
    actor: Optional[str] = None,
    action: Optional[str] = None,
    success: Optional[bool] = None,
    limit: int = 10000,
) -> List[Dict[str, Any]]:
    """Export audit log entries for compliance."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.audit.service import AuditService

        svc = AuditService(session=session)
        return svc.export(
            target_type=target_type,
            actor=actor,
            action=action,
            success=success,
            limit=limit,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/stats")
def get_audit_stats() -> Dict[str, Any]:
    """Get aggregated audit statistics."""
    session = _get_db_session()
    try:
        from common_lib.modules.secrets_manager.audit.service import AuditService

        svc = AuditService(session=session)
        return svc.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
