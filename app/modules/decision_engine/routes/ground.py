"""Grounding Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    GroundRequest,
    GroundResponse,
)

from common_lib.modules.decision_engine.services import DecisionEngineService

router = APIRouter(prefix="/ground", tags=["Ground"])
_service = DecisionEngineService()


@router.post("", response_model=GroundResponse)
async def ground_claims(request: GroundRequest):
    """Run grounding pipeline: extract claims, retrieve evidence, verify, compute coverage."""
    try:
        result = _service.ground_claims(request)
        return GroundResponse(
            grounding_coverage=result,
            status="success",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Grounding failed: {e}")
