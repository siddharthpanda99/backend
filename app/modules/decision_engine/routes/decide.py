"""Decide Routes."""

from fastapi import APIRouter

from common_lib.modules.decision_engine.schemas import (
    DecideRequest,
    DecideResponse,
)

from common_lib.modules.decision_engine.services import DecisionEngineService

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/decide", tags=["Decide"])
_service = DecisionEngineService()


@router.post("", response_model=DecideResponse)
async def route_decision(request: DecideRequest):
    """Run cascaded decision engine (tiers 1-5) and return decision."""
    _require_fabric()

    try:
        result = _service.route_decision(request)
        return DecideResponse(
            decision=result,
            status="success",
        )
    except NotImplementedError as e:
        # Raised when an optional inference backend is absent. Distinct from a
        # domain error: the request was fine, the capability was not wired up.
        raise http_error(e, prefix="Decision routing not yet implemented")
    except Exception as e:
        raise http_error(e, prefix="Decision failed")
