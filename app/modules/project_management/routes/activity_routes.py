"""
PM Activity Routes — Activity log for projects and issues.

RBAC permissions: activity.read
"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from app.modules.project_management.field_security_deps import filter_list_response

router = APIRouter(prefix="/activity", tags=["project_management", "activity"])


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


@router.get("")
def list_activity(
    request: Request,
    project_id: Optional[str] = Query(None),
    issue_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("activity.read", "*", "activity"),
):
    """List activity log entries with optional filters."""
    from common_lib.modules.project_management.activity.service import ActivityService
    svc = ActivityService(session)
    items = svc.list_activity(
        project_id=project_id, issue_id=issue_id,
        user_id=user_id, limit=limit, offset=offset,
    )
    return {"items": items, "total": len(items), "limit": limit, "offset": offset}
