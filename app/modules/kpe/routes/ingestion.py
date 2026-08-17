"""KPE Ingestion Route — Thin FastAPI wrapper delegating to common_lib.

All logic lives in common_lib.modules.knowledge_engine.kpe.services.IngestionService.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from common_lib.modules.knowledge_engine.kpe.schemas.ingest import IngestRequest, IngestResponse
from common_lib.modules.knowledge_engine.kpe.services.ingestion_service import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter()

_ingestion_service = IngestionService()


@router.post("/", response_model=IngestResponse)
async def ingest_content(payload: IngestRequest):
    """Ingest content via the KPE pipeline."""
    try:
        return await _ingestion_service.ingest(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Ingestion failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs", response_model=List[dict])
async def list_ingestion_logs(
    limit: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = Query(None),
):
    """List recent ingestion logs."""
    try:
        return await _ingestion_service.list_logs(
            limit=limit, source_type=source_type
        )
    except Exception as e:
        logger.error("Failed to list ingestion logs: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
