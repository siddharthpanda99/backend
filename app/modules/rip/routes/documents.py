"""RIP Document routes — Ingest, list, get, delete documents; chunking.

Implements endpoints 11.1–11.7 from the implementation tracker.
"""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional

from common_lib.modules.rip.rip_documents.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentListResponse,
    ChunkRequest,
    ChunkResponse,
    ChunkListResponse,
)
from common_lib.modules.rip.rip_documents.service import (
    extract_text,
    chunk_document,
    Chunk,
)

router = APIRouter(prefix="/rip/documents", tags=["RIP — Documents"])


@router.post("", response_model=DocumentResponse)
async def ingest_document(payload: DocumentCreate):
    """Ingest a document into RIP.

    Extracts text, creates a DocumentRecord, and returns the result.
    """
    try:
        from common_lib.modules.rip.rip_documents.service import ingest

        result = await ingest(
            title=payload.title,
            source_type=payload.source_type,
            source_uri=payload.source_uri,
            content=payload.content,
            content_type=payload.content_type,
            metadata=payload.metadata,
            tenant_id=payload.tenant_id,
            access_level=payload.access_level,
            language=payload.language,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tenant_id: Optional[str] = Query(None),
    source_type: Optional[str] = Query(None),
):
    """List ingested documents with pagination and optional filters."""
    try:
        from common_lib.modules.rip.rip_documents.service import list_docs

        return await list_docs(
            page=page,
            page_size=page_size,
            tenant_id=tenant_id,
            source_type=source_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get a single document by ID."""
    try:
        from common_lib.modules.rip.rip_documents.service import get_doc

        doc = await get_doc(document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its associated chunks and embeddings."""
    try:
        from common_lib.modules.rip.rip_documents.service import delete_doc

        success = await delete_doc(document_id)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunk", response_model=ChunkListResponse)
async def chunk_document_endpoint(payload: ChunkRequest):
    """Chunk a document using the specified strategy.

    Supports: fixed, recursive, semantic, hierarchical, llm, late.
    """
    try:
        from common_lib.modules.rip.rip_documents.service import get_doc

        doc = await get_doc(payload.document_id)
        if doc is None:
            raise HTTPException(status_code=404, detail="Document not found")

        chunks = await chunk_document(
            text=doc.content,
            strategy=payload.strategy,
            metadata={
                "document_id": payload.document_id,
                "chunk_size": payload.chunk_size,
                "chunk_overlap": payload.chunk_overlap,
            },
        )

        chunk_responses = []
        for i, c in enumerate(chunks):
            content = getattr(c, "content", str(c))
            chunk_responses.append(
                ChunkResponse(
                    id=getattr(c, "id", f"chunk_{payload.document_id}_{i}"),
                    document_id=payload.document_id,
                    parent_id=getattr(c, "parent_id", None),
                    chunk_index=i,
                    content=content,
                    content_tokens=getattr(c, "content_tokens", len(content) // 4),
                    chunk_strategy=payload.strategy,
                    metadata=getattr(c, "metadata", {}),
                    level=getattr(c, "level", 0),
                )
            )

        return ChunkListResponse(
            items=chunk_responses,
            total=len(chunk_responses),
            document_id=payload.document_id,
            strategy=payload.strategy,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks/{document_id}", response_model=ChunkListResponse)
async def list_chunks(document_id: str):
    """List all chunks for a document."""
    try:
        from common_lib.modules.rip.rip_documents.service import get_chunks

        chunks = await get_chunks(document_id)
        return ChunkListResponse(
            items=list(chunks),
            total=len(list(chunks)),
            document_id=document_id,
            strategy="all",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies", response_model=dict)
async def list_chunking_strategies():
    """List all available chunking strategies with descriptions."""
    return {
        "strategies": [
            {"id": "fixed", "name": "Fixed-size", "description": "Fixed token-size chunks with optional overlap"},
            {"id": "recursive", "name": "Recursive Character", "description": "Natural boundary splitting (paragraphs → sentences → words)"},
            {"id": "semantic", "name": "Semantic", "description": "Embedding-similarity-based boundary detection"},
            {"id": "hierarchical", "name": "Hierarchical", "description": "Multi-level chunks (section → paragraph → sentence)"},
            {"id": "llm", "name": "LLM-based (LumberChunker)", "description": "LLM-guided semantic boundary identification"},
            {"id": "late", "name": "Late Chunking", "description": "Embed full document, then chunk the embedding space"},
        ]
    }
