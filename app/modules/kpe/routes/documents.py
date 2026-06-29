"""KPE Document Routes — Thin FastAPI wrappers delegating to common_lib.

All CRUD logic lives in common_lib.modules.kpe.services.DocumentService.
"""

from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from common_lib.modules.kpe.schemas.document import DocumentCreate, DocumentResponse
from common_lib.modules.kpe.services.document_service import DocumentService

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton service instance
_doc_service = DocumentService()


@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source_type: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
):
    """List documents with optional filters."""
    try:
        return await _doc_service.list_documents(
            skip=skip, limit=limit, source_type=source_type, tenant_id=tenant_id
        )
    except Exception as e:
        logger.error("Failed to list documents: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get a document by ID."""
    try:
        doc = await _doc_service.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=DocumentResponse, status_code=201)
async def create_document(payload: DocumentCreate):
    """Create a new document."""
    try:
        return await _doc_service.create_document(payload)
    except Exception as e:
        logger.error("Failed to create document: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """Delete a document and its related data."""
    try:
        deleted = await _doc_service.delete_document(document_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete document %s: %s", document_id, e)
        raise HTTPException(status_code=500, detail=str(e))
