"""
Knowledge Hub — Packet Routes.

Endpoints:
    GET    /knowledge-hub/packets                — List packets
    POST   /knowledge-hub/packets                — Create packet
    GET    /knowledge-hub/packets/{id}           — Get packet
    PUT    /knowledge-hub/packets/{id}           — Update packet
    DELETE /knowledge-hub/packets/{id}           — Delete packet
    POST   /knowledge-hub/packets/{id}/resolve   — Resolve/aggregate packet data
    POST   /knowledge-hub/packets/{id}/verify    — Verify packet
    GET    /knowledge-hub/packets/{id}/data      — Get resolved data
    POST   /knowledge-hub/packets/{id}/test-all  — Test all sources/pipelines
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_hub.models import PacketRecord
from common_lib.modules.knowledge_hub.services.packet_service import (
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


class PacketUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_config_ids: Optional[List[str]] = None
    pipeline_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None


# ═══════════════════════════════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/packets")
def list_packets(
    status: Optional[str] = Query(None, description="Filter by status"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List data packets."""
    packets = PacketService.list_packets(session, status=status, tag=tag)
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
    """Update an existing data packet."""
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
    """Delete a data packet."""
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
    """Resolve/aggregate all data from sources and pipelines in a packet.

    Runs execute on all associated sources and pipelines, caches
    the consolidated result, and returns the resolved data summary.
    """
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
    """Get the resolved data for a packet.

    If not yet resolved, triggers resolution first.
    Optional filter parameter for text search within the data.
    """
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
    """Test all sources and pipelines in a packet.

    Runs execute on every associated source and pipeline, reporting
    pass/fail status for each. Use this before marking as verified
    to ensure all data extraction is working.
    """
    result = PacketService.test_all(session, packet_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result


@router.post("/packets/{packet_id}/verify")
def verify_packet(
    packet_id: str = Path(..., description="Packet ID"),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Mark a data packet as verified (after successful testing).

    Only verified packets can be included in production projects
    and attached to agents.
    """
    record = PacketService.verify_packet(session, packet_id)
    if not record:
        # Check if it exists but tests failed
        existing = PacketService.get_packet(session, packet_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot verify packet '{packet_id}': "
                    "run test-all first and ensure all sources/pipelines pass"
                ),
            )
        raise HTTPException(status_code=404, detail=f"Packet '{packet_id}' not found")
    return {
        "success": True,
        "data": _packet_to_dict(record),
        "message": f"Packet '{record.name}' verified successfully",
    }


# ── Serialization helpers ─────────────────────────────────────


def _packet_to_dict(record: PacketRecord) -> Dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "description": record.description,
        "status": record.status,
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
