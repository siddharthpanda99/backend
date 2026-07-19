"""Doc Processing module API routes — PDF extraction, text/metadata/tables.

Thin routing layer that delegates to common_lib.modules.doc_processing services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


class ExtractRequest(BaseModel):
    file_path: str
    options: Optional[Dict[str, Any]] = None


class ExtractTextRequest(BaseModel):
    file_path: str
    pages: Optional[str] = None


class ExtractTablesRequest(BaseModel):
    file_path: str
    pages: Optional[str] = None


class ExtractMetadataRequest(BaseModel):
    file_path: str


def _get_service():
    from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
    return PDFExtractionPipeline()


@router.post("/extract")
async def extract_full(request: ExtractRequest) -> Dict[str, Any]:
    """Full PDF extraction (text + metadata + tables)."""
    try:
        svc = _get_service()
        result = svc.extract(request.file_path, **(request.options or {})) if hasattr(svc, "extract") else {"file": request.file_path}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/text")
async def extract_text(request: ExtractTextRequest) -> Dict[str, Any]:
    """Extract text from PDF."""
    try:
        svc = _get_service()
        result = svc.extract_text(request.file_path, pages=request.pages) if hasattr(svc, "extract_text") else {"text": ""}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/tables")
async def extract_tables(request: ExtractTablesRequest) -> Dict[str, Any]:
    """Extract tables from PDF."""
    try:
        svc = _get_service()
        result = svc.extract_tables(request.file_path, pages=request.pages) if hasattr(svc, "extract_tables") else {"tables": []}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/extract/metadata")
async def extract_metadata(request: ExtractMetadataRequest) -> Dict[str, Any]:
    """Extract metadata from PDF."""
    try:
        svc = _get_service()
        result = svc.extract_metadata(request.file_path) if hasattr(svc, "extract_metadata") else {"metadata": {}}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parsers")
async def list_parsers() -> Dict[str, Any]:
    """List available parsers."""
    try:
        svc = _get_service()
        result = svc.list_parsers() if hasattr(svc, "list_parsers") else []
        return {"parsers": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
