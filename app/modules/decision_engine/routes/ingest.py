"""Intent Ingestion Routes."""

from fastapi import APIRouter, HTTPException

from common_lib.modules.decision_engine.schemas import (
    IngestRequest,
    IngestResponse,
)

from common_lib.modules.decision_engine.services import IntentIngestionService

router = APIRouter(prefix="/ingest", tags=["Ingest"])
_service = IntentIngestionService()


@router.post("", response_model=IngestResponse)
async def ingest_intent(request: IngestRequest):
    """Parse user request into structured goal specification."""
    try:
        result = _service.ingest_intent(request)
        return IngestResponse(
            goal_spec=result,
            status="success",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
