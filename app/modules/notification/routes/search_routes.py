"""Notification Search — API routes.

REST endpoints for searching the notification search index across all
SSOT §29 query dimensions: keyword, full-text, metadata, recipient,
status, date range, template, provider, and audit.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["Notification — Search"])


# ── Request Schemas ─────────────────────────────────────────────────


class IndexNotificationRequest(BaseModel):
    notification_id: str
    event_id: str
    title: str
    notification_type: str
    status: str = "pending"
    keywords: str = ""
    recipient_id: str = ""


class SearchRequest(BaseModel):
    query: Optional[str] = None
    notification_type: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    recipient_id: Optional[str] = None
    recipient_email: Optional[str] = None
    template_id: Optional[str] = None
    template_name: Optional[str] = None
    provider: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    date_field: str = "created_at"
    sort_by: str = "created_at"
    sort_desc: bool = True
    limit: int = 50
    offset: int = 0


# ── Dependencies ────────────────────────────────────────────────────


def _get_session():
    from app.modules.project_management.deps import get_pm_session
    return get_pm_session()


def _get_search_svc(session=None):
    from common_lib.modules.notification.search.service import NotificationSearchService
    if session is None:
        session = _get_session()
    return NotificationSearchService(session=session)


# ── Indexing ────────────────────────────────────────────────────────


@router.post("/index")
async def index_notification(request: IndexNotificationRequest) -> Dict[str, Any]:
    """Index a notification document for search."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        return svc.index_notification(
            notification_id=request.notification_id,
            event_id=request.event_id,
            title=request.title,
            notification_type=request.notification_type,
            status=request.status,
            keywords=request.keywords or None,
            recipient_id=request.recipient_id or None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.delete("/index/{notification_id}")
async def delete_index(notification_id: str) -> Dict[str, Any]:
    """Remove a notification from the search index."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        deleted = svc.delete_index(notification_id=notification_id)
        return {"deleted": deleted, "notification_id": notification_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


# ── Search ──────────────────────────────────────────────────────────


@router.post("/query")
async def search_notifications(request: SearchRequest) -> Dict[str, Any]:
    """Multi-dimensional search across the notification index."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)

        # Parse dates if provided
        date_from = None
        date_to = None
        if request.date_from:
            date_from = datetime.fromisoformat(request.date_from)
        if request.date_to:
            date_to = datetime.fromisoformat(request.date_to)

        return svc.search(
            query=request.query,
            notification_type=request.notification_type,
            category=request.category,
            channel=request.channel,
            priority=request.priority,
            status=request.status,
            recipient_id=request.recipient_id,
            recipient_email=request.recipient_email,
            template_id=request.template_id,
            template_name=request.template_name,
            provider=request.provider,
            date_from=date_from,
            date_to=date_to,
            date_field=request.date_field,
            sort_by=request.sort_by,
            sort_desc=request.sort_desc,
            limit=request.limit,
            offset=request.offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/keyword")
async def search_keyword(q: str = Query(..., description="Search keyword"),
                          limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    """Quick keyword search across all indexed notification text fields."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        return svc.search_keyword(keyword=q, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/recipient/{recipient_id}")
async def search_recipient(recipient_id: str,
                            status: Optional[str] = Query(None),
                            limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    """Search notifications for a specific recipient."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        return svc.search_by_recipient(recipient_id=recipient_id, status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/type/{notification_type}")
async def search_type(notification_type: str,
                       status: Optional[str] = Query(None),
                       limit: int = Query(50, ge=1, le=500)) -> Dict[str, Any]:
    """Search notifications by type."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        return svc.search_by_type(notification_type=notification_type, status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/status/{status}")
async def search_status(status: str,
                         limit: int = Query(100, ge=1, le=1000)) -> Dict[str, Any]:
    """Search notifications by delivery status."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        return svc.search_by_status(status=status, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()


@router.get("/stats")
async def get_index_stats() -> Dict[str, Any]:
    """Get search index statistics."""
    session = _get_session()
    try:
        svc = _get_search_svc(session)
        return svc.get_index_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        session.close()
