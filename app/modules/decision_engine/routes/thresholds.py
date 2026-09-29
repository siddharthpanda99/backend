"""Threshold Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    ThresholdPolicyRead,
    ThresholdPolicyUpdate,
)

from common_lib.modules.decision_engine.services import DecisionRegistryService

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/thresholds", tags=["Thresholds"])
_service = DecisionRegistryService()


@router.get("", response_model=ThresholdPolicyRead)
async def get_thresholds():
    """Get current threshold policy."""
    _require_fabric()

    try:
        policy = _service.get_thresholds()
        return ThresholdPolicyRead.model_validate(policy)
    except Exception as e:
        raise http_error(e, prefix="Get thresholds failed")


@router.patch("", response_model=ThresholdPolicyRead)
async def update_thresholds(request: ThresholdPolicyUpdate):
    """Update threshold policy."""
    _require_fabric()

    try:
        policy = _service.update_thresholds(request)
        return ThresholdPolicyRead.model_validate(policy)
    except ValueError as e:
        raise http_error(e)
    except Exception as e:
        raise http_error(e, prefix="Update thresholds failed")
