"""Model Registry Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    DecisionModelSpecCreate,
    DecisionModelSpecRead,
    DecisionModelSpecList,
    CalibrationRequest,
    CalibrationResponse,
)

from common_lib.modules.decision_engine.services import DecisionRegistryService

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/models", tags=["Models"])
_service = DecisionRegistryService()


def _to_read(spec: object) -> DecisionModelSpecRead:
    """Shape a DecisionModelSpec dataclass for the response schema.

    DecisionModelSpec.calibration is a CalibrationSpec dataclass, which the
    CalibrationSpecBase model cannot validate directly from attributes — go
    through the spec's own to_dict() which already serializes nested records.
    """
    data = spec.to_dict() if hasattr(spec, "to_dict") else spec
    return DecisionModelSpecRead.model_validate(data)


@router.get("", response_model=DecisionModelSpecList)
async def list_models():
    """List all registered decision models."""
    _require_fabric()

    try:
        models = _service.list_models()
        return DecisionModelSpecList(
            items=[_to_read(m) for m in models],
            total=len(models),
        )
    except Exception as e:
        raise http_error(e, prefix="List models failed")


@router.get("/{model_id}", response_model=DecisionModelSpecRead)
async def get_model(model_id: str):
    """Get model by ID."""
    _require_fabric()

    try:
        model = _service.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return _to_read(model)
    except HTTPException:
        raise
    except Exception as e:
        raise http_error(e, prefix="Get model failed")


@router.post("", response_model=DecisionModelSpecRead)
async def register_model(request: DecisionModelSpecCreate):
    """Register a new decision model."""
    _require_fabric()

    try:
        model = _service.register_model(request)
        return _to_read(model)
    except ValueError as e:
        raise http_error(e)
    except Exception as e:
        raise http_error(e, prefix="Register model failed")


@router.post("/{model_id}/calibrate", response_model=CalibrationResponse)
async def calibrate_model(model_id: str, request: CalibrationRequest):
    """Calibrate a model on a dataset."""
    _require_fabric()

    try:
        result = _service.calibrate_model(model_id, request)
        return CalibrationResponse(
            calibration_spec=result,
            status="success",
        )
    except ValueError as e:
        raise http_error(e)
    except Exception as e:
        raise http_error(e, prefix="Calibration failed")
