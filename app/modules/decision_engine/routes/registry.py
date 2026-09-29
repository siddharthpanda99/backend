"""Decision Registry routes — model registry and threshold management.

This router deliberately declares **no** ``prefix=``. The re-basing of
``/registry/*`` onto the router root is the served contract: the Decision
Fabric UI client (``DecisionFabricPage/services/decisionApi.ts``) calls
``PATCH /decision-engine/models/{id}`` with the ``updates`` envelope declared
below, ``GET /decision-engine/calibration/{id}`` and
``GET /decision-engine/thresholds/{decision_type}``, all at the root, and the
regression is pinned by ``tests/test_decision_fabric_e2e.py``.

Mounted paths (relative to the ``/decision-engine`` mount):

PATCH  /models/{model_id}                     — update an existing model
DELETE /models/{model_id}                    — delete (archive) a model
POST   /thresholds                           — update threshold policies
GET    /thresholds/{decision_type}           — effective thresholds for a decision
GET    /model/{decision_type}/{tier}         — best model for decision/tier
POST   /calibration                          — record calibration results
GET    /calibration/{model_id}               — calibration history for a model

Removed as unreachable dead code (P0, shadowed routes)
------------------------------------------------------
Four handlers used to be declared here at the same paths as ``models.py`` and
``thresholds.py``. FastAPI resolves to the first registration, so these four
were never reachable — and each would additionally have 500'd had it been
called, because they declared ``dict``/``list[dict]`` responses while returning
``DecisionModelSpec`` dataclass instances. The survivors are the correct single
home, per G10 (the Pydantic schema is the contract):

* ``GET /models``          -> ``models.py`` (``DecisionModelSpecList``).
* ``GET /models/{id}``     -> ``models.py`` (``DecisionModelSpecRead`` + 404 on
  a miss, where the dead handler returned ``null``).
* ``POST /models``         -> ``models.py`` (``DecisionModelSpecCreate`` ->
  ``DecisionModelSpecRead``). The dead handler wanted a ``{"model_spec": ...}``
  envelope; the UI posts the fields flat.
* ``GET /thresholds``      -> ``thresholds.py`` (``ThresholdPolicyRead`` from
  ``get_thresholds()``). The dead handler called ``load_thresholds()``, which is
  not a separate capability: ``DecisionRegistryService.__init__`` already reads
  that same ``config/thresholds.yaml``, and re-reading it only differs by
  raising ``FileNotFoundError`` -> 500 when the file is absent, where
  ``get_thresholds()`` returns the working default. Reading the current policy
  therefore remains reachable, and in strictly better shape.

No capability was dropped: every one of the four is still served by the
surviving route, which ``app/modules/decision_engine/tests/test_routes.py``
covers (``test_list_models``, ``test_get_model``, ``test_get_thresholds``).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.modules.decision_engine.routes._errors import http_error

from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter()


# Request/Response models
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


@router.patch("/models/{model_id}")
async def update_model(model_id: str, payload: UpdateModelRequest) -> dict[str, Any]:
    """PATCH /registry/models/{model_id} — update an existing decision model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.update_model(model_id, payload.updates)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Model update not yet implemented")


@router.delete("/models/{model_id}")
async def delete_model(model_id: str) -> dict[str, Any]:
    """DELETE /registry/models/{model_id} — delete (archive) a decision model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.delete_model(model_id)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Model deletion not yet implemented")


@router.post("/thresholds")
async def update_thresholds(payload: UpdateThresholdsRequest) -> dict[str, Any]:
    """POST /registry/thresholds — update threshold policies."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.update_thresholds(payload.thresholds)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Threshold update not yet implemented")


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
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Threshold resolution not yet implemented")


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
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Model selection not yet implemented")


@router.post("/calibration")
async def record_calibration(payload: RecordCalibrationRequest) -> dict[str, Any]:
    """POST /registry/calibration — record calibration results for a model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.record_calibration(payload.model_id, payload.calibration_data)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Calibration recording not yet implemented")


@router.get("/calibration/{model_id}")
async def get_calibration_history(model_id: str) -> list[dict[str, Any]]:
    """GET /registry/calibration/{model_id} — get calibration history for a model."""
    _require_fabric()

    from common_lib.modules.decision_engine.services import DecisionRegistryService

    service = DecisionRegistryService()
    try:
        return service.get_calibration_history(model_id)
    except NotImplementedError as exc:
        raise http_error(exc, prefix="Calibration history not yet implemented")
