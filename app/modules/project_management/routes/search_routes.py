"""
PM Search — REST Routes.

Endpoints:
- GET /search/advanced — Advanced query search with structured query language
- GET /search/explain — Explain/parse a query without executing
- GET /search — Basic search (existing, via IssueService)
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port

    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["project_management", "search"])


@router.get("/advanced")
def advanced_search(
    _perm: None = require_permission("search.read", "*", "search"),
    project_id: str = Query(..., description="Project ID"),
    query: str = Query(
        ...,
        description="Advanced query string (e.g. 'priority:high status:in_progress assignee:john')",
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(_get_session),
):
    """Execute an advanced search query with structured parsing."""
    from common_lib.modules.project_management.search.service import (
        AdvancedQuerySearchService,
    )

    svc = AdvancedQuerySearchService(session=session)
    return svc.execute_query(
        project_id=project_id, query=query, limit=limit, offset=offset
    )


@router.get("/explain")
def explain_query(
    _perm: None = require_permission("search.read", "*", "search"),
    query: str = Query(..., description="Query string to explain"),
    session: Session = Depends(_get_session),
):
    """Parse and explain a query without executing it."""
    from common_lib.modules.project_management.search.service import (
        AdvancedQuerySearchService,
    )

    svc = AdvancedQuerySearchService(session=session)
    return svc.explain_query(query=query)


# ============================================================================
# Global Cross-Entity Search (SSOT 19.04, 19.08, 27.04)
# ============================================================================


@router.get("/global")
def global_search(
    _perm: None = require_permission("search.read", "*", "search"),
    query: str = Query(..., description="Free-text search query"),
    entity_types: Optional[str] = Query(
        None,
        description="Comma-separated entity types (issue,project,sprint,release,goal,comment)",
    ),
    project_ids: Optional[str] = Query(
        None, description="Comma-separated project IDs to scope search"
    ),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = Query(
        None, description="User ID for search history tracking"
    ),
    session: Session = Depends(_get_session),
):
    """Global cross-entity search across issues, projects, sprints, releases, goals, and comments.

    Returns grouped results by entity type with relevance ranking and facets.
    """
    from common_lib.modules.project_management.search import GlobalSearchService

    svc = GlobalSearchService(session=session)
    types_list = [t.strip() for t in entity_types.split(",")] if entity_types else None
    pids_list = [p.strip() for p in project_ids.split(",")] if project_ids else None
    return svc.global_search(
        query=query,
        entity_types=types_list,
        project_ids=pids_list,
        limit=limit,
        offset=offset,
        user_id=user_id,
    )


@router.get("/recent")
def get_recent_searches(
    _perm: None = require_permission("search.read", "*", "search"),
    user_id: str = Query(..., description="User ID"),
    limit: int = Query(10, ge=1, le=50),
):
    """Get recent search queries for a user."""
    from common_lib.modules.project_management.search import get_recent_searches as _get

    searches = _get(user_id=user_id, limit=limit)
    return {"searches": searches}


@router.delete("/recent")
def clear_recent_searches(
    _perm: None = require_permission("search.read", "*", "search"),
    user_id: str = Query(..., description="User ID"),
):
    """Clear all recent search history for a user."""
    from common_lib.modules.project_management.search import (
        clear_recent_searches as _clear,
    )

    return _clear(user_id=user_id)


@router.get("/analytics")
def get_search_analytics(
    _perm: None = require_permission("search.read", "*", "search"),
    user_id: Optional[str] = Query(
        None, description="Optional user ID to scope analytics"
    ),
):
    """Get search usage analytics — total searches, top queries."""
    from common_lib.modules.project_management.search import (
        get_search_analytics as _analytics,
    )

    return _analytics(user_id=user_id)
