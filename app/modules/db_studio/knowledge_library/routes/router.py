"""Thin FastAPI router for Query History, Snippets & Templates (UDS Module 21)."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.knowledge_library import (
    KnowledgeLibraryService,
    HistoryRecordCreate, HistoryRecordOut, HistorySearchRequest,
    SavedQueryCreate, SavedQueryUpdate, SavedQueryOut,
    SnippetCreate, SnippetUpdate, SnippetOut, SnippetVersionOut,
    TemplateCreate, TemplateUpdate, TemplateOut,
    CollectionCreate, CollectionUpdate, CollectionOut,
    CollectionItemAdd, CollectionItemOut,
    TagCreate, TagOut,
    SearchRequest, SearchResultOut,
    KnowledgeLibraryDashboardOut,
)

router = APIRouter(prefix="/api/v1/knowledge-library", tags=["Query History, Snippets & Templates"])
svc = KnowledgeLibraryService()


# ── History ────────────────────────────────────────────────────────────

@router.post("/history", response_model=HistoryRecordOut)
def record_execution(req: HistoryRecordCreate):
    return svc.record_execution(req)


@router.get("/history", response_model=List[HistoryRecordOut])
def list_history(
    workspace_id: Optional[str] = None,
    database_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_history(workspace_id, database_type, status, limit)


@router.get("/history/search", response_model=List[HistoryRecordOut])
def search_history(req: HistorySearchRequest):
    return svc.search_history(req)


@router.get("/history/{history_id}", response_model=HistoryRecordOut)
def get_history(history_id: str):
    h = svc.get_history(history_id)
    if not h:
        raise HTTPException(404, "History record not found")
    return h


@router.post("/history/{history_id}/favorite", response_model=HistoryRecordOut)
def toggle_favorite(history_id: str):
    h = svc.toggle_favorite(history_id)
    if not h:
        raise HTTPException(404, "History record not found")
    return h


@router.post("/history/{history_id}/pin", response_model=HistoryRecordOut)
def toggle_pin(history_id: str):
    h = svc.toggle_pin(history_id)
    if not h:
        raise HTTPException(404, "History record not found")
    return h


# ── Saved Queries ─────────────────────────────────────────────────────

@router.post("/queries", response_model=SavedQueryOut)
def create_saved_query(req: SavedQueryCreate):
    return svc.create_saved_query(req)


@router.get("/queries", response_model=List[SavedQueryOut])
def list_saved_queries(
    category: Optional[str] = None,
    language: Optional[str] = None,
    workspace_id: Optional[str] = None,
    starred: Optional[bool] = None,
    limit: int = 50,
):
    return svc.list_saved_queries(category, language, workspace_id, starred, limit)


@router.get("/queries/{query_id}", response_model=SavedQueryOut)
def get_saved_query(query_id: str):
    q = svc.get_saved_query(query_id)
    if not q:
        raise HTTPException(404, "Saved query not found")
    return q


@router.put("/queries/{query_id}", response_model=SavedQueryOut)
def update_saved_query(query_id: str, req: SavedQueryUpdate):
    q = svc.update_saved_query(query_id, req)
    if not q:
        raise HTTPException(404, "Saved query not found")
    return q


@router.delete("/queries/{query_id}")
def delete_saved_query(query_id: str):
    if not svc.delete_saved_query(query_id):
        raise HTTPException(404, "Saved query not found")
    return {"ok": True}


# ── Snippets ───────────────────────────────────────────────────────────

@router.post("/snippets", response_model=SnippetOut)
def create_snippet(req: SnippetCreate):
    return svc.create_snippet(req)


@router.get("/snippets", response_model=List[SnippetOut])
def list_snippets(
    language: Optional[str] = None,
    category: Optional[str] = None,
    workspace_id: Optional[str] = None,
    team_only: Optional[bool] = None,
    starred: Optional[bool] = None,
    limit: int = 50,
):
    return svc.list_snippets(language, category, workspace_id, team_only, starred, limit)


@router.get("/snippets/{snippet_id}", response_model=SnippetOut)
def get_snippet(snippet_id: str):
    s = svc.get_snippet(snippet_id)
    if not s:
        raise HTTPException(404, "Snippet not found")
    return s


@router.put("/snippets/{snippet_id}", response_model=SnippetOut)
def update_snippet(snippet_id: str, req: SnippetUpdate):
    s = svc.update_snippet(snippet_id, req)
    if not s:
        raise HTTPException(404, "Snippet not found")
    return s


@router.delete("/snippets/{snippet_id}")
def delete_snippet(snippet_id: str):
    if not svc.delete_snippet(snippet_id):
        raise HTTPException(404, "Snippet not found")
    return {"ok": True}


@router.get("/snippets/{snippet_id}/versions", response_model=List[SnippetVersionOut])
def list_snippet_versions(snippet_id: str, limit: int = 50):
    return svc.list_snippet_versions(snippet_id, limit)


# ── Templates ──────────────────────────────────────────────────────────

@router.post("/templates", response_model=TemplateOut)
def create_template(req: TemplateCreate):
    return svc.create_template(req)


@router.get("/templates", response_model=List[TemplateOut])
def list_templates(
    template_type: Optional[str] = None,
    language: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_templates(template_type, language, category, limit)


@router.get("/templates/{template_id}", response_model=TemplateOut)
def get_template(template_id: str):
    t = svc.get_template(template_id)
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.put("/templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: str, req: TemplateUpdate):
    t = svc.update_template(template_id, req)
    if not t:
        raise HTTPException(404, "Template not found")
    return t


@router.delete("/templates/{template_id}")
def delete_template(template_id: str):
    if not svc.delete_template(template_id):
        raise HTTPException(404, "Template not found")
    return {"ok": True}


# ── Collections ────────────────────────────────────────────────────────

@router.post("/collections", response_model=CollectionOut)
def create_collection(req: CollectionCreate):
    return svc.create_collection(req)


@router.get("/collections", response_model=List[CollectionOut])
def list_collections(workspace_id: Optional[str] = None, limit: int = 50):
    return svc.list_collections(workspace_id, limit)


@router.put("/collections/{collection_id}", response_model=CollectionOut)
def update_collection(collection_id: str, req: CollectionUpdate):
    c = svc.update_collection(collection_id, req)
    if not c:
        raise HTTPException(404, "Collection not found")
    return c


@router.delete("/collections/{collection_id}")
def delete_collection(collection_id: str):
    if not svc.delete_collection(collection_id):
        raise HTTPException(404, "Collection not found")
    return {"ok": True}


@router.post("/collections/{collection_id}/items", response_model=CollectionItemOut)
def add_collection_item(collection_id: str, req: CollectionItemAdd):
    return svc.add_collection_item(collection_id, req)


@router.get("/collections/{collection_id}/items", response_model=List[CollectionItemOut])
def list_collection_items(collection_id: str, limit: int = 100):
    return svc.list_collection_items(collection_id, limit)


@router.delete("/collections/items/{item_id}")
def remove_collection_item(item_id: str):
    if not svc.remove_collection_item(item_id):
        raise HTTPException(404, "Collection item not found")
    return {"ok": True}


# ── Tags ───────────────────────────────────────────────────────────────

@router.post("/tags", response_model=TagOut)
def create_tag(req: TagCreate):
    return svc.create_tag(req)


@router.get("/tags", response_model=List[TagOut])
def list_tags(workspace_id: Optional[str] = None, limit: int = 100):
    return svc.list_tags(workspace_id, limit)


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: str):
    if not svc.delete_tag(tag_id):
        raise HTTPException(404, "Tag not found")
    return {"ok": True}


# ── Search ─────────────────────────────────────────────────────────────

@router.post("/search", response_model=List[SearchResultOut])
def search(req: SearchRequest):
    return svc.search(req)


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=KnowledgeLibraryDashboardOut)
def knowledge_library_dashboard():
    return svc.get_dashboard()
