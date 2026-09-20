"""
Knowledge Engine — Evidence Routes.

Thin transport for evidence CRUD operations.
Delegates to common_lib.modules.knowledge_engine.services.evidence_service.EvidenceService
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.knowledge_engine.services.evidence_service import (
    Evidence,
    EvidenceType,
    EvidenceSource,
    get_evidence_service,
)

router = APIRouter(prefix="/evidence", tags=["Knowledge Engine — Evidence"])


# ── Request/Response Models ────────────────────────────────────


class EvidenceCreateRequest(BaseModel):
    content: str
    evidence_type: EvidenceType = EvidenceType.DOCUMENT
    source: EvidenceSource = EvidenceSource.INGESTION
    title: str | None = None
    summary: str | None = None
    source_document_id: str | None = None
    source_uri: str | None = None
    source_metadata: dict[str, Any] | None = None
    extraction_method: str = "auto"
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    extracted_by: str | None = None
    supports_claim_ids: list[str] = Field(default_factory=list)
    contradicts_claim_ids: list[str] = Field(default_factory=list)
    related_entity_ids: list[str] = Field(default_factory=list)
    provenance_chain: list[dict[str, Any]] = Field(default_factory=list)
    parent_evidence_ids: list[str] = Field(default_factory=list)
    tenant_id: str | None = None
    classification: str = "public"


class EvidenceUpdateRequest(BaseModel):
    content: str | None = None
    title: str | None = None
    summary: str | None = None
    source_metadata: dict[str, Any] | None = None
    extraction_confidence: float | None = Field(None, ge=0.0, le=1.0)
    validated: bool | None = None
    validated_by: str | None = None
    validation_notes: str | None = None
    supports_claim_ids: list[str] | None = None
    contradicts_claim_ids: list[str] | None = None
    related_entity_ids: list[str] | None = None
    provenance_chain: list[dict[str, Any]] | None = None
    parent_evidence_ids: list[str] | None = None
    classification: str | None = None
    metadata_json: dict[str, Any] | None = None


class EvidenceResponse(BaseModel):
    evidence: Evidence


class EvidenceListResponse(BaseModel):
    evidence: list[Evidence]
    total: int


class ProvenanceStepRequest(BaseModel):
    step: dict[str, Any]


# ── Dependency Injection ────────────────────────────────────────


def get_service() -> Any:
    """Get evidence service instance."""
    return get_evidence_service()


# ── Routes ─────────────────────────────────────────────────────


@router.post("", response_model=EvidenceResponse, status_code=201)
async def create_evidence(
    request: EvidenceCreateRequest,
    service=Depends(get_service),
):
    """Create a new evidence record."""
    try:
        evidence = await service.create_evidence(
            content=request.content,
            evidence_type=request.evidence_type,
            source=request.source,
            title=request.title,
            summary=request.summary,
            source_document_id=request.source_document_id,
            source_uri=request.source_uri,
            source_metadata=request.source_metadata,
            extraction_method=request.extraction_method,
            extraction_confidence=request.extraction_confidence,
            extracted_by=request.extracted_by,
            supports_claim_ids=request.supports_claim_ids,
            contradicts_claim_ids=request.contradicts_claim_ids,
            related_entity_ids=request.related_entity_ids,
            provenance_chain=request.provenance_chain,
            parent_evidence_ids=request.parent_evidence_ids,
            tenant_id=request.tenant_id,
            classification=request.classification,
        )
        return EvidenceResponse(evidence=evidence)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to create evidence: {exc}"
        ) from exc


@router.get("/{evidence_id}", response_model=EvidenceResponse)
async def get_evidence(
    evidence_id: str,
    service=Depends(get_service),
):
    """Get evidence by ID."""
    try:
        evidence = await service.get_evidence(evidence_id)
        if not evidence:
            raise HTTPException(
                status_code=404, detail=f"Evidence {evidence_id} not found"
            )
        return EvidenceResponse(evidence=evidence)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get evidence: {exc}"
        ) from exc


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    evidence_type: EvidenceType | None = Query(None, description="Filter by type"),
    source: EvidenceSource | None = Query(None, description="Filter by source"),
    source_document_id: str | None = Query(
        None, description="Filter by source document"
    ),
    supports_claim_id: str | None = Query(
        None, description="Filter by supported claim"
    ),
    contradicts_claim_id: str | None = Query(
        None, description="Filter by contradicted claim"
    ),
    related_entity_id: str | None = Query(None, description="Filter by related entity"),
    tenant_id: str | None = Query(None, description="Filter by tenant"),
    validated: bool | None = Query(None, description="Filter by validated"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset"),
    service=Depends(get_service),
):
    """List evidence with filtering."""
    try:
        result = await service.list_evidence(
            evidence_type=evidence_type,
            source=source,
            source_document_id=source_document_id,
            supports_claim_id=supports_claim_id,
            contradicts_claim_id=contradicts_claim_id,
            related_entity_id=related_entity_id,
            tenant_id=tenant_id,
            validated=validated,
            limit=limit,
            offset=offset,
        )
        return EvidenceListResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to list evidence: {exc}"
        ) from exc


@router.put("/{evidence_id}", response_model=EvidenceResponse)
async def update_evidence(
    evidence_id: str,
    request: EvidenceUpdateRequest,
    service=Depends(get_service),
):
    """Update evidence record."""
    try:
        evidence = await service.update_evidence(
            evidence_id=evidence_id,
            content=request.content,
            title=request.title,
            summary=request.summary,
            source_metadata=request.source_metadata,
            extraction_confidence=request.extraction_confidence,
            validated=request.validated,
            validated_by=request.validated_by,
            validation_notes=request.validation_notes,
            supports_claim_ids=request.supports_claim_ids,
            contradicts_claim_ids=request.contradicts_claim_ids,
            related_entity_ids=request.related_entity_ids,
            provenance_chain=request.provenance_chain,
            parent_evidence_ids=request.parent_evidence_ids,
            classification=request.classification,
            metadata_json=request.metadata_json,
        )
        if not evidence:
            raise HTTPException(
                status_code=404, detail=f"Evidence {evidence_id} not found"
            )
        return EvidenceResponse(evidence=evidence)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to update evidence: {exc}"
        ) from exc


@router.delete("/{evidence_id}")
async def delete_evidence(
    evidence_id: str,
    service=Depends(get_service),
):
    """Delete evidence record."""
    try:
        success = await service.delete_evidence(evidence_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Evidence {evidence_id} not found"
            )
        return {"success": True}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete evidence: {exc}"
        ) from exc


# ── Provenance Routes ─────────────────────────────────────────


@router.get("/{evidence_id}/provenance", response_model=list[dict[str, Any]])
async def get_evidence_provenance(
    evidence_id: str,
    service=Depends(get_service),
):
    """Get provenance chain for evidence."""
    try:
        provenance = await service.get_provenance(evidence_id)
        return provenance
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get provenance: {exc}"
        ) from exc


@router.post("/{evidence_id}/provenance", response_model=EvidenceResponse)
async def add_provenance_step(
    evidence_id: str,
    request: ProvenanceStepRequest,
    service=Depends(get_service),
):
    """Add a step to the provenance chain."""
    try:
        evidence = await service.add_provenance_step(
            evidence_id=evidence_id,
            step=request.step,
        )
        if not evidence:
            raise HTTPException(
                status_code=404, detail=f"Evidence {evidence_id} not found"
            )
        return EvidenceResponse(evidence=evidence)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to add provenance step: {exc}"
        ) from exc
