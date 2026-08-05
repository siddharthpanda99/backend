"""
PM Burndown Chart Route — Thin API layer.

Registered at: /api/v1/jira/sprints/{sprint_id}/burndown
"""
from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission
from common_lib.modules.project_management import SprintService


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{sprint_id}/burndown")
def get_burndown_data(
    sprint_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("sprint.read", "*", "sprint"),
):
    """Get burndown chart data for a sprint.

    Returns ideal burndown (linear descent), actual burndown (from
    completed_at timestamps), daily completion breakdown, and metadata.
    """
    svc = SprintService(session)
    data = svc.get_burndown_data(sprint_id)
    if not data:
        raise HTTPException(status_code=404, detail="Sprint not found")
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"])
    return data
