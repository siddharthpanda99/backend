"""
Knowledge Engine — Entity Routes.

Thin transport for entity CRUD operations.
Delegates to common_lib.modules.knowledge_engine.services.entity_service.EntityService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.models.entity import (
    Entity,
    EntityType,
    EntityStatus,
    EntityVersion,
    EntityRelationship,
)
from common_lib.modules.knowledge_engine.services.entity_service import (
    get_entity_service,
)

router = APIRouter(prefix="/entities", tags=["Knowledge Engine — Entities"])


# ── Request/Response Models ────────────────────────────────────


class EntityCreateRequest(BaseModel):
    entity_type: EntityType
    canonical_name: str = Field(..., min_length=1, max_length=512)
    display_name: str | None = Field(None, max_length=512)
    description: str | None = Field(None, max_length=8192)
    domain: str | None = Field(None, max_length=128)
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    external_ids: dict[str, str] = Field(default_factory=dict)
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tenant_id: str | None = None


class EntityUpdateRequest(BaseModel):
    canonical_name: str | None = Field(None, min_length=1, max_length=512)
    display_name: str | None = Field(None, max_length=512)
    description: str | None = Field(None, max_length=8192)
    domain: str | None = Field(None, max_length=128)
    tags: list[str] | None = None
    aliases: list[str] | None = None
    external_ids: dict[str, str] | None = None
    status: EntityStatus | None = None
    metadata: dict[str, Any] | None = None
    change_reason: str | None = None


class EntityResponse(BaseModel):
    entity: Entity


class EntityListResponse(BaseModel):
    entities: list[Entity]
    total: int


class EntityVersionsResponse(BaseModel):
    entity: Entity
    versions: list[EntityVersion]


class RelationshipCreateRequest(BaseModel):
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str = Field(..., min_length=1, max_length=128)
    relationship_subtype: str | None = None
    direction: str = "directed"
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)


class RelationshipResponse(BaseModel):
    relationship: EntityRelationship


class RelationshipListResponse(BaseModel):
    relationships: list[EntityRelationship]


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get entity service instance."""
    return get_entity_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=EntityResponse, status_code=201)
async def create_entity(
    request: EntityCreateRequest,
    service=Depends(get_service),
    created_by: str = Query(default="api", description="Creator identifier"),
):
    """Create a new entity."""
    try:
        entity = await service.create_entity(
            entity_type=request.entity_type,
            canonical_name=request.canonical_name,
            display_name=request.display_name,
            description=request.description,
            domain=request.domain,
            tags=request.tags,
            aliases=request.aliases,
            external_ids=request.external_ids,
            extraction_confidence=request.extraction_confidence,
            tenant_id=request.tenant_id,
            created_by=created_by,
        )
        return EntityResponse(entity=entity)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create entity: {exc}"
        ) from exc


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    include_versions: bool = Query(False, description="Include version history"),
    service=Depends(get_service),
):
    """Get an entity by ID."""
    try:
        if include_versions:
            result = await service.get_entity(entity_id, include_versions=True)
            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Entity {entity_id} not found"
                )
            return EntityVersionsResponse(**result)
        entity = await service.get_entity(entity_id, include_versions=False)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        return EntityResponse(entity=entity)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get entity: {exc}"
        ) from exc


@router.get("", response_model=EntityListResponse)
async def list_entities(
    entity_type: EntityType | None = Query(None, description="Filter by entity type"),
    domain: str | None = Query(None, description="Filter by domain"),
    status: EntityStatus | None = Query(None, description="Filter by status"),
    tenant_id: str | None = Query(None, description="Filter by tenant"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List entities with filtering."""
    try:
        result = await service.list_entities(
            entity_type=entity_type,
            domain=domain,
            status=status,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )
        return EntityListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list entities: {exc}"
        ) from exc


@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: UUID,
    request: EntityUpdateRequest,
    service=Depends(get_service),
    updated_by: str = Query(default="api", description="Updater identifier"),
):
    """Update an entity."""
    try:
        entity = await service.update_entity(
            entity_id=entity_id,
            canonical_name=request.canonical_name,
            display_name=request.display_name,
            description=request.description,
            domain=request.domain,
            tags=request.tags,
            aliases=request.aliases,
            external_ids=request.external_ids,
            status=request.status,
            metadata=request.metadata,
            updated_by=updated_by,
            change_reason=request.change_reason,
        )
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        return EntityResponse(entity=entity)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update entity: {exc}"
        ) from exc


@router.delete("/{entity_id}")
async def delete_entity(
    entity_id: UUID,
    hard_delete: bool = Query(False, description="Hard delete (permanent)"),
    service=Depends(get_service),
    deleted_by: str = Query(default="api", description="Deleter identifier"),
):
    """Delete an entity (soft delete by default)."""
    try:
        result = await service.delete_entity(
            entity_id=entity_id,
            hard_delete=hard_delete,
            deleted_by=deleted_by,
        )
        if not result["success"]:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete entity: {exc}"
        ) from exc


# ── Versioning Routes ─────────────────────────────────────────


@router.get("/{entity_id}/versions", response_model=list[EntityVersion])
async def get_entity_versions(
    entity_id: UUID,
    service=Depends(get_service),
):
    """Get version history for an entity."""
    try:
        versions = await service.get_entity_versions(entity_id)
        return versions
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get versions: {exc}"
        ) from exc


@router.get("/{entity_id}/versions/{version}", response_model=EntityVersion)
async def get_entity_version(
    entity_id: UUID,
    version: int,
    service=Depends(get_service),
):
    """Get a specific version of an entity."""
    try:
        entity_version = await service.get_entity_version(entity_id, version)
        if not entity_version:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for entity {entity_id}",
            )
        return entity_version
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get version: {exc}"
        ) from exc


@router.post("/{entity_id}/rollback", response_model=EntityResponse)
async def rollback_entity(
    entity_id: UUID,
    target_version: int = Query(..., description="Target version to rollback to"),
    service=Depends(get_service),
    rolled_back_by: str = Query(default="api", description="Rollback initiator"),
    rollback_reason: str | None = Query(None, description="Rollback reason"),
):
    """Rollback entity to a previous version."""
    try:
        entity = await service.rollback_entity(
            entity_id=entity_id,
            target_version=target_version,
            rolled_back_by=rolled_back_by,
            rollback_reason=rollback_reason,
        )
        if not entity:
            raise HTTPException(
                status_code=404,
                detail=f"Entity {entity_id} or version {target_version} not found",
            )
        return EntityResponse(entity=entity)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to rollback entity: {exc}"
        ) from exc


# ── Relationship Routes ───────────────────────────────────────


@router.post("/relationships", response_model=RelationshipResponse, status_code=201)
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


@router.get("/relationships/{relationship_id}", response_model=RelationshipResponse)
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


@router.get("/relationships", response_model=RelationshipListResponse)
async def list_relationships(
    entity_id: UUID | None = Query(None, description="Filter by entity"),
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


@router.delete("/relationships/{relationship_id}")
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
