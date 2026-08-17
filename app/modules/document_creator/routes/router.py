"""Document Creator — FastAPI Routes.

Endpoints:
    POST /documents/create          — Create document from data
    GET  /documents/formats         — List supported formats
    POST /documents/preview         — Preview document (returns base64)
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from common_lib.modules.doc_processing.document_creator.service import get_document_creator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Document Creator"])


# ── Schemas ───────────────────────────────────────────────────────

class DocumentCreateRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="List of row objects")
    format: str = Field(default="pdf", description="pdf, excel, markdown, html, csv")
    title: str = Field(default="Document", description="Document title")
    filename: Optional[str] = Field(default=None, description="Output filename")
    columns: Optional[List[str]] = Field(default=None, description="Specific columns to include")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")


class DocumentPreviewRequest(BaseModel):
    data: List[Dict[str, Any]] = Field(..., description="List of row objects")
    format: str = Field(default="html", description="Format for preview")
    title: str = Field(default="Document", description="Document title")
    columns: Optional[List[str]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


# ── Routes ─────────────────────────────────────────────────────────

@router.get("/formats")
def list_formats() -> Dict[str, Any]:
    """List supported document formats."""
    return {
        "success": True,
        "formats": [
            {"id": "pdf", "name": "PDF", "content_type": "application/pdf", "extension": ".pdf"},
            {"id": "excel", "name": "Excel", "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "extension": ".xlsx"},
            {"id": "markdown", "name": "Markdown", "content_type": "text/markdown", "extension": ".md"},
            {"id": "html", "name": "HTML", "content_type": "text/html", "extension": ".html"},
            {"id": "csv", "name": "CSV", "content_type": "text/csv", "extension": ".csv"},
        ],
    }


@router.post("/create")
def create_document(request: DocumentCreateRequest) -> Response:
    """Create a document from structured data. Returns the file directly."""
    service = get_document_creator()
    try:
        result = service.create(
            data=request.data,
            format=request.format,
            title=request.title,
            filename=request.filename,
            columns=request.columns,
            metadata=request.metadata,
        )
        return Response(
            content=result["content"],
            media_type=result["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{result["filename"]}"'},
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Document creation failed")
        raise HTTPException(500, f"Document creation failed: {e}")


@router.post("/preview")
def preview_document(request: DocumentPreviewRequest) -> Dict[str, Any]:
    """Preview document as base64-encoded content."""
    service = get_document_creator()
    try:
        result = service.create(
            data=request.data,
            format=request.format,
            title=request.title,
            columns=request.columns,
            metadata=request.metadata,
        )
        b64 = base64.b64encode(result["content"]).decode("ascii")
        return {
            "success": True,
            "content_type": result["content_type"],
            "filename": result["filename"],
            "record_count": result["record_count"],
            "preview_b64": b64,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Document preview failed")
        raise HTTPException(500, f"Document preview failed: {e}")
