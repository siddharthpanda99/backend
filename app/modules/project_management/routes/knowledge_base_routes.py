"""
PM Module — Knowledge Base (Public) Routes (Domain 44)

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


router = APIRouter(prefix="/knowledge_base", tags=["PM Knowledge Base (Public)"])


# ------------------------------------------------------------------ #
# KbCategory CRUD
# ------------------------------------------------------------------ #

@router.get("")
def list_categorys(
    limit: int = Query(50),
    offset: int = Query(0),
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.read", "*", "knowledge_base"),
):
    """List KbCategory records."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    items = svc.list_categorys(limit=limit, offset=offset)
    items = [i.model_dump() for i in items] if items and hasattr(items[0], 'model_dump') else items
    total = len(items)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("")
def create_category(
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.create", "*", "knowledge_base"),
):
    """Create a KbCategory record."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    row = svc.create_category(data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.get("/{category_id}")
def get_category(
    category_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.read", "*", "knowledge_base"),
):
    """Get a single KbCategory by id."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    row = svc.get_category(category_id)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.patch("/{category_id}")
def update_category(
    category_id: str,
    data: dict,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.update", "*", "knowledge_base"),
):
    """Update a KbCategory record (partial)."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    row = svc.update_category(category_id, data=data)
    return row.model_dump() if hasattr(row, 'model_dump') else row


@router.delete("/{category_id}")
def delete_category(
    category_id: str,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.delete", "*", "knowledge_base"),
):
    """Delete a KbCategory record."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    svc.delete_category(category_id)
    return {"ok": True}


@router.post("/{article_id}/publish-article")
def publish_article(
    article_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.update", "*", "knowledge_base"),
):
    """Publish a draft article."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    kwargs = dict(data or {})
    kwargs['article_id'] = article_id
    result = svc.publish_article(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{space_id}/search-articles")
def search_articles(
    space_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.update", "*", "knowledge_base"),
):
    """Search published KB articles by keyword."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    kwargs = dict(data or {})
    kwargs['space_id'] = space_id
    result = svc.search_articles(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result


@router.post("/{space_id}/get-feedback-report")
def get_feedback_report(
    space_id: str,
    data: dict = None,
    session: Session = Depends(_get_session),
    _perm: None = require_permission("knowledge_base.update", "*", "knowledge_base"),
):
    """Feedback summary per article for a space."""
    from common_lib.modules.project_management.knowledge_base.service import KnowledgeBaseService

    svc = KnowledgeBaseService(session)
    kwargs = dict(data or {})
    kwargs['space_id'] = space_id
    result = svc.get_feedback_report(**kwargs)
    if hasattr(result, 'model_dump'):
        return result.model_dump()
    if isinstance(result, list) and result and hasattr(result[0], 'model_dump'):
        return [r.model_dump() for r in result]
    return result
