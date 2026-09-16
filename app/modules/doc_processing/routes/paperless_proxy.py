"""Paperless-ngx REST proxy router for platform API consumers (W5-L03).

Exposes client-facing document queries, metadata, thumbnail previews,
and multipart file upload without exposing the internal Docker network.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile, status

from common_lib.modules.doc_processing.config.flags import (
    PAPERLESS_INTEGRATION_ENABLED,
    is_enabled,
)
from common_lib.modules.doc_processing.paperless_client.client import (
    PaperlessApiError,
    get_paperless_client,
)
from common_lib.modules.doc_processing.paperless_client.models import (
    PaperlessDocument,
    PaperlessDocumentListResponse,
)

router = APIRouter(prefix="/paperless", tags=["Paperless DMS Proxy"])


def _check_enabled():
    if not is_enabled(PAPERLESS_INTEGRATION_ENABLED):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Paperless integration is currently disabled via feature flag.",
        )


@router.get(
    "/documents",
    response_model=PaperlessDocumentListResponse,
    summary="List Paperless Documents",
)
async def list_paperless_documents(
    query: Optional[str] = Query(default=None, description="Search term"),
    correspondent: Optional[int] = Query(default=None, description="Filter by correspondent ID"),
    document_type: Optional[int] = Query(default=None, description="Filter by document type ID"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
):
    """Query documents from Paperless-ngx."""
    _check_enabled()
    client = get_paperless_client()
    try:
        return await client.list_documents(
            query=query,
            correspondent=correspondent,
            document_type=document_type,
            page=page,
            page_size=page_size,
        )
    except PaperlessApiError as exc:
        raise HTTPException(status_code=exc.status_code or 500, detail=str(exc))


@router.get(
    "/documents/{document_id}",
    response_model=PaperlessDocument,
    summary="Get Document Details",
)
async def get_paperless_document(document_id: int):
    """Fetch complete metadata for a document."""
    _check_enabled()
    client = get_paperless_client()
    try:
        return await client.get_document(document_id)
    except PaperlessApiError as exc:
        raise HTTPException(status_code=exc.status_code or 404, detail=str(exc))


@router.get(
    "/documents/{document_id}/preview",
    summary="Get Document Thumbnail Preview",
)
async def get_document_preview(document_id: int):
    """Stream binary thumbnail image of document first page."""
    _check_enabled()
    client = get_paperless_client()
    try:
        image_bytes = await client.download_preview(document_id)
        return Response(content=image_bytes, media_type="image/png")
    except PaperlessApiError as exc:
        raise HTTPException(status_code=exc.status_code or 404, detail=str(exc))


@router.post(
    "/documents/upload",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload Document to Paperless",
)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    correspondent: Optional[int] = Form(default=None),
    document_type: Optional[int] = Form(default=None),
):
    """Upload a file to Paperless-ngx for intake & processing."""
    _check_enabled()
    client = get_paperless_client()
    content = await file.read()
    try:
        task_id = await client.post_document(
            file_path_or_bytes=content,
            file_name=file.filename or "document.pdf",
            title=title,
            correspondent=correspondent,
            document_type=document_type,
        )
        return {
            "status": "QUEUED",
            "task_id": task_id,
            "filename": file.filename,
        }
    except PaperlessApiError as exc:
        raise HTTPException(status_code=exc.status_code or 500, detail=str(exc))
