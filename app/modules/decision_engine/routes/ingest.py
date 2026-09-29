"""Intent Ingestion Routes."""

from fastapi import APIRouter

from common_lib.modules.decision_engine.schemas import (
    IngestRequest,
    IngestResponse,
)

from common_lib.modules.decision_engine.services import IntentIngestionService

from app.modules.decision_engine.routes._errors import http_error
from app.modules.decision_engine.routes._flags import (
    require_fabric as _require_fabric,
)

router = APIRouter(prefix="/ingest", tags=["Ingest"])
_service = IntentIngestionService()


@router.post("", response_model=IngestResponse)
async def ingest_intent(request: IngestRequest):
    """Parse user request into structured goal specification."""
    _require_fabric()

    try:
        result = _service.ingest_intent(request)
        return IngestResponse(
            goal_spec=result,
            status="success",
        )
    except ValueError as e:
        raise http_error(e)
    except Exception as e:
        raise http_error(e, prefix="Ingestion failed")
