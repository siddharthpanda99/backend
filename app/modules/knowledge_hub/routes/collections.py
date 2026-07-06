"""
Collections — FastAPI Routes.

Endpoints:
    GET    /collections              — List root collections
    POST   /collections              — Create collection
    GET    /collections/tree         — Full nested tree
    GET    /collections/{id}         — Get collection
    PUT    /collections/{id}         — Update collection
    DELETE /collections/{id}         — Delete collection (recursive)
    POST   /collections/{id}/attach-agent    — Attach to agent
    POST   /collections/{id}/attach-session  — Attach to chat session
    POST   /collections/{id}/detach          — Detach from agent/session
    POST   /collections/{id}/items           — Add item
    DELETE /collections/{id}/items/{item_id} — Remove item
    POST   /collections/{id}/search          — Search within collection
    GET    /collections/{id}/sources         — Get all source IDs (flat)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.collections.service import CollectionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/collections", tags=["Collections"])


# ── Pydantic Schemas ───────────────────────────────────────────────

class CollectionCreate(BaseModel):
    name: str = Field(..., description="Collection name")
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    parent_collection_id: Optional[str] = None
    is_public: bool = False
    owner_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class CollectionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class AddItemRequest(BaseModel):
    item_type: str = Field(
        ..., description="file, api_source, sub_collection, knowledge_project, custom_note"
    )
    source_id: str = Field(..., description="ID of the referenced entity")
    label: Optional[str] = None
    relevance_note: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    sort_order: int = 0
    pinned: bool = False


class AttachAgentRequest(BaseModel):
    agent_id: str = Field(..., description="Agent ID to attach to")


class AttachSessionRequest(BaseModel):
    session_id: str = Field(..., description="Chat session ID to attach to")


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    limit: int = Field(default=20, description="Max results")


# ── Routes ──────────────────────────────────────────────────────────

@router.get("")
def list_collections(
    parent_id: Optional[str] = Query(None, description="Filter by parent collection"),
    owner_id: Optional[str] = Query(None, description="Filter by owner"),
    attached_agent_id: Optional[str] = Query(None, description="Filter by attached agent"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List collections (root level by default)."""
    collections = CollectionService.list_collections(
        session, parent_id=parent_id, owner_id=owner_id, attached_agent_id=attached_agent_id
    )
    return {
        "success": True,
        "data": [_to_dict(c) for c in collections],
        "total": len(collections),
    }


@router.get("/tree")
def get_tree(
    root_id: Optional[str] = Query(None, description="Root collection ID (null = all roots)"),
    max_depth: int = Query(10, ge=1, le=20),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get the full collection tree (nested)."""
    tree = CollectionService.get_full_tree(session, root_id=root_id, max_depth=max_depth)
    return {"success": True, **tree}


@router.post("", status_code=201)
def create_collection(
    request: CollectionCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new collection."""
    record = CollectionService.create_collection(session, request.model_dump())
    return {"success": True, "data": _to_dict(record)}


@router.get("/{collection_id}")
def get_collection(
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a collection by ID with its items."""
    record = CollectionService.get_collection(session, collection_id)
    if not record:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    items = CollectionService.list_items(session, collection_id)
    return {
        "success": True,
        "data": _to_dict(record, items=[_item_to_dict(i) for i in items]),
    }


@router.put("/{collection_id}")
def update_collection(
    request: CollectionUpdate,
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update a collection."""
    record = CollectionService.update_collection(
        session, collection_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    return {"success": True, "data": _to_dict(record)}


@router.delete("/{collection_id}")
def delete_collection(
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a collection (recursive — deletes children and items)."""
    deleted = CollectionService.delete_collection(session, collection_id)
    if not deleted:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    return {"success": True, "message": f"Collection '{collection_id}' deleted"}


# ── Agent / Session Attachment ─────────────────────────────────────

@router.post("/{collection_id}/attach-agent")
def attach_to_agent(
    request: AttachAgentRequest,
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Attach a collection to an agent as its knowledge boundary."""
    record = CollectionService.attach_to_agent(session, collection_id, request.agent_id)
    if not record:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    return {"success": True, "data": _to_dict(record)}


@router.post("/{collection_id}/attach-session")
def attach_to_session(
    request: AttachSessionRequest,
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Attach a collection to a chat session as its knowledge boundary."""
    record = CollectionService.attach_to_session(session, collection_id, request.session_id)
    if not record:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    return {"success": True, "data": _to_dict(record)}


@router.post("/{collection_id}/detach")
def detach_collection(
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Detach a collection from its agent/session."""
    record = CollectionService.detach(session, collection_id)
    if not record:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    return {"success": True, "data": _to_dict(record)}


# ── Items ──────────────────────────────────────────────────────────

@router.post("/{collection_id}/items", status_code=201)
def add_item(
    request: AddItemRequest,
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Add an item (file, API, sub-collection, project, or note) to a collection."""
    # Verify collection exists
    collection = CollectionService.get_collection(session, collection_id)
    if not collection:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    item = CollectionService.add_item(
        session,
        collection_id=collection_id,
        item_type=request.item_type,
        source_id=request.source_id,
        label=request.label,
        relevance_note=request.relevance_note,
        tags=request.tags,
        sort_order=request.sort_order,
        pinned=request.pinned,
    )
    return {"success": True, "data": _item_to_dict(item)}


@router.delete("/{collection_id}/items/{item_id}")
def remove_item(
    collection_id: str = Path(...),
    item_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Remove an item from a collection."""
    removed = CollectionService.remove_item(session, item_id)
    if not removed:
        raise HTTPException(404, f"Item '{item_id}' not found")
    return {"success": True, "message": f"Item '{item_id}' removed"}


# ── Search & Sources ──────────────────────────────────────────────

@router.post("/{collection_id}/search")
def search_collection(
    request: SearchRequest,
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Search across all items in a collection (and sub-collections)."""
    collection = CollectionService.get_collection(session, collection_id)
    if not collection:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    results = CollectionService.search_in_collection(
        session, collection_id, request.query, limit=request.limit
    )
    return {"success": True, "data": results, "total": len(results)}


@router.get("/{collection_id}/sources")
def get_all_sources(
    collection_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get all source IDs (flat) in a collection tree."""
    collection = CollectionService.get_collection(session, collection_id)
    if not collection:
        raise HTTPException(404, f"Collection '{collection_id}' not found")
    sources = CollectionService.get_all_source_ids(session, collection_id)
    return {"success": True, "data": sources, "total": len(sources)}


# ── Serialization helpers ──────────────────────────────────────────

def _to_dict(record, items=None):
    d = {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "icon": record.icon,
        "color": record.color,
        "parent_collection_id": record.parent_collection_id,
        "item_count": record.item_count,
        "total_descendant_count": record.total_descendant_count,
        "attached_agent_id": record.attached_agent_id,
        "attached_session_id": record.attached_session_id,
        "is_public": record.is_public,
        "owner_id": record.owner_id,
        "tags": record.tags,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }
    if items is not None:
        d["items"] = items
    return d


def _item_to_dict(item):
    return {
        "id": item.id,
        "collection_id": item.collection_id,
        "item_type": item.item_type,
        "source_id": item.source_id,
        "label": item.label,
        "sort_order": item.sort_order,
        "pinned": item.pinned,
        "relevance_note": item.relevance_note,
        "tags": item.tags,
        "added_at": item.added_at.isoformat() if item.added_at else None,
    }
