"""REST API routes for Universal Query Workbench (UDS Module 02).

Prefix: /api/v1/query-workbench
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from common_lib.modules.db_studio.query_workbench import (
    QueryWorkbenchService,
    QueryExecuteRequest,
    QueryExecuteResponse,
    ExplainRequest,
    ExplainResponse,
    BatchExecuteRequest,
    BatchExecuteResponse,
    SavedQueryCreate,
    SavedQueryUpdate,
    SavedQueryOut,
    SavedQueryListResponse,
    SnippetCreate,
    SnippetUpdate,
    SnippetOut,
    SnippetListResponse,
    QueryTemplateCreate,
    QueryTemplateUpdate,
    QueryTemplateOut,
    QueryTemplateListResponse,
    QueryHistoryEntryOut,
    QueryHistoryListResponse,
    ExecutionLogOut,
    ConnectionBrief,
)

logger = logging.getLogger(__name__)

router = APIRouter()
svc = QueryWorkbenchService()


# ═══════════════════════════════════════════════════════════════════════════
# Query Execution
# ═══════════════════════════════════════════════════════════════════════════

@router.post("/execute", response_model=QueryExecuteResponse)
def execute_query(req: QueryExecuteRequest):
    """Execute a SQL query against a connected database."""
    return svc.execute_query(req)


@router.post("/explain", response_model=ExplainResponse)
def explain_query(req: ExplainRequest):
    """Run EXPLAIN or EXPLAIN ANALYZE on a query."""
    return svc.explain_query(req)


@router.post("/batch", response_model=BatchExecuteResponse)
def batch_execute(req: BatchExecuteRequest):
    """Execute multiple statements sequentially."""
    return svc.batch_execute(req)


# ═══════════════════════════════════════════════════════════════════════════
# Saved Queries
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/saved-queries", response_model=SavedQueryListResponse)
def list_saved_queries(
    search: Optional[str] = Query(None),
    folder: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    database_type: Optional[str] = Query(None),
    favorites_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    tag_list = tags.split(",") if tags else None
    return svc.list_saved_queries(
        search=search, folder=folder, tags=tag_list,
        database_type=database_type, favorites_only=favorites_only,
        offset=offset, limit=limit,
    )


@router.get("/saved-queries/{query_id}", response_model=SavedQueryOut)
def get_saved_query(query_id: str):
    result = svc.get_saved_query(query_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Saved query '{query_id}' not found")
    return result


@router.post("/saved-queries", status_code=201, response_model=SavedQueryOut)
def create_saved_query(req: SavedQueryCreate):
    return svc.create_saved_query(req)


@router.put("/saved-queries/{query_id}", response_model=SavedQueryOut)
def update_saved_query(query_id: str, req: SavedQueryUpdate):
    result = svc.update_saved_query(query_id, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Saved query '{query_id}' not found")
    return result


@router.delete("/saved-queries/{query_id}")
def delete_saved_query(query_id: str):
    if not svc.delete_saved_query(query_id):
        raise HTTPException(status_code=404, detail=f"Saved query '{query_id}' not found")
    return {"ok": True}


@router.post("/saved-queries/{query_id}/favorite", response_model=SavedQueryOut)
def toggle_saved_query_favorite(query_id: str):
    result = svc.update_saved_query(query_id, SavedQueryUpdate(is_favorite=True))
    if not result:
        raise HTTPException(status_code=404, detail=f"Saved query '{query_id}' not found")
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Snippets
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/snippets", response_model=SnippetListResponse)
def list_snippets(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    database_type: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_snippets(
        search=search, category=category, database_type=database_type,
        offset=offset, limit=limit,
    )


@router.get("/snippets/{snippet_id}", response_model=SnippetOut)
def get_snippet(snippet_id: str):
    result = svc.get_snippet(snippet_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Snippet '{snippet_id}' not found")
    return result


@router.post("/snippets", status_code=201, response_model=SnippetOut)
def create_snippet(req: SnippetCreate):
    return svc.create_snippet(req)


@router.put("/snippets/{snippet_id}", response_model=SnippetOut)
def update_snippet(snippet_id: str, req: SnippetUpdate):
    result = svc.update_snippet(snippet_id, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Snippet '{snippet_id}' not found")
    return result


@router.delete("/snippets/{snippet_id}")
def delete_snippet(snippet_id: str):
    if not svc.delete_snippet(snippet_id):
        raise HTTPException(status_code=404, detail=f"Snippet '{snippet_id}' not found")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════
# Query Templates
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/templates", response_model=QueryTemplateListResponse)
def list_templates(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    database_type: Optional[str] = Query(None),
    builtin_only: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_templates(
        search=search, category=category, database_type=database_type,
        builtin_only=builtin_only, offset=offset, limit=limit,
    )


@router.get("/templates/{template_id}", response_model=QueryTemplateOut)
def get_template(template_id: str):
    result = svc.get_template(template_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return result


@router.post("/templates", status_code=201, response_model=QueryTemplateOut)
def create_template(req: QueryTemplateCreate):
    return svc.create_template(req)


@router.put("/templates/{template_id}", response_model=QueryTemplateOut)
def update_template(template_id: str, req: QueryTemplateUpdate):
    result = svc.update_template(template_id, req)
    if not result:
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return result


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    if not svc.delete_template(template_id):
        raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
    return {"ok": True}


@router.post("/templates/{template_id}/apply")
def apply_template(template_id: str, params: Dict[str, Any]):
    """Render a template with parameters and return the generated SQL."""
    try:
        sql = svc.apply_template(template_id, params)
        if sql is None:
            raise HTTPException(status_code=404, detail=f"Template '{template_id}' not found")
        return {"sql": sql}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════
# Query History
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/history", response_model=QueryHistoryListResponse)
def list_history(
    connection_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    database_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_history(
        connection_id=connection_id, status=status,
        database_type=database_type, search=search,
        offset=offset, limit=limit,
    )


@router.delete("/history")
def clear_history(connection_id: Optional[str] = Query(None)):
    """Clear query history, optionally filtered by connection."""
    count = svc.clear_history(connection_id=connection_id)
    return {"ok": True, "deleted": count}


# ═══════════════════════════════════════════════════════════════════════════
# Execution Logs
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/execution-logs", response_model=List[ExecutionLogOut])
def list_execution_logs(
    connection_id: Optional[str] = Query(None),
    history_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    return svc.list_execution_logs(
        connection_id=connection_id, history_id=history_id,
        offset=offset, limit=limit,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Connections (for workbench toolbar)
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/connections", response_model=List[ConnectionBrief])
def list_connections():
    """List available connections for the workbench connection selector."""
    return svc.list_connections_brief()
