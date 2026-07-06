"""
Document Vault — FastAPI Routes.

Manages document storage, metadata extraction, file tracking,
and content parsing results across the document_vault schema.

Endpoints:
    GET    /document-vault/                          — List all documents
    POST   /document-vault/                          — Upload/create document
    GET    /document-vault/{document_id}             — Get document detail
    PUT    /document-vault/{document_id}             — Update document
    DELETE /document-vault/{document_id}             — Delete document
    GET    /document-vault/{document_id}/files       — List files for document
    POST   /document-vault/{document_id}/files       — Attach file to document
    GET    /document-vault/{document_id}/metadata    — Get document metadata
    PUT    /document-vault/{document_id}/metadata    — Update metadata
    GET    /document-vault/{document_id}/content     — Get extracted content
    POST   /document-vault/{document_id}/content     — Store extracted content
    GET    /document-vault/{document_id}/content/{parser_id} — Get by parser
    GET    /document-vault/stats                     — Vault statistics
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select, func

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.document_vault.db_models import (
    DocumentVault as DocumentVaultModel,
    DocumentFiles as DocumentFilesModel,
    DocumentMetadata as DocumentMetadataModel,
    ExtractedContents as ExtractedContentsModel,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document-vault", tags=["Document Vault"])


# ── Pydantic Schemas ───────────────────────────────────────────────


class DocumentCreate(BaseModel):
    document_id: str = Field(..., description="Unique document identifier")
    filename: str = Field(..., description="Original filename")
    status: str = Field(default="pending", description="Document status")
    sources: Optional[List[str]] = Field(default=None, description="Sources array")
    tags: Optional[List[str]] = Field(default=None, description="Tags array")


class DocumentUpdate(BaseModel):
    filename: Optional[str] = None
    status: Optional[str] = None
    sources: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class FileCreate(BaseModel):
    document_id: str = Field(..., description="Parent document ID")
    filename: str = Field(..., description="File name")
    content_type: str = Field(..., description="MIME type")
    file_size: int = Field(..., description="File size in bytes")
    minio_key: str = Field(..., description="MinIO storage key")
    minio_bucket: str = Field(default="document-vault", description="MinIO bucket")
    checksum: Optional[str] = None


class MetadataUpdate(BaseModel):
    filename: Optional[str] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    page_count: Optional[int] = None
    word_count: Optional[int] = None
    language: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    custom_metadata: Optional[str] = None


class ContentStore(BaseModel):
    parser_id: str = Field(..., description="Parser identifier")
    text_content: Optional[str] = None
    json_content: Optional[str] = None
    text_length: int = Field(default=0)
    token_count: Optional[int] = None
    latency_ms: int = Field(default=0)
    confidence: Optional[float] = None
    success: bool = Field(default=True)
    error_message: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════
# Document CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("")
def list_documents(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all documents in the vault."""
    stmt = select(DocumentVaultModel)
    if status:
        stmt = stmt.where(DocumentVaultModel.status == status)
    stmt = stmt.order_by(DocumentVaultModel.created_at.desc())
    stmt = stmt.offset(offset).limit(limit)
    results = session.exec(stmt).all()
    total = session.exec(
        select(func.count()).select_from(DocumentVaultModel)
    ).one()
    return {
        "success": True,
        "data": [_vault_to_dict(r) for r in results],
        "total": total,
    }


