"""
Knowledge Engine — Relationship Routes.

Thin transport for relationship CRUD operations.
Delegates to common_lib.modules.knowledge_engine.services.entity_service.EntityService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.models.entity import (
    EntityRelationship,
)
from common_lib.modules.knowledge_engine.services.entity_service import (
    get_entity_service,
)

router = APIRouter(prefix="/relationships", tags=["Knowledge Engine — Relationships"])


# ── Request/Response Models ────────────────────────────────────


class RelationshipCreateRequest(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str = Field(..., min_length=1, max_length=128)
    relationship_subtype: str | None = None
    direction: str = "directed"
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_from: str | None = None  # ISO datetime
    valid_to: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipUpdateRequest(BaseModel):
    relationship_type: str | None = Field(None, min_length=1, max_length=128)
    relationship_subtype: str | None = None
    direction: str | None = None
    weight: float | None = Field(None, ge=0.0, le=1.0)
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    valid_from: str | None = None
    valid_to: str | None = None
    properties: dict[str, Any] | None = None
    superseded_by: UUID | None = None


class RelationshipResponse(BaseModel):
    relationship: EntityRelationship


class RelationshipListResponse(BaseModel):
    relationships: list[EntityRelationship]


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get entity service instance (handles relationships too)."""
    return get_entity_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=RelationshipResponse, status_code=201)
async def create_relationship(
    request: RelationshipCreateRequest,
    service=Depends(get_service),
    created_by: str = Query(default="api", description="Creator identifier"),
):
    """Create a relationship between entities."""
    try:
        relationship = await service.create_relationship(
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
            relationship_type=request.relationship_type,
            relationship_subtype=request.relationship_subtype,
            direction=request.direction,
            weight=request.weight,
            confidence=request.confidence,
            properties=request.properties,
            created_by=created_by,
        )
        if not relationship:
            raise HTTPException(
                status_code=404, detail="Source or target entity not found"
            )
        return RelationshipResponse(relationship=relationship)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create relationship: {exc}"
        ) from exc


@router.get("/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(
    relationship_id: UUID,
    service=Depends(get_service),
):
    """Get a relationship by ID."""
    try:
        relationship = await service.get_relationship(relationship_id)
        if not relationship:
            raise HTTPException(
                status_code=404, detail=f"Relationship {relationship_id} not found"
            )
        return RelationshipResponse(relationship=relationship)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get relationship: {exc}"
        ) from exc


@router.get("", response_model=RelationshipListResponse)
async def list_relationships(
    entity_id: UUID | None = Query(
        None, description="Filter by entity (source or target)"
    ),
    relationship_type: str | None = Query(
        None, description="Filter by relationship type"
    ),
    service=Depends(get_service),
):
    """List relationships."""
    try:
        relationships = await service.list_relationships(
            entity_id=entity_id,
            relationship_type=relationship_type,
        )
        return RelationshipListResponse(relationships=relationships)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list relationships: {exc}"
        ) from exc


@router.put("/{relationship_id}", response_model=RelationshipResponse)
async def update_relationship(
    relationship_id: UUID,
    request: RelationshipUpdateRequest,
    service=Depends(get_service),
):
    """Update a relationship."""
    try:
        # Get existing relationship
        relationship = await service.get_relationship(relationship_id)
        if not relationship:
            raise HTTPException(
                status_code=404, detail=f"Relationship {relationship_id} not found"
            )

        # Note: The service doesn't have an update_relationship method yet,
        # so we'd need to delete and recreate or add the method.
        # For now, return the existing one with a message.
        raise HTTPException(
            status_code=501,
            detail="Relationship update not yet implemented; use delete + create",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update relationship: {exc}"
        ) from exc


@router.delete("/{relationship_id}")
async def delete_relationship(
    relationship_id: UUID,
    service=Depends(get_service),
):
    """Delete a relationship."""
    try:
        success = await service.delete_relationship(relationship_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Relationship {relationship_id} not found"
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete relationship: {exc}"
        ) from exc
