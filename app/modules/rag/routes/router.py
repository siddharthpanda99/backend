"""RAG contracts routes — thin routers delegating to common_lib (RAG-P0-002).

Schema publish only: ``GET /rag/contracts/status`` and
``GET /rag/contracts/schemas`` stay visible while the flag is OFF;
``POST /rag/contracts/validate/*`` answer 404 while OFF (G9).
G1: no business logic here. G6: no tables.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag/contracts", tags=["RAG Contracts"])

_FLAG = "rag.contracts.enabled"


def _require_flag() -> None:
    try:
        from common_lib.modules.rag.flags import is_enabled
    except ImportError:
        raise HTTPException(status_code=404, detail="RAG contracts unavailable")
    if is_enabled(_FLAG):
        return
    raise HTTPException(
        status_code=404,
        detail=(
            "RAG contracts validation is gated behind the feature flag "
            f"'{_FLAG}', which is currently OFF. Enable "
            "RAG_CONTRACTS_ENABLED=true and restart."
        ),
    )


def _service():
    from common_lib.modules.rag.service import get_contract_service

    return get_contract_service()


@router.get("/status")
async def contracts_status() -> Dict[str, Any]:
    """Contracts version, flag state, model list, state enumerations (visible while OFF)."""
    return _service().status()


@router.get("/schemas")
async def contracts_schemas() -> Dict[str, Any]:
    """Publish JSON Schemas for all 8 canonical contracts (visible while OFF)."""
    return _service().publish_schemas()


class ValidateModelRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="ModelDefinition fields")


class ValidateInstanceRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="RuntimeInstance fields")


class ValidateTransitionRequest(BaseModel):
    current: str = Field(..., description="Current state")
    next: str = Field(..., description="Desired state", alias="next_state")

    model_config = {"populate_by_name": True}


class ValidateEvidenceRecordRequest(BaseModel):
    capability_id: str
    state: str
    instance_id: Optional[str] = None
    reason: Optional[str] = None
    remediation_hint: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class ValidateEmbeddingProfileRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="EmbeddingProfile fields")


class ValidateEmbeddingCompatRequest(BaseModel):
    profile: Dict[str, Any] = Field(..., description="EmbeddingProfile fields")
    index: Dict[str, Any] = Field(..., description="Index binding")


class ValidateArtifactRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="KnowledgeArtifact fields")


class ValidateEvidenceItemRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="EvidenceItem fields")


class ValidatePipelineRequest(BaseModel):
    payload: Dict[str, Any] = Field(..., description="PipelineDefinition fields")


def _guarded(fn, *args, **kwargs):
    _require_flag()
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        from common_lib.modules.rag.service import FlagDisabledError

        if isinstance(exc, FlagDisabledError):
            raise HTTPException(status_code=404, detail=str(exc))
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/validate/model")
async def validate_model(request: ValidateModelRequest) -> Dict[str, Any]:
    return _guarded(_service().validate_model, request.payload)


@router.post("/validate/instance")
async def validate_instance(request: ValidateInstanceRequest) -> Dict[str, Any]:
    return _guarded(_service().validate_instance, request.payload)


@router.post("/validate/lifecycle")
async def validate_lifecycle(request: ValidateTransitionRequest) -> Dict[str, Any]:
    return _guarded(_service().validate_lifecycle, request.current, request.next)


@router.post("/validate/evidence-transition")
async def validate_evidence_transition(request: ValidateTransitionRequest) -> Dict[str, Any]:
    return _guarded(_service().validate_evidence, request.current, request.next)


@router.post("/validate/evidence-record")
async def validate_evidence_record(request: ValidateEvidenceRecordRequest) -> Dict[str, Any]:
    return _guarded(_service().record_evidence, request.model_dump())


@router.post("/validate/embedding-profile")
async def validate_embedding_profile(
    request: ValidateEmbeddingProfileRequest,
) -> Dict[str, Any]:
    return _guarded(_service().validate_embedding_profile, request.payload)


@router.post("/validate/embedding-compat")
async def validate_embedding_compat(
    request: ValidateEmbeddingCompatRequest,
) -> Dict[str, Any]:
    return _guarded(
        _service().validate_embedding_compat, request.profile, request.index
    )


@router.post("/validate/artifact")
async def validate_artifact(request: ValidateArtifactRequest) -> Dict[str, Any]:
    return _guarded(_service().validate_artifact, request.payload)


@router.post("/validate/evidence-item")
async def validate_evidence_item(
    request: ValidateEvidenceItemRequest,
) -> Dict[str, Any]:
    return _guarded(_service().validate_evidence_item, request.payload)


@router.post("/validate/pipeline")
async def validate_pipeline(request: ValidatePipelineRequest) -> Dict[str, Any]:
    return _guarded(_service().validate_pipeline, request.payload)
