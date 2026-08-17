"""Knowledge Hub — Packet Routes.

Endpoints:
    GET    /knowledge-hub/packets                  — List packets
    POST   /knowledge-hub/packets                  — Create packet
    GET    /knowledge-hub/packets/{id}             — Get packet
    PUT    /knowledge-hub/packets/{id}             — Update packet
    DELETE /knowledge-hub/packets/{id}             — Delete packet
    POST   /knowledge-hub/packets/{id}/resolve     — Resolve/aggregate packet data
    POST   /knowledge-hub/packets/{id}/verify      — Verify packet
    GET    /knowledge-hub/packets/{id}/data        — Get resolved data
    POST   /knowledge-hub/packets/{id}/test-all    — Test all sources/pipelines

    # Phase 3 enhancements
    GET    /knowledge-hub/packets/{id}/items        — List items
    POST   /knowledge-hub/packets/{id}/items        — Add item
    DELETE /knowledge-hub/packets/{id}/items/{item_id} — Remove item
    PUT    /knowledge-hub/packets/{id}/items/reorder    — Reorder items
    PUT    /knowledge-hub/packets/{id}/items/{item_id}/pin — Pin/unpin item
    POST   /knowledge-hub/packets/{id}/publish     — Publish packet
    POST   /knowledge-hub/packets/{id}/unpublish   — Unpublish packet
    GET    /knowledge-hub/packets/{id}/export      — Export (json, markdown)
    POST   /knowledge-hub/packets/{id}/duplicate   — Duplicate packet
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_engine.knowledge_hub.models import PacketRecord, PacketItemRecord
from common_lib.modules.knowledge_engine.knowledge_hub.services.packet_service import (
    PacketService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-hub", tags=["Knowledge Hub — Packets"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class PacketCreate(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., description="Packet name for curation")
    description: Optional[str] = None
    source_config_ids: List[str] = Field(default_factory=list)
    pipeline_ids: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    packet_type: str = Field("curated", description="curated or dynamic")


class PacketUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_config_ids: Optional[List[str]] = None
    pipeline_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    packet_type: Optional[str] = None


class PacketItemCreate(BaseModel):
    id: Optional[str] = None
    item_type: str = Field(default="chunk", description="chunk or custom_note")
    chunk_id: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    relevance_note: Optional[str] = None
    added_by: Optional[str] = None
    pinned: bool = False
    sort_order: Optional[int] = None


class PacketReorderRequest(BaseModel):
    item_ids: List[str] = Field(..., description="Ordered list of item IDs")


class PacketDuplicateRequest(BaseModel):
    include_items: bool = Field(True, description="Copy items to new packet")


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/packets")
def list_packets(
    status: Optional[str] = Query(None, description="Filter by status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    packet_type: Optional[str] = Query(None, description="Filter by type: curated or dynamic"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List data packets."""
    packets = PacketService.list_packets(session, status=status, tag=tag, packet_type=packet_type)
    return {
        "success": True,
        "data": [_packet_to_dict(p) for p in packets],
        "total": len(packets),
    }


@router.get("/packets/{packet_id}")
def get_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a data packet by ID."""
    record = PacketService.get_packet(session, packet_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {"success": True, "data": _packet_to_dict(record)}


@router.post("/packets", status_code=201)
def create_packet(
    request: PacketCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new data packet."""
    record = PacketService.create_packet(session, request.model_dump())
    return {"success": True, "data": _packet_to_dict(record)}


