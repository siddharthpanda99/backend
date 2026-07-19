"""Data Pipeline module API routes — Ingestion, Extraction, RAG, Observability.

Thin routing layer that delegates to common_lib.modules.data_pipeline services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    source: str
    content: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 10
    filters: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Lazy service loader
# ---------------------------------------------------------------------------

def _get_pipeline_service():
    from common_lib.modules.data_pipeline.service import DataPipelineService
    return DataPipelineService()


# ---------------------------------------------------------------------------
# Pipeline endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def pipeline_status() -> Dict[str, Any]:
    """Get pipeline status and statistics."""
    try:
        svc = _get_pipeline_service()
        result = svc.get_status() if hasattr(svc, "get_status") else {"status": "ok"}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest")
async def ingest_data(request: IngestRequest) -> Dict[str, Any]:
    """Ingest data from a source into the pipeline."""
    try:
        svc = _get_pipeline_service()
        result = svc.ingest(request.source, request.content, request.config)
        return {"result": result, "message": "Data ingested successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract")
async def extract_data(source: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Extract data from a source."""
    try:
        svc = _get_pipeline_service()
        result = svc.extract(source, config) if hasattr(svc, "extract") else {"source": source}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/normalize")
async def normalize_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize data for storage."""
    try:
        svc = _get_pipeline_service()
        result = svc.normalize(data) if hasattr(svc, "normalize") else data
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed")
async def embed_content(content: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Generate embeddings for content."""
    try:
        svc = _get_pipeline_service()
        result = svc.embed(content, model) if hasattr(svc, "embed") else {"content": content}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Query endpoints
# ---------------------------------------------------------------------------

@router.post("/query")
async def query_pipeline(request: QueryRequest) -> Dict[str, Any]:
    """Query the pipeline (RAG retrieval)."""
    try:
        svc = _get_pipeline_service()
        result = svc.query(request.query, request.top_k, request.filters) if hasattr(svc, "query") else {"query": request.query, "results": []}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ner")
async def extract_entities(text: str) -> Dict[str, Any]:
    """Extract named entities from text."""
    try:
        svc = _get_pipeline_service()
        result = svc.extract_entities(text) if hasattr(svc, "extract_entities") else {"text": text, "entities": []}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Storage endpoints
# ---------------------------------------------------------------------------

@router.get("/storage/stats")
async def storage_stats() -> Dict[str, Any]:
    """Get storage statistics (vector, document, graph)."""
    try:
        svc = _get_pipeline_service()
        result = svc.get_storage_stats() if hasattr(svc, "get_storage_stats") else {}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Observability endpoints
# ---------------------------------------------------------------------------

@router.get("/observability/pipelines")
async def list_pipelines() -> Dict[str, Any]:
    """List all active pipelines."""
    try:
        svc = _get_pipeline_service()
        result = svc.list_pipelines() if hasattr(svc, "list_pipelines") else []
        return {"pipelines": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
