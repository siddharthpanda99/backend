"""
Knowledge Engine — Claim Routes.

Thin transport for claim CRUD operations.
Delegates to common_lib.modules.knowledge_engine.services.claim_service.ClaimService
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.models.claim import (
    Claim,
    ClaimType,
    ClaimStatus,
    EpistemicState,
    ClaimVersion,
    ClaimContradiction,
    KnowledgeGap,
)
from common_lib.modules.knowledge_engine.services.claim_service import get_claim_service

router = APIRouter(prefix="/claims", tags=["Knowledge Engine — Claims"])


# ── Request/Response Models ────────────────────────────────────


class ClaimCreateRequest(BaseModel):
    claim_type: ClaimType = ClaimType.FACT
    subject: str = Field(..., min_length=1, max_length=512)
    predicate: str = Field(..., min_length=1, max_length=512)
    object: str | None = Field(None, max_length=512)
    object_value: str | None = None
    object_type: str | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    scope: str | None = None
    conditions: list[str] = Field(default_factory=list)
    exceptions: list[str] = Field(default_factory=list)
    epistemic_state: EpistemicState = EpistemicState.CANDIDATE
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    source_document_ids: list[str] = Field(default_factory=list)
    extraction_method: str = "auto"
    tenant_id: str | None = None


class ClaimUpdateRequest(BaseModel):
    subject: str | None = Field(None, min_length=1, max_length=512)
    predicate: str | None = Field(None, min_length=1, max_length=512)
    object: str | None = Field(None, max_length=512)
    object_value: str | None = None
    object_type: str | None = None
    qualifiers: dict[str, Any] | None = None
    scope: str | None = None
    conditions: list[str] | None = None
    exceptions: list[str] | None = None
    epistemic_state: EpistemicState | None = None
    status: ClaimStatus | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    evidence_ids: list[str] | None = None
    evidence_strength: float | None = Field(None, ge=0.0, le=1.0)
    contradicts_claim_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None
    validated: bool | None = None
    change_reason: str | None = None


class ClaimResponse(BaseModel):
    claim: Claim


class ClaimListResponse(BaseModel):
    claims: list[Claim]
    total: int


class ClaimVersionsResponse(BaseModel):
    claim: Claim
    versions: list[ClaimVersion]


class ContradictionCreateRequest(BaseModel):
    claim_id_1: str
    claim_id_2: str
    contradiction_type: str = "semantic"
    severity: str = "medium"
    value_1: str | None = None
    value_2: str | None = None
    evidence_supporting_1: list[str] = Field(default_factory=list)
    evidence_supporting_2: list[str] = Field(default_factory=list)
    detected_by: str = "system"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ContradictionResponse(BaseModel):
    contradiction: ClaimContradiction


class ContradictionResolveRequest(BaseModel):
    resolution_method: str = "manual"
    resolution_note: str | None = None
    resolved_by: str | None = None


class KnowledgeGapCreateRequest(BaseModel):
    gap_type: str
    description: str
    affected_entities: list[str] = Field(default_factory=list)
    affected_claims: list[str] = Field(default_factory=list)
    context: str | None = None
    source_document_ids: list[str] = Field(default_factory=list)
    priority: str = "medium"
    assigned_to: str | None = None


class KnowledgeGapResponse(BaseModel):
    gap: KnowledgeGap


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get claim service instance."""
    return get_claim_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=ClaimResponse, status_code=201)
async def create_claim(
    request: ClaimCreateRequest,
    service=Depends(get_service),
    extracted_by: str = Query(default="api", description="Extractor identifier"),
):
    """Create a new claim."""
    try:
        claim = await service.create_claim(
            claim_type=request.claim_type,
            subject=request.subject,
            predicate=request.predicate,
            object=request.object,
            object_value=request.object_value,
            object_type=request.object_type,
            qualifiers=request.qualifiers,
            scope=request.scope,
            conditions=request.conditions,
            exceptions=request.exceptions,
            epistemic_state=request.epistemic_state,
            confidence=request.confidence,
            evidence_ids=request.evidence_ids,
            source_document_ids=request.source_document_ids,
            extraction_method=request.extraction_method,
            extracted_by=extracted_by,
            tenant_id=request.tenant_id,
        )
        return ClaimResponse(claim=claim)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create claim: {exc}"
        ) from exc


