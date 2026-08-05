"""
PM Backlog Routes — Thin API layer for backlog operations.

Registered at: /api/v1/jira/backlog/

RBAC permissions: backlog.read, backlog.update
"""
from __future__ import annotations

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session
from pydantic import BaseModel

from app.modules.auth.dependencies import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


from common_lib.modules.project_management import SprintService

logger = logging.getLogger(__name__)
router = APIRouter()


class ReorderRequest(BaseModel):
    project_id: str
    issue_ids: List[str]


@router.post("/reorder")
def reorder_backlog(
    data: ReorderRequest,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("backlog.update", "*", "backlog"),
):
    """Reorder the backlog using LexoRank.

    Provide an ordered list of issue IDs (first = highest priority).
    Uses the LexoRank algorithm to assign proper rank strings that
    allow future insertions between any two items.
    """
    svc = SprintService(session)
    try:
        success = svc.reorder_backlog(
            project_id=data.project_id,
            issue_ids=data.issue_ids,
        )
        if success:
            return {"success": True, "count": len(data.issue_ids)}
        raise HTTPException(status_code=400, detail="Failed to reorder backlog")
    except Exception as e:
        logger.exception("Failed to reorder backlog")
        raise HTTPException(status_code=500, detail=str(e))
