"""Chunks CRUD and editor API routes — thin routers delegating to common_lib.

Endpoints: list, create, get, update, delete chunks; split, merge, similar,
confidence override, soft-delete, and children queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from sqlmodel import Session

from app.modules.knowledge.dependencies import get_knowledge_engine_service
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.knowledge_engine.models.db_records import KnowledgeChunkRecord
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService
from common_lib.modules.knowledge_engine.services.chunk_repository import (
    ChunkRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Knowledge Chunks"])

# ── Shared instance ──────────────────────────────────────────

_chunk_repo = ChunkRepository()

# ── Helper ───────────────────────────────────────────────────


def _record_to_dict(rec: KnowledgeChunkRecord) -> dict[str, Any]:
    return {
        "chunk_id": rec.chunk_id,
        "content": rec.content,
        "source_id": rec.source_id,
        "source_type": rec.source_type,
        "domain": rec.domain,
        "classification": rec.classification,
        "job_id": rec.job_id,
        "metadata": rec.metadata_json or {},
        "entity_mentions": rec.entity_mentions or [],
        "topics": rec.topics or [],
        "embedding": rec.embedding,
        "created_at": rec.created_at.isoformat() if rec.created_at else None,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


# ── Schemas ──────────────────────────────────────────────────


class ChunkCreateRequest(BaseModel):
    content: str = Field(..., description="Chunk text content", min_length=1)
    source_id: str = Field(..., description="Source document identifier")
    source_type: str = Field("text", description="Source content type")
    metadata: dict[str, Any] = Field(default_factory=dict)
    entity_mentions: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    domain: str = Field("", description="Knowledge domain")
    classification: str = Field("public", description="RBAC classification")


class ChunkUpdateRequest(BaseModel):
    content: Optional[str] = Field(None, description="Updated content")
    metadata: Optional[dict[str, Any]] = Field(None, description="Updated metadata")
    entity_mentions: Optional[list[str]] = Field(None)
    topics: Optional[list[str]] = Field(None)
    domain: Optional[str] = Field(None)
    classification: Optional[str] = Field(None)


class ChunkSplitRequest(BaseModel):
    split_point: int = Field(
        ..., description="Character index where the split occurs", ge=0
    )
    second_content: str = Field(
        ..., description="Content for the second (new) child chunk", min_length=1
    )
    re_embed: bool = Field(True, description="Whether to regenerate embeddings")


class ChunkMergeRequest(BaseModel):
    chunk_ids: list[str] = Field(
        ..., description="Chunk UUIDs to merge (min 2)", min_length=2
    )
    re_embed: bool = Field(True)
    merge_strategy: str = Field(
        "concat", description="concat or newline", pattern="^(concat|newline)$"
    )


class ChunkSimilarRequest(BaseModel):
    chunk_id: str = Field(..., description="Reference chunk UUID")
    top_k: int = Field(10, ge=1, le=50)
    min_score: float = Field(0.0, ge=0.0, le=1.0)


class ChunkConfidenceRequest(BaseModel):
    confidence: float = Field(..., ge=0.0, le=1.0, description="0.0 to 1.0")


class ChunkEditRequest(BaseModel):
    content: str = Field(..., min_length=1, description="New chunk content")
    re_embed: bool = Field(True)


# ── CRUD ─────────────────────────────────────────────────────


@router.get("/chunks")
async def list_chunks(
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    records, total = _chunk_repo.filter_by_source(
        session=session,
        source_id=source_id,
        domain=domain,
        offset=offset,
        limit=limit,
    )
    return {
        "success": True,
        "data": {
            "chunks": [_record_to_dict(r) for r in records],
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        "message": f"Found {total} chunks",
    }


@router.post("/chunks", status_code=201)
async def create_chunk(
    request: ChunkCreateRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        chunk_id = str(uuid4())
        embedding = None
        try:
            embed_result = await service.embed(text=request.content)
            embedding = embed_result.dense if hasattr(embed_result, "dense") else None
        except Exception:
            pass

        record = _chunk_repo.create_chunk(
            session=session,
            chunk_id=chunk_id,
            content=request.content,
            source_id=request.source_id,
            source_type=request.source_type,
            domain=request.domain,
            classification=request.classification,
            metadata_json=request.metadata,
            entity_mentions=request.entity_mentions,
            topics=request.topics,
            embedding=embedding,
        )
        return {
            "success": True,
            "data": _record_to_dict(record),
            "message": f"Chunk {chunk_id[:8]} created",
        }
    except Exception as e:
        logger.exception("Failed to create chunk")
        raise HTTPException(status_code=500, detail=f"Failed to create chunk: {str(e)}")


@router.get("/chunks/{chunk_id}")
async def get_chunk(
    chunk_id: str = Path(..., description="Chunk UUID"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        record = _chunk_repo.get_by_chunk_id_or_raise(
            session, chunk_id, detail=f"Chunk {chunk_id} not found"
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "success": True,
        "data": _record_to_dict(record),
        "message": "Chunk retrieved",
    }


@router.put("/chunks/{chunk_id}")
async def update_chunk(
    request: ChunkUpdateRequest,
    chunk_id: str = Path(..., description="Chunk UUID to update"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        record = _chunk_repo.get_by_chunk_id_or_raise(
            session, chunk_id, detail=f"Chunk {chunk_id} not found"
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    update_data = request.model_dump(exclude_none=True)
    field_map: dict[str, str] = {
        "content": "content",
        "metadata": "metadata_json",
        "entity_mentions": "entity_mentions",
        "topics": "topics",
        "domain": "domain",
        "classification": "classification",
    }
    mapped: dict[str, Any] = {}
    for request_field, db_field in field_map.items():
        if request_field in update_data:
            mapped[db_field] = update_data[request_field]

    record = _chunk_repo.update_from_dict(session, record, mapped)
    return {
        "success": True,
        "data": _record_to_dict(record),
        "message": f"Chunk {chunk_id[:8]} updated",
    }


@router.delete("/chunks/{chunk_id}")
async def delete_chunk(
    chunk_id: str = Path(..., description="Chunk UUID to delete"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        _chunk_repo.delete_by_chunk_id_or_raise(session, chunk_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")
    return {
        "success": True,
        "data": {"chunk_id": chunk_id},
        "message": f"Chunk {chunk_id[:8]} deleted",
    }


# ── Editor ───────────────────────────────────────────────────


_chunk_editor_svc: Optional[Any] = None


def _get_chunk_editor_svc(service: KnowledgeEngineService) -> Any:
    global _chunk_editor_svc
    if _chunk_editor_svc is None:
        from common_lib.modules.knowledge_engine.services.chunk_editor_service import (
            ChunkEditorService,
        )

        _chunk_editor_svc = ChunkEditorService(
            embedding_fn=lambda text: service.embed(text=text)
        )
    return _chunk_editor_svc


@router.post("/chunks/{chunk_id}/split", status_code=201)
async def split_chunk(
    request: ChunkSplitRequest,
    chunk_id: str = Path(..., description="Chunk UUID to split"),
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        editor = _get_chunk_editor_svc(service)
        child_a, child_b = await editor.split_chunk(
            session=session,
            chunk_id=chunk_id,
            split_point=request.split_point,
            second_content=request.second_content,
            re_embed=request.re_embed,
        )
        return {
            "success": True,
            "data": {
                "children": [_record_to_dict(child_a), _record_to_dict(child_b)],
                "parent_id": chunk_id,
            },
            "message": "Chunk split into 2 children",
        }
    except Exception as e:
        logger.exception("Chunk split failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunks/merge", status_code=201)
async def merge_chunks(
    request: ChunkMergeRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        editor = _get_chunk_editor_svc(service)
        merged = await editor.merge_chunks(
            session=session,
            chunk_ids=request.chunk_ids,
            re_embed=request.re_embed,
            merge_strategy=request.merge_strategy,
        )
        return {
            "success": True,
            "data": {
                "chunk": _record_to_dict(merged),
                "merged_ids": request.chunk_ids,
                "strategy": request.merge_strategy,
            },
            "message": f"Merged {len(request.chunk_ids)} chunks into one",
        }
    except Exception as e:
        logger.exception("Chunk merge failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks/{chunk_id}/similar")
async def find_similar_chunks(
    chunk_id: str = Path(..., description="Reference chunk UUID"),
    top_k: int = Query(10, ge=1, le=50),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        editor = _get_chunk_editor_svc(service)
        results = editor.find_similar(
            session=session,
            chunk_id=chunk_id,
            top_k=top_k,
            min_score=min_score,
        )
        return {
            "success": True,
            "data": {
                "results": results,
                "reference_chunk_id": chunk_id,
                "count": len(results),
            },
            "message": f"Found {len(results)} similar chunks",
        }
    except Exception as e:
        logger.exception("Similar chunks query failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/chunks/{chunk_id}/confidence")
async def override_chunk_confidence(
    request: ChunkConfidenceRequest,
    chunk_id: str = Path(..., description="Chunk UUID"),
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        editor = _get_chunk_editor_svc(service)
        record = editor.override_confidence(
            session=session, chunk_id=chunk_id, confidence=request.confidence
        )
        return {
            "success": True,
            "data": _record_to_dict(record),
            "message": f"Confidence set to {request.confidence}",
        }
    except Exception as e:
        logger.exception("Confidence override failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chunks/{chunk_id}/soft-delete")
async def soft_delete_chunk(
    chunk_id: str = Path(..., description="Chunk UUID to soft-delete"),
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        editor = _get_chunk_editor_svc(service)
        result = editor.soft_delete(session=session, chunk_id=chunk_id)
        return {
            "success": True,
            "data": result,
            "message": f"Chunk {chunk_id[:8]} soft-deleted",
        }
    except Exception as e:
        logger.exception("Soft delete failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chunks/{chunk_id}/children")
async def get_chunk_children(
    chunk_id: str = Path(..., description="Parent chunk UUID"),
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        editor = _get_chunk_editor_svc(service)
        children = editor.get_children(session=session, chunk_id=chunk_id)
        return {
            "success": True,
            "data": {
                "children": children,
                "parent_id": chunk_id,
                "count": len(children),
            },
            "message": f"Found {len(children)} child chunks",
        }
    except Exception as e:
        logger.exception("Get children failed")
        raise HTTPException(status_code=500, detail=str(e))


__all__ = ["router"]