@router.put("/packets/{packet_id}")
def update_packet(
    request: PacketUpdate,
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update an existing data packet. Auto-increments version on content change."""
    record = PacketService.update_packet(
        session, packet_id, request.model_dump(exclude_none=True)
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {"success": True, "data": _packet_to_dict(record)}


@router.delete("/packets/{packet_id}")
def delete_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a data packet and all its items."""
    deleted = PacketService.delete_packet(session, packet_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {"success": True, "message": f"Packet '{packet_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Resolve / Data / Test All / Verify
# ═══════════════════════════════════════════════════════════════════


@router.post("/packets/{packet_id}/resolve")
def resolve_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Resolve/aggregate all data from sources and pipelines in a packet."""
    result = PacketService.resolve_packet(session, packet_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.get("/packets/{packet_id}/data")
def get_packet_data(
    packet_id: str = Path(..., description="Packet ID"),
    filter: Optional[str] = Query(None, alias="filter", description="Text filter"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get the resolved data for a packet."""
    result = PacketService.get_packet_data(
        session, packet_id, filter_query=filter
    )
    if not result.get("success"):
        raise HTTPException(status_code=404, detail="Packet not found")
    return result


@router.post("/packets/{packet_id}/test-all")
def test_all_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Test all sources and pipelines in a packet."""
    result = PacketService.test_all(session, packet_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/packets/{packet_id}/verify")
def verify_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Mark a data packet as verified (after successful testing)."""
    record = PacketService.verify_packet(session, packet_id)
    if not record:
        existing = PacketService.get_packet(session, packet_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Cannot verify packet: run test-all first and ensure all pass",
            )
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": _packet_to_dict(record),
        "message": f"Packet '{record.name}' verified successfully",
    }


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Publish / Unpublish
# ═══════════════════════════════════════════════════════════════════


@router.post("/packets/{packet_id}/publish")
def publish_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Publish a packet, making it publicly accessible."""
    record = PacketService.publish_packet(session, packet_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": _packet_to_dict(record),
        "message": f"Packet '{record.name}' published",
    }


@router.post("/packets/{packet_id}/unpublish")
def unpublish_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Unpublish a packet, reverting to draft status."""
    record = PacketService.unpublish_packet(session, packet_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": _packet_to_dict(record),
        "message": f"Packet '{record.name}' unpublished",
    }


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Export
# ═══════════════════════════════════════════════════════════════════


@router.get("/packets/{packet_id}/export")
def export_packet(
    packet_id: str = Path(..., description="Packet ID"),
    fmt: str = Query("json", description="Export format: json or markdown"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Export a packet in JSON or Markdown format.

    JSON includes full structured data with metadata and items.
    Markdown produces a human-readable document with item sections.
    """
    if fmt not in ("json", "markdown"):
        raise HTTPException(status_code=400, detail="Format must be 'json' or 'markdown'")
    result = PacketService.export_packet(session, packet_id, fmt=fmt)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Duplicate
# ═══════════════════════════════════════════════════════════════════


@router.post("/packets/{packet_id}/duplicate", status_code=201)
def duplicate_packet(
    request: PacketDuplicateRequest,
    packet_id: str = Path(..., description="Packet ID to duplicate"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Duplicate a packet with a '(Copy)' suffix. Optionally copy items."""
    record = PacketService.duplicate_packet(
        session, packet_id, include_items=request.include_items,
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": _packet_to_dict(record),
        "message": f"Packet duplicated as '{record.name}'",
    }


# ═══════════════════════════════════════════════════════════════════
# Phase 3: Item CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/packets/{packet_id}/items")
def list_packet_items(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all items in a packet, ordered by sort_order."""
    packet = PacketService.get_packet(session, packet_id)
    if not packet:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    items = PacketService.list_items(session, packet_id)
    return {
        "success": True,
        "data": {
            "packet_id": packet_id,
            "items": [_item_to_dict(i) for i in items],
            "total": len(items),
        },
    }


@router.post("/packets/{packet_id}/items", status_code=201)
def add_packet_item(
    request: PacketItemCreate,
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Add an item to a packet."""
    item = PacketService.add_item(session, packet_id, request.model_dump(exclude_none=True))
    if not item:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": _item_to_dict(item),
        "message": "Item added to packet",
    }


@router.delete("/packets/{packet_id}/items/{item_id}")
def remove_packet_item(
    packet_id: str = Path(..., description="Packet ID"),
    item_id: str = Path(..., description="Item ID to remove"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Remove an item from a packet."""
    removed = PacketService.remove_item(session, packet_id, item_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Item not found in packet")
    return {"success": True, "message": "Item removed from packet"}


@router.put("/packets/{packet_id}/items/reorder")
def reorder_packet_items(
    request: PacketReorderRequest,
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Reorder items within a packet."""
    items = PacketService.reorder_items(session, packet_id, request.item_ids)
    if items is None:
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": {
            "items": [_item_to_dict(i) for i in items],
            "total": len(items),
        },
        "message": "Items reordered",
    }


@router.put("/packets/{packet_id}/items/{item_id}/pin")
def pin_packet_item(
    item_id: str = Path(..., description="Item ID"),
    packet_id: str = Path(..., description="Packet ID"),
    pinned: bool = Query(True, description="Pin or unpin"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Pin or unpin an item. Pinned items survive dynamic refresh."""
    item = PacketService.pin_item(session, packet_id, item_id, pinned=pinned)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in packet")
    return {
        "success": True,
        "data": _item_to_dict(item),
        "message": f"Item {'pinned' if pinned else 'unpinned'}",
    }


# ── Serialization helpers ─────────────────────────────────────


def _packet_to_dict(record: PacketRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "status": record.status,
        "version": record.version,
        "packet_type": record.packet_type,
        "is_published": record.is_published,
        "published_at": record.published_at.isoformat() if record.published_at else None,
        "verified_at": record.verified_at.isoformat() if record.verified_at else None,
        "verified_by": record.verified_by,
        "source_config_ids": record.source_config_ids,
        "pipeline_ids": record.pipeline_ids,
        "resolved_data": record.resolved_data,
        "data_size_bytes": record.data_size_bytes,
        "tags": record.tags,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "updated_at": record.updated_at.isoformat() if record.updated_at else None,
    }


def _item_to_dict(item: PacketItemRecord) -> Dict[str, Any]:
    return {
        "id": item.id,
        "packet_id": item.packet_id,
        "item_type": item.item_type,
        "chunk_id": item.chunk_id,
        "title": item.title,
        "content": item.content,
        "relevance_note": item.relevance_note,
        "added_by": item.added_by,
        "added_at": item.added_at.isoformat() if item.added_at else None,
        "pinned": item.pinned,
        "sort_order": item.sort_order,
    }
