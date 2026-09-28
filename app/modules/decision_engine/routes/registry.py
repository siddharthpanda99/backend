"""Decision Registry routes — model registry and threshold management.

GET  /api/v1/decision-engine/registry/models          — list registered decision models
GET  /api/v1/decision-engine/registry/models/{id}     — get a specific model
POST /api/v1/decision-engine/registry/models          — register a new model
PATCH /api/v1/decision-engine/registry/models/{id}    — update an existing model
DELETE /api/v1/decision-engine/registry/models/{id}   — delete (archive) a model

GET  /api/v1/decision-engine/registry/thresholds      — load threshold policies
POST /api/v1/decision-engine/registry/thresholds      — update threshold policies
GET  /api/v1/decision-engine/registry/thresholds/{decision_type} — get thresholds for decision
GET  /api/v1/decision-engine/registry/model/{decision_type}/{tier} — get best model for decision/tier

POST /api/v1/decision-engine/registry/calibration     — record calibration results
GET  /api/v1/decision-engine/registry/calibration/{model_id} — get calibration history
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from common_lib.modules.decision_engine.flags import (
    NEXUS_DECISION_FABRIC_ENABLED,
    is_decision_flag_enabled,
)

router = APIRouter()


def _require_fabric() -> None:
    """Fail-closed flag guard: 503 until NEXUS_DECISION_FABRIC_ENABLED is on."""
    if not is_decision_flag_enabled(NEXUS_DECISION_FABRIC_ENABLED):
        raise HTTPException(
            status_code=503,
            detail="Decision Fabric is disabled (NEXUS_DECISION_FABRIC_ENABLED=off)",
        )


# Request/Response models
class RegisterModelRequest(BaseModel):
    """Request to register a new decision model."""

    model_spec: dict[str, Any] = Field(..., description="DecisionModelSpec dict")


class UpdateModelRequest(BaseModel):
    """Request to update an existing decision model."""

    updates: dict[str, Any] = Field(..., description="Fields to update")


class UpdateThresholdsRequest(BaseModel):
    """Request to update threshold policies."""

    thresholds: dict[str, Any] = Field(..., description="ThresholdPolicy dict")


class RecordCalibrationRequest(BaseModel):
    """Request to record calibration results."""

    model_id: str = Field(..., description="Model identifier")
    calibration_data: dict[str, Any] = Field(
        ..., description="CalibrationSpec with metrics, samples, timestamp"
    )


class GetModelForDecisionRequest(BaseModel):
    """Request to get best model for decision type at tier."""

    decision_type: str = Field(..., description="One of DECISION_TYPES")
    tier: int = Field(
        ..., description="Pipeline tier (1=rule, 2=heuristic, 3=model, 4=llm, 5=human)"
    )


@router.get("/models")
async def list_models() -> list[dict[str, Any]]:
    """GET /registry/models — list registered decision models."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.list_models()
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Model listing not yet implemented")


@router.get("/models/{model_id}")
async def get_model(model_id: str) -> dict[str, Any] | None:
    """GET /registry/models/{model_id} — get a specific decision model by ID."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.get_model(model_id)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Model retrieval not yet implemented"
        )


@router.post("/models")
async def register_model(payload: RegisterModelRequest) -> dict[str, Any]:
    """POST /registry/models — register a new decision model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.register_model(payload.model_spec)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Model registration not yet implemented"
        )


@router.patch("/models/{model_id}")
async def update_model(model_id: str, payload: UpdateModelRequest) -> dict[str, Any]:
    """PATCH /registry/models/{model_id} — update an existing decision model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.update_model(model_id, payload.updates)
    except NotImplementedError:
        raise HTTPException(status_code=501, detail="Model update not yet implemented")


@router.delete("/models/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    """DELETE /registry/models/{model_id} — delete (archive) a decision model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.delete_model(model_id)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Model deletion not yet implemented"
        )


@router.get("/thresholds")
async def load_thresholds() -> dict[str, Any]:
    """GET /registry/thresholds — load threshold policies from config."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.load_thresholds()
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Threshold loading not yet implemented"
        )


@router.post("/thresholds")
async def update_thresholds(payload: UpdateThresholdsRequest) -> dict[str, Any]:
    """POST /registry/thresholds — update threshold policies."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.update_thresholds(payload.thresholds)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Threshold update not yet implemented"
        )


@router.get("/thresholds/{decision_type}")
async def get_thresholds_for_decision(
    decision_type: str, model_id: str | None = None
) -> dict[str, Any]:
    """GET /registry/thresholds/{decision_type} — get effective thresholds for a decision.

    Resolves thresholds in order: model-specific → decision-type-specific → global.
    """
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.get_thresholds_for_decision(decision_type, model_id)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Threshold resolution not yet implemented"
        )


@router.get("/model/{decision_type}/{tier}")
async def get_model_for_decision(
    decision_type: str, tier: int
) -> dict[str, Any] | None:
    """GET /registry/model/{decision_type}/{tier} — get the best model for a decision type at a specific tier."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        spec = service.get_model_for_decision(decision_type, tier)
        # The response is declared as a plain dict but the service returns a
        # DecisionModelSpec dataclass, which FastAPI cannot serialise — the
        # endpoint 500'd on every call until this conversion.
        return spec.to_dict() if spec is not None else None
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Model selection not yet implemented"
        )


@router.post("/calibration")
async def record_calibration(payload: RecordCalibrationRequest) -> dict[str, Any]:
    """POST /registry/calibration — record calibration results for a model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.record_calibration(payload.model_id, payload.calibration_data)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Calibration recording not yet implemented"
        )


@router.get("/calibration/{model_id}")
async def get_calibration_history(model_id: str) -> list[dict[str, Any]]:
    """GET /registry/calibration/{model_id} — get calibration history for a model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.get_calibration_history(model_id)
    except NotImplementedError:
        raise HTTPException(
            status_code=501, detail="Calibration history not yet implemented"
        )
