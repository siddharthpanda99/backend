"""Decision Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    DecideRequest,
    DecideResponse,
)

from common_lib.modules.decision_engine.services import DecisionEngineService

router = APIRouter(prefix="/decide", tags=["Decide"])
_service = DecisionEngineService()


@router.post("", response_model=DecideResponse)
async def route_decision(request: DecideRequest):
    """Run cascaded decision engine (tiers 1-5) and return decision."""
    try:
        result = _service.route_decision(request)
        return DecideResponse(
            decision=result,
            status="success",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision failed: {e}")