@router.get("/{claim_id}", response_model=ClaimResponse)
async def get_claim(
    claim_id: str | UUID,
    include_versions: bool = Query(False, description="Include version history"),
    service=Depends(get_service),
):
    """Get a claim by ID."""
    try:
        if include_versions:
            result = await service.get_claim(str(claim_id), include_versions=True)
            if not result:
                raise HTTPException(
                    status_code=404, detail=f"Claim {claim_id} not found"
                )
            return ClaimVersionsResponse(**result)
        claim = await service.get_claim(str(claim_id), include_versions=False)
        if not claim:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        return ClaimResponse(claim=claim)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get claim: {exc}"
        ) from exc


@router.get("", response_model=ClaimListResponse)
async def list_claims(
    claim_type: ClaimType | None = Query(None, description="Filter by claim type"),
    epistemic_state: EpistemicState | None = Query(
        None, description="Filter by epistemic state"
    ),
    status: ClaimStatus | None = Query(None, description="Filter by status"),
    subject: str | None = Query(None, description="Filter by subject"),
    predicate: str | None = Query(None, description="Filter by predicate"),
    tenant_id: str | None = Query(None, description="Filter by tenant"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List claims with filtering."""
    try:
        result = await service.list_claims(
            claim_type=claim_type,
            epistemic_state=epistemic_state,
            status=status,
            subject=subject,
            predicate=predicate,
            tenant_id=tenant_id,
            limit=limit,
            offset=offset,
        )
        return ClaimListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list claims: {exc}"
        ) from exc


@router.put("/{claim_id}", response_model=ClaimResponse)
async def update_claim(
    claim_id: str | UUID,
    request: ClaimUpdateRequest,
    service=Depends(get_service),
    updated_by: str = Query(default="api", description="Updater identifier"),
    validated_by: str | None = Query(None, description="Validator identifier"),
):
    """Update a claim."""
    try:
        claim = await service.update_claim(
            claim_id=str(claim_id),
            subject=request.subject,
            predicate=request.predicate,
            object=request.object,
            object_value=request.object_value,
            object_type=request.object_type,
            qualifiers=request.qualifiers,
            scope=request.scope,
            conditions=request.conditions,
            exceptions=request.exceptions,
            epistemic_state=request.epistemic_state,
            status=request.status,
            confidence=request.confidence,
            evidence_ids=request.evidence_ids,
            evidence_strength=request.evidence_strength,
            contradicts_claim_ids=request.contradicts_claim_ids,
            metadata=request.metadata,
            validated=request.validated,
            validated_by=validated_by,
            updated_by=updated_by,
            change_reason=request.change_reason,
        )
        if not claim:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        return ClaimResponse(claim=claim)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update claim: {exc}"
        ) from exc


@router.delete("/{claim_id}")
async def delete_claim(
    claim_id: str | UUID,
    hard_delete: bool = Query(False, description="Hard delete (permanent)"),
    service=Depends(get_service),
):
    """Delete a claim (soft delete by default)."""
    try:
        result = await service.delete_claim(str(claim_id), hard_delete=hard_delete)
        if not result["success"]:
            raise HTTPException(status_code=404, detail=f"Claim {claim_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete claim: {exc}"
        ) from exc


# ── Versioning Routes ─────────────────────────────────────────


@router.get("/{claim_id}/versions", response_model=list[ClaimVersion])
async def get_claim_versions(
    claim_id: str | UUID,
    service=Depends(get_service),
):
    """Get version history for a claim."""
    try:
        versions = await service.get_claim_versions(str(claim_id))
        return versions
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get versions: {exc}"
        ) from exc


@router.get("/{claim_id}/versions/{version}", response_model=ClaimVersion)
async def get_claim_version(
    claim_id: str | UUID,
    version: int,
    service=Depends(get_service),
):
    """Get a specific version of a claim."""
    try:
        claim_version = await service.get_claim_version(str(claim_id), version)
        if not claim_version:
            raise HTTPException(
                status_code=404,
                detail=f"Version {version} not found for claim {claim_id}",
            )
        return claim_version
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get version: {exc}"
        ) from exc


@router.post("/{claim_id}/rollback", response_model=ClaimResponse)
async def rollback_claim(
    claim_id: str | UUID,
    target_version: int = Query(..., description="Target version to rollback to"),
    service=Depends(get_service),
    rolled_back_by: str = Query(default="api", description="Rollback initiator"),
    rollback_reason: str | None = Query(None, description="Rollback reason"),
):
    """Rollback claim to a previous version."""
    try:
        claim = await service.rollback_claim(
            claim_id=str(claim_id),
            target_version=target_version,
            rolled_back_by=rolled_back_by,
            rollback_reason=rollback_reason,
        )
        if not claim:
            raise HTTPException(
                status_code=404,
                detail=f"Claim {claim_id} or version {target_version} not found",
            )
        return ClaimResponse(claim=claim)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to rollback claim: {exc}"
        ) from exc


# ── Contradiction Routes ──────────────────────────────────────


@router.post("/contradictions", response_model=ContradictionResponse, status_code=201)
async def create_contradiction(
    request: ContradictionCreateRequest,
    service=Depends(get_service),
):
    """Record a contradiction between two claims."""
    try:
        contradiction = await service.create_contradiction(
            claim_id_1=request.claim_id_1,
            claim_id_2=request.claim_id_2,
            contradiction_type=request.contradiction_type,
            severity=request.severity,
            value_1=request.value_1,
            value_2=request.value_2,
            evidence_supporting_1=request.evidence_supporting_1,
            evidence_supporting_2=request.evidence_supporting_2,
            detected_by=request.detected_by,
            confidence=request.confidence,
        )
        return ContradictionResponse(contradiction=contradiction)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create contradiction: {exc}"
        ) from exc


@router.put(
    "/contradictions/{contradiction_id}/resolve", response_model=ContradictionResponse
)
async def resolve_contradiction(
    contradiction_id: UUID,
    request: ContradictionResolveRequest,
    service=Depends(get_service),
):
    """Resolve a contradiction."""
    try:
        contradiction = await service.resolve_contradiction(
            contradiction_id=contradiction_id,
            resolution_method=request.resolution_method,
            resolution_note=request.resolution_note,
            resolved_by=request.resolved_by,
        )
        if not contradiction:
            raise HTTPException(
                status_code=404, detail=f"Contradiction {contradiction_id} not found"
            )
        return ContradictionResponse(contradiction=contradiction)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to resolve contradiction: {exc}"
        ) from exc


# ── Knowledge Gap Routes ──────────────────────────────────────


@router.post("/gaps", response_model=KnowledgeGapResponse, status_code=201)
async def create_knowledge_gap(
    request: KnowledgeGapCreateRequest,
    service=Depends(get_service),
):
    """Create a knowledge gap record."""
    try:
        gap = await service.create_knowledge_gap(
            gap_type=request.gap_type,
            description=request.description,
            affected_entities=request.affected_entities,
            affected_claims=request.affected_claims,
            context=request.context,
            source_document_ids=request.source_document_ids,
            priority=request.priority,
            assigned_to=request.assigned_to,
        )
        return KnowledgeGapResponse(gap=gap)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create knowledge gap: {exc}"
        ) from exc


@router.get("/gaps", response_model=list[KnowledgeGapResponse])
async def list_knowledge_gaps(
    status: str | None = Query(None, description="Filter by status"),
    priority: str | None = Query(None, description="Filter by priority"),
    gap_type: str | None = Query(None, description="Filter by gap type"),
    service=Depends(get_service),
):
    """List knowledge gaps."""
    try:
        gaps = await service.list_knowledge_gaps(
            status=status,
            priority=priority,
            gap_type=gap_type,
        )
        return [KnowledgeGapResponse(gap=g) for g in gaps]
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list knowledge gaps: {exc}"
        ) from exc
