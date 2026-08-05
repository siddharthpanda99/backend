"""RBAC Audit API routes — SSOT 19, 20, 21."""
from __future__ import annotations
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audit", tags=["rbac-audit"])

def _get_db_session():
    from sqlmodel import Session
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.post("/access-reviews")
def create_access_review(name: str, review_type: str = "role_assignment", scope_type: Optional[str] = None, scope_id: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        r = AccessReviewService(session).create_review(name=name, review_type=review_type, scope_type=scope_type, scope_id=scope_id)
        return {"id": r.id, "name": r.name, "status": r.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/access-reviews/decide")
def decide_review_item(item_id: str, decision: str, reason: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.access_reviews import AccessReviewService
        AccessReviewService(session).decide_item(item_id, decision, reason)
        return {"success": True}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/entitlement-requests")
def create_entitlement_request(requester_id: int, permission_name: Optional[str] = None, role_name: Optional[str] = None, reason: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        er = EntitlementRequestService(session).create_request(requester_id, permission_name=permission_name, role_name=role_name, reason=reason)
        return {"id": er.id, "status": er.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/entitlement-requests/{rid}/approve")
def approve_entitlement_request(rid: str, reviewer_id: int):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        er = EntitlementRequestService(session).approve_request(rid, reviewer_id)
        return {"id": er.id, "status": er.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()

@router.post("/entitlement-requests/{rid}/deny")
def deny_entitlement_request(rid: str, reviewer_id: int, reason: Optional[str] = None):
    session = _get_db_session()
    try:
        from common_lib.modules.rbac.audit.entitlement_requests import EntitlementRequestService
        er = EntitlementRequestService(session).deny_request(rid, reviewer_id, reason)
        return {"id": er.id, "status": er.status}
    except Exception as e: raise HTTPException(500, str(e))
    finally: session.close()
