"""Threshold Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    ThresholdPolicyRead,
    ThresholdPolicyUpdate,
)

from common_lib.modules.decision_engine.services import DecisionRegistryService

router = APIRouter(prefix="/thresholds", tags=["Thresholds"])
_service = DecisionRegistryService()


@router.get("", response_model=ThresholdPolicyRead)
async def get_thresholds():
    """Get current threshold policy."""
    try:
        policy = _service.get_thresholds()
        return ThresholdPolicyRead.model_validate(policy)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get thresholds failed: {e}")


@router.patch("", response_model=ThresholdPolicyRead)
async def update_thresholds(request: ThresholdPolicyUpdate):
    """Update threshold policy."""
    try:
        policy = _service.update_thresholds(request)
        return ThresholdPolicyRead.model_validate(policy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update thresholds failed: {e}")
