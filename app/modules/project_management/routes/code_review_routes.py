"""
PM Module — Code Review Integration Routes (Domain 38)

REST API endpoints mounted in index.py.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from sqlmodel import Session

from app.modules.auth.dependencies.authz import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


router = APIRouter(prefix="/code_review", tags=["PM Code Review Integration"])


# ------------------------------------------------------------------ #
# PullRequest CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_prs(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("code_review.read", "*", "code_review"),
):
    """List PullRequest records."""
    from common_lib.modules.project_management.code_review.service import CodeReviewService

    svc = CodeReviewService(session)
    items = svc.list_prs(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_pr(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("code_review.create", "*", "code_review"),
):
    """Create a PullRequest record."""
    from common_lib.modules.project_management.code_review.service import CodeReviewService

    svc = CodeReviewService(session)
    row = svc.create_pr(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{pr_id}")
def get_pr(
    pr_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("code_review.read", "*", "code_review"),
):
    """Get a single PullRequest by id."""
    from common_lib.modules.project_management.code_review.service import CodeReviewService

    svc = CodeReviewService(session)
    row = svc.get_pr(pr_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{pr_id}")
def update_pr(
    pr_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("code_review.update", "*", "code_review"),
):
    """Update a PullRequest record (partial)."""
    from common_lib.modules.project_management.code_review.service import CodeReviewService

    svc = CodeReviewService(session)
    row = svc.update_pr(pr_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{pr_id}")
def delete_pr(
    pr_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("code_review.delete", "*", "code_review"),
):
    """Delete a PullRequest record."""
    from common_lib.modules.project_management.code_review.service import CodeReviewService

    svc = CodeReviewService(session)
    svc.delete_pr(pr_id)
    return {"ok": True}


@router.post("/{max_hours}/flag-stale-prs")
def flag_stale_prs(
    max_hours: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("code_review.update", "*", "code_review"),
):
    """Flag PRs awaiting review longer than max_hours."""
    from common_lib.modules.project_management.code_review.service import CodeReviewService

    svc = CodeReviewService(session)
    kwargs = dict(data or {})
    kwargs['max_hours'] = max_hours
    result = svc.flag_stale_prs(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
