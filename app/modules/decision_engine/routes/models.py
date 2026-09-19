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

router = APIRouter(prefix="/models", tags=["Models"])
_service = DecisionRegistryService()


@router.get("", response_model=DecisionModelSpecList)
async def list_models():
    """List all registered decision models."""
    try:
        models = _service.list_models()
        return DecisionModelSpecList(
            items=[DecisionModelSpecRead.model_validate(m) for m in models]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List models failed: {e}")


@router.get("/{model_id}", response_model=DecisionModelSpecRead)
async def get_model(model_id: str):
    """Get model by ID."""
    try:
        model = _service.get_model(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return DecisionModelSpecRead.model_validate(model)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get model failed: {e}")


@router.post("", response_model=DecisionModelSpecRead)
async def register_model(request: DecisionModelSpecCreate):
    """Register a new decision model."""
    try:
        model = _service.register_model(request)
        return DecisionModelSpecRead.model_validate(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Register model failed: {e}")


@router.post("/{model_id}/calibrate", response_model=CalibrationResponse)
async def calibrate_model(model_id: str, request: CalibrationRequest):
    """Calibrate a model on a dataset."""
    try:
        result = _service.calibrate_model(model_id, request)
        return CalibrationResponse(
            calibration_spec=result,
            status="success",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibration failed: {e}")
