"""Grounding Routes."""

from fastapi import APIRouter

from common_lib.modules.decision_engine.schemas import (
    GroundRequest,
    GroundResponse,
)

from common_lib.modules.decision_engine.services import DecisionEngineService

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/ground", tags=["Ground"])
_service = DecisionEngineService()


@router.post("", response_model=GroundResponse)
async def ground_claims(request: GroundRequest):
    """Run grounding pipeline: extract claims, retrieve evidence, verify, compute coverage."""
    _require_fabric()

    try:
        result = _service.ground_claims(request)
        return GroundResponse(
            grounding_coverage=result,
            status="success",
        )
    except Exception as e:
        raise http_error(e, prefix="Grounding failed")