@router.post("", status_code=201)
def create_document(
    request: DocumentCreate,
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create a new document vault entry."""
    # Check for duplicate document_id
    existing = session.exec(
        select(DocumentVaultModel).where(
            DocumentVaultModel.document_id == request.document_id
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Document '{request.document_id}' already exists",
        )
    record = DocumentVaultModel(
        document_id=request.document_id,
        filename=request.filename,
        status=request.status,
        sources=json.dumps(request.sources) if request.sources else None,
        tags=json.dumps(request.tags) if request.tags else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return {"success": True, "data": _vault_to_dict(record)}


@router.get("/{document_id}")
def get_document(
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get a document by ID."""
    record = _get_vault_or_404(session, document_id)
    return {"success": True, "data": _vault_to_dict(record)}


@router.put("/{document_id}")
def update_document(
    request: DocumentUpdate,
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Update a document vault entry."""
    record = _get_vault_or_404(session, document_id)
    update_data = request.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(record, key, value)
    record.updated_at = datetime.utcnow()
    session.add(record)
    session.commit()
    session.refresh(record)
    return {"success": True, "data": _vault_to_dict(record)}


@router.delete("/{document_id}")
def delete_document(
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Delete a document and all associated files, metadata, and content."""
    record = _get_vault_or_404(session, document_id)
    # Delete associated records
    files = session.exec(
        select(DocumentFilesModel).where(
            DocumentFilesModel.document_id == document_id
        )
    ).all()
    for f in files:
        session.delete(f)

    meta = session.exec(
        select(DocumentMetadataModel).where(
            DocumentMetadataModel.document_id == document_id
        )
    ).first()
    if meta:
        session.delete(meta)

    contents = session.exec(
        select(ExtractedContentsModel).where(
            ExtractedContentsModel.document_id == document_id
        )
    ).all()
    for c in contents:
        session.delete(c)

    session.delete(record)
    session.commit()
    return {"success": True, "message": f"Document '{document_id}' deleted"}


# ═══════════════════════════════════════════════════════════════════
# Files
# ═══════════════════════════════════════════════════════════════════


@router.get("/{document_id}/files")
def list_files(
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all files attached to a document."""
    _get_vault_or_404(session, document_id)
    files = session.exec(
        select(DocumentFilesModel).where(
            DocumentFilesModel.document_id == document_id
        )
    ).all()
    return {
        "success": True,
        "data": [_file_to_dict(f) for f in files],
        "total": len(files),
    }


@router.post("/{document_id}/files", status_code=201)
def add_file(
    request: FileCreate,
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Attach a file to a document."""
    _get_vault_or_404(session, document_id)
    record = DocumentFilesModel(
        document_id=document_id,
        filename=request.filename,
        content_type=request.content_type,
        file_size=request.file_size,
        minio_key=request.minio_key,
        minio_bucket=request.minio_bucket,
        checksum=request.checksum,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return {"success": True, "data": _file_to_dict(record)}


# ═══════════════════════════════════════════════════════════════════
# Metadata
# ═══════════════════════════════════════════════════════════════════


@router.get("/{document_id}/metadata")
def get_metadata(
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get metadata for a document."""
    _get_vault_or_404(session, document_id)
    meta = session.exec(
        select(DocumentMetadataModel).where(
            DocumentMetadataModel.document_id == document_id
        )
    ).first()
    if not meta:
        raise HTTPException(
            status_code=404,
            detail=f"No metadata found for document '{document_id}'",
        )
    return {"success": True, "data": _metadata_to_dict(meta)}


@router.put("/{document_id}/metadata")
def upsert_metadata(
    request: MetadataUpdate,
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Create or update metadata for a document."""
    _get_vault_or_404(session, document_id)
    meta = session.exec(
        select(DocumentMetadataModel).where(
            DocumentMetadataModel.document_id == document_id
        )
    ).first()

    update_data = request.model_dump(exclude_none=True)
    if meta:
        for key, value in update_data.items():
            setattr(meta, key, value)
        meta.updated_at = datetime.utcnow()
    else:
        # Create metadata with document_id as the document reference
        vault = _get_vault_or_404(session, document_id)
        meta = DocumentMetadataModel(
            document_id=document_id,
            filename=update_data.get("filename", vault.filename),
            file_type=update_data.get("file_type", ""),
            mime_type=update_data.get("mime_type", ""),
            file_size=update_data.get("file_size", 0),
            page_count=update_data.get("page_count"),
            word_count=update_data.get("word_count"),
            language=update_data.get("language"),
            title=update_data.get("title"),
            author=update_data.get("author"),
            custom_metadata=update_data.get("custom_metadata"),
        )

    session.add(meta)
    session.commit()
    session.refresh(meta)
    return {"success": True, "data": _metadata_to_dict(meta)}


# ═══════════════════════════════════════════════════════════════════
# Extracted Content
# ═══════════════════════════════════════════════════════════════════


@router.get("/{document_id}/content")
def list_contents(
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """List all extracted content records for a document."""
    _get_vault_or_404(session, document_id)
    contents = session.exec(
        select(ExtractedContentsModel).where(
            ExtractedContentsModel.document_id == document_id
        )
    ).all()
    return {
        "success": True,
        "data": [_content_to_dict(c) for c in contents],
        "total": len(contents),
    }


@router.post("/{document_id}/content", status_code=201)
def store_content(
    request: ContentStore,
    document_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Store extracted content for a document."""
    _get_vault_or_404(session, document_id)
    record = ExtractedContentsModel(
        document_id=document_id,
        parser_id=request.parser_id,
        text_content=request.text_content,
        json_content=request.json_content,
        text_length=request.text_length,
        token_count=request.token_count,
        latency_ms=request.latency_ms,
        confidence=request.confidence,
        success=request.success,
        error_message=request.error_message,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return {"success": True, "data": _content_to_dict(record)}


@router.get("/{document_id}/content/{parser_id}")
def get_content_by_parser(
    document_id: str = Path(...),
    parser_id: str = Path(...),
    session: Session = Depends(get_session),
) -> Dict[str, Any]:
    """Get extracted content by document and parser ID."""
    _get_vault_or_404(session, document_id)
    record = session.exec(
        select(ExtractedContentsModel).where(
            ExtractedContentsModel.document_id == document_id,
            ExtractedContentsModel.parser_id == parser_id,
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No content for parser '{parser_id}' on document '{document_id}'",
        )
    return {"success": True, "data": _content_to_dict(record)}


# ── Helpers ────────────────────────────────────────────────────────


def _get_vault_or_404(session: Session, document_id: str) -> DocumentVaultModel:
    record = session.exec(
        select(DocumentVaultModel).where(
            DocumentVaultModel.document_id == document_id
        )
    ).first()
    if not record:
        raise HTTPException(
            status_code=404, detail=f"Document '{document_id}' not found"
        )
    return record


def _vault_to_dict(r: DocumentVaultModel) -> Dict[str, Any]:
    sources = None
    if r.sources:
        try:
            sources = json.loads(r.sources)
        except (json.JSONDecodeError, TypeError):
            sources = r.sources
    tags = None
    if r.tags:
        try:
            tags = json.loads(r.tags)
        except (json.JSONDecodeError, TypeError):
            tags = r.tags
    return {
        "id": r.id,
        "document_id": r.document_id,
        "filename": r.filename,
        "status": r.status,
        "sources": sources,
        "tags": tags,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _file_to_dict(r: DocumentFilesModel) -> Dict[str, Any]:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "filename": r.filename,
        "content_type": r.content_type,
        "file_size": r.file_size,
        "minio_key": r.minio_key,
        "minio_bucket": r.minio_bucket,
        "checksum": r.checksum,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _metadata_to_dict(r: DocumentMetadataModel) -> Dict[str, Any]:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "filename": r.filename,
        "file_type": r.file_type,
        "mime_type": r.mime_type,
        "file_size": r.file_size,
        "page_count": r.page_count,
        "word_count": r.word_count,
        "language": r.language,
        "title": r.title,
        "author": r.author,
        "custom_metadata": r.custom_metadata,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


def _content_to_dict(r: ExtractedContentsModel) -> Dict[str, Any]:
    return {
        "id": r.id,
        "document_id": r.document_id,
        "parser_id": r.parser_id,
        "text_content": r.text_content[:500] if r.text_content else None,
        "json_content": r.json_content,
        "text_length": r.text_length,
        "token_count": r.token_count,
        "latency_ms": r.latency_ms,
        "confidence": r.confidence,
        "success": r.success,
        "error_message": r.error_message,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
