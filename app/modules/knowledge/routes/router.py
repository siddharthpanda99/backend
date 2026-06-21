"""
Knowledge Engine — API Routes.

FastAPI route definitions for the Knowledge Engine at /api/v1/knowledge/.

Core endpoints remain here; domain-specific subsets are delegated to
sub-routers (chunks, security, conflicts, quality, learning).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sqlmodel import Session, func, select

from app.modules.knowledge.dependencies import get_knowledge_engine_service
from app.modules.knowledge.routes.instance_routes import router as instance_router
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.data_storage.database.repository import NotFoundError
from common_lib.modules.knowledge_engine.config import KnowledgeEngineError
from common_lib.modules.knowledge_engine.models.db_records import KnowledgeChunkRecord
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService
from common_lib.modules.knowledge_engine.services.chunk_repository import (
    ChunkRepository,
)
from common_lib.modules.knowledge_engine.services.community_service import (
    CommunityService,
)
from common_lib.modules.knowledge_engine.services.analytics_service import (
    AnalyticsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Engine"])

# ── Service instances ──────────────────────────────────────────

_chunk_repo = ChunkRepository()
_community_svc = CommunityService()

# ── Request / Response Schemas ───────────────────────────────


class RetrieveRequest(BaseModel):
    query: str = Field(..., description="Natural language query", min_length=1)
    top_k: int = Field(100, description="Number of initial candidates", ge=1, le=500)
    token_budget: Optional[int] = Field(
        None,
        description="Token budget for context (reserved, currently unused by engine)",
        ge=1000,
    )


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query", min_length=1)
    top_k: int = Field(20, description="Maximum results", ge=1, le=100)
    filters: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata filters"
    )


class QueryUnderstandRequest(BaseModel):
    query: str = Field(..., description="Query to analyze", min_length=1)
    context: Optional[dict[str, Any]] = Field(
        None, description="Optional context (domain, tenant_id, etc.)"
    )


class ChunkRequest(BaseModel):
    text: str = Field(..., description="Text to chunk", min_length=1)
    source_id: str = Field(..., description="Source document identifier")
    content_type: str = Field(
        "text", description="Content type (text, code, markdown, qa)"
    )
    strategy: str = Field(
        "auto", description="Chunking strategy (auto, semantic, code, etc.)"
    )


class EmbedRequest(BaseModel):
    text: str = Field(..., description="Text to embed", min_length=1)
    model_id: str = Field("BAAI/bge-m3", description="Embedding model ID")


class EmbedBatchRequest(BaseModel):
    texts: list[str] = Field(
        ..., description="Texts to embed", min_length=1, max_length=100
    )
    model_id: str = Field("BAAI/bge-m3", description="Embedding model ID")


class CompressRequest(BaseModel):
    vector: list[float] = Field(..., description="Float32 vector to compress")
    bits: int = Field(8, description="Quantization bits (4 or 8)")


class DecompressRequest(BaseModel):
    compressed: str = Field(..., description="Base64-encoded compressed bytes")
    bits: int = Field(8, description="Quantization bits used during compression")
    dimensions: int = Field(..., description="Original vector dimensions")


class ConfigUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(..., description="Config fields to update")


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/retrieve")
async def retrieve(
    request: RetrieveRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        result = await service.retrieve(query=request.query, top_k=request.top_k)
        if result is None:
            return {
                "success": False,
                "data": {},
                "message": "Retrieval returned no results (pipeline may be uninitialized)",
            }
        return {
            "success": True,
            "data": result,
            "message": f"Retrieved context for query: {request.query[:50]}...",
        }
    except KnowledgeEngineError as e:
        logger.error(f"Retrieval failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected retrieval error")
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.post("/search")
async def search(
    request: SearchRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        results = await service.search(
            query=request.query, filters=request.filters, top_k=request.top_k
        )
        return {
            "success": True,
            "data": {"results": results, "count": len(results)},
            "message": f"Found {len(results)} results",
        }
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/query-understand")
async def query_understand(request: QueryUnderstandRequest) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.retrieval.query_understanding import (
            QueryUnderstanding,
        )

        qu = QueryUnderstanding()
        plan = await qu.analyze(query=request.query, context=request.context or {})
        return {
            "success": True,
            "data": plan.model_dump(),
            "message": "Query analyzed",
        }
    except Exception as e:
        logger.exception("Query understanding failed")
        raise HTTPException(status_code=500, detail=f"Query analysis failed: {str(e)}")


@router.post("/chunk")
async def chunk_document(
    request: ChunkRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        metadata = {
            "source_id": request.source_id,
            "content_type": request.content_type,
        }
        if request.strategy != "auto":
            metadata["strategy"] = request.strategy
        chunks = await service.chunk(text=request.text, metadata=metadata)
        return {
            "success": True,
            "data": {
                "chunks": [c.model_dump() for c in chunks],
                "count": len(chunks),
                "strategy": request.strategy,
            },
            "message": f"Text split into {len(chunks)} chunks",
        }
    except KnowledgeEngineError as e:
        logger.error(f"Chunking failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected chunking error")
        raise HTTPException(status_code=500, detail=f"Chunking failed: {str(e)}")


@router.post("/embed")
async def embed_text(
    request: EmbedRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        result = await service.embed(text=request.text, model_id=request.model_id)
        return {
            "success": True,
            "data": result.model_dump(),
            "message": f"Embedded text with {request.model_id}",
        }
    except KnowledgeEngineError as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected embedding error")
        raise HTTPException(status_code=500, detail=f"Embedding failed: {str(e)}")


@router.post("/embed/batch")
async def embed_batch(
    request: EmbedBatchRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        result = await service.embed_batch(
            texts=request.texts, model_id=request.model_id
        )
        return {
            "success": True,
            "data": result.model_dump(),
            "message": f"Embedded {len(request.texts)} texts with {request.model_id}",
        }
    except KnowledgeEngineError as e:
        logger.error(f"Batch embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected batch embedding error")
        raise HTTPException(status_code=500, detail=f"Batch embedding failed: {str(e)}")


@router.get("/models")
async def list_models(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        models = service.list_models()
        default = service.get_default_model()
        return {
            "success": True,
            "data": {"models": models, "default": default, "total": len(models)},
            "message": f"{len(models)} models available",
        }
    except Exception as e:
        logger.exception("Failed to list models")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/config")
async def get_config(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        config = service.get_config()
        return {"success": True, "data": config, "message": "Configuration retrieved"}
    except Exception as e:
        logger.exception("Failed to get config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/config")
async def update_config(
    request: ConfigUpdateRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        config = service.update_config(request.updates)
        return {"success": True, "data": config, "message": "Configuration updated"}
    except Exception as e:
        logger.exception("Failed to update config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.get("/health")
async def health_check(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        status = await service.health()
        return {
            "success": True,
            "data": status,
            "message": "Knowledge Engine is healthy"
            if status.get("initialized")
            else "Knowledge Engine is not fully initialized",
        }
    except Exception as e:
        logger.exception("Health check failed")
        return {
            "success": False,
            "data": {"module": "knowledge_engine", "error": str(e)},
            "message": "Health check failed",
        }


@router.post("/compress")
async def compress_vector(
    request: CompressRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        import base64

        compressed = service.compress_vector(request.vector, bits=request.bits)
        return {
            "success": True,
            "data": {
                "compressed": base64.b64encode(compressed).decode("utf-8"),
                "original_dimensions": len(request.vector),
                "compressed_bytes": len(compressed),
                "bits": request.bits,
            },
            "message": f"Vector compressed ({len(request.vector)} dims → {len(compressed)} bytes)",
        }
    except Exception as e:
        logger.exception("Compression failed")
        raise HTTPException(status_code=500, detail=f"Compression failed: {str(e)}")


@router.post("/decompress")
async def decompress_vector(
    request: DecompressRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    try:
        import base64

        compressed_bytes = base64.b64decode(request.compressed)
        vector = service.decompress_vector(compressed_bytes, bits=request.bits)
        return {
            "success": True,
            "data": {
                "vector": vector[:10],
                "dimensions": len(vector),
                "bits": request.bits,
            },
            "message": f"Vector decompressed ({len(vector)} dims)",
        }
    except Exception as e:
        logger.exception("Decompression failed")
        raise HTTPException(status_code=500, detail=f"Decompression failed: {str(e)}")


# ── Ingest Schemas ────────────────────────────────────────────


class IngestDocumentRequest(BaseModel):
    source_id: str = Field(..., description="Source connector identifier")
    content: str = Field(..., description="Document content text")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata (title, author, content_type, etc.)",
    )
    strategy: str = Field("auto", description="Chunking strategy")


class ValidateRequest(BaseModel):
    chunks: list[str] = Field(
        ..., description="List of chunk IDs or contents to validate", min_length=1
    )
    query: str = Field("", description="Original query for context")
    query_type: str = Field(
        "factual", description="Type of query for validation thresholds"
    )


# ═══════════════════════════════════════════════════════════════════
# POST /ingest/document
# ═══════════════════════════════════════════════════════════════════


@router.post("/ingest/document")
async def ingest_document(
    request: IngestDocumentRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        metadata = {
            "source_id": request.source_id,
            "content_type": request.metadata.get("content_type", "text"),
            "title": request.metadata.get("title", ""),
            "author": request.metadata.get("author", ""),
        }
        if request.strategy != "auto":
            metadata["strategy"] = request.strategy

        chunks = await service.chunk(text=request.content, metadata=metadata)

        job_id = str(uuid4())
        stored_ids = []
        for chunk in chunks:
            chunk_data = chunk.model_dump() if hasattr(chunk, "model_dump") else {}
            cid = str(chunk_data.get("chunk_id", uuid4()))
            _chunk_repo.create_chunk(
                session=session,
                chunk_id=cid,
                content=chunk_data.get("content", ""),
                source_id=request.source_id,
                source_type=metadata.get("content_type", "text"),
                domain=chunk_data.get("domain", ""),
                job_id=job_id,
                metadata_json=request.metadata,
                entity_mentions=chunk_data.get("entity_mentions", []),
                topics=chunk_data.get("topics", []),
            )
            stored_ids.append(cid)

        from common_lib.modules.knowledge_hub.services.conflict_service import (
            KBConflictService,
        )

        conflict_svc = KBConflictService()
        conflicts_detected = 0
        for cid in stored_ids:
            chunk_record = _chunk_repo.get_by_chunk_id(session, cid)
            if chunk_record:
                new_conflicts = conflict_svc.scan_on_ingest(
                    session=session, new_chunk=chunk_record
                )
                conflicts_detected += len(new_conflicts)

        return {
            "success": True,
            "data": {
                "job_id": job_id,
                "source_id": request.source_id,
                "chunks_created": len(stored_ids),
                "chunk_ids": stored_ids,
                "conflicts_detected": conflicts_detected,
            },
            "message": (
                f"Ingested document: {len(stored_ids)} chunks created"
                + (
                    f" ({conflicts_detected} conflict{'s' if conflicts_detected != 1 else ''} detected)"
                    if conflicts_detected
                    else ""
                )
            ),
        }
    except KnowledgeEngineError as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected ingestion error")
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# SSE Streaming Retrieve
# ═══════════════════════════════════════════════════════════════════


@router.post("/retrieve/stream")
async def retrieve_stream(
    request: RetrieveRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> StreamingResponse:
    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            yield _sse_event(
                "query_understanding", {"status": "analyzing", "query": request.query}
            )

            from common_lib.modules.knowledge_engine.retrieval.query_understanding import (
                QueryUnderstanding,
            )

            qu = QueryUnderstanding()
            plan = await qu.analyze(query=request.query, context={})
            plan_data = plan.model_dump() if hasattr(plan, "model_dump") else plan

            yield _sse_event(
                "query_understanding",
                {
                    "status": "complete",
                    "query_type": plan_data.get("query_type", "unknown"),
                    "entities": plan_data.get("entities", []),
                },
            )

            yield _sse_event(
                "hybrid_search", {"status": "searching", "top_k": request.top_k}
            )

            result = await service.retrieve(query=request.query, top_k=request.top_k)
            if result is None:
                yield _sse_event("error", {"message": "Retrieval returned no results"})
                return

            yield _sse_event(
                "hybrid_search",
                {
                    "status": "complete",
                    "chunks_count": len(result.get("knowledge_chunks", [])),
                },
            )

            yield _sse_event("complete", {"status": "success", "result": result})
        except Exception as e:
            logger.exception("Streaming retrieval failed")
            yield _sse_event("error", {"message": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ═══════════════════════════════════════════════════════════════════
# POST /validate
# ═══════════════════════════════════════════════════════════════════


@router.post("/validate")
async def validate_knowledge(
    request: ValidateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        from common_lib.modules.knowledge_engine.validation.validator import (
            KnowledgeValidator,
        )

        validator = KnowledgeValidator()

        from common_lib.modules.knowledge_engine.models.validation import (
            ValidationReport,
        )

        pseudo_chunks = []
        for item in request.chunks:
            record = _chunk_repo.get_by_chunk_id(session, item)
            if record:
                pseudo_chunks.append(
                    {
                        "chunk_id": record.chunk_id,
                        "content": record.content,
                        "source_id": record.source_id,
                        "source_type": record.source_type,
                        "domain": record.domain,
                        "metadata": record.metadata_json or {},
                        "entity_mentions": record.entity_mentions or [],
                        "topics": record.topics or [],
                    }
                )
            else:
                pseudo_chunks.append(
                    {
                        "chunk_id": str(uuid4()),
                        "content": item,
                        "source_id": "validation_input",
                        "source_type": "text",
                    }
                )

        validation = await validator.validate(
            chunks=pseudo_chunks,
            query=request.query or "",
            query_type=request.query_type,
        )
        report = validation.model_dump() if hasattr(validation, "model_dump") else {}

        return {"success": True, "data": report, "message": "Validation complete"}
    except Exception as e:
        logger.exception("Validation failed")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# GET /communities
# ═══════════════════════════════════════════════════════════════════


@router.get("/communities")
async def list_communities(
    min_members: int = Query(1, ge=1, description="Minimum community size"),
    limit: int = Query(20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        data = _community_svc.list_communities(session, min_members=min_members)
        return {
            "success": True,
            "data": data,
            "message": f"Found {data['total']} communities",
        }
    except Exception as e:
        logger.exception("Failed to list communities")
        raise HTTPException(
            status_code=500, detail=f"Failed to list communities: {str(e)}"
        )


@router.get("/communities/{community_id}")
async def get_community(
    community_id: str = Path(..., description="Community identifier"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        detail = _community_svc.get_community(session, community_id)
        if detail is None:
            raise HTTPException(
                status_code=404, detail=f"Community {community_id} not found"
            )
        return {
            "success": True,
            "data": detail,
            "message": f"Community {community_id} details retrieved",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get community {community_id}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get community: {str(e)}"
        )


# Include self-learning instance CRUD routes
router.include_router(instance_router)

# ═══════════════════════════════════════════════════════════════════
# Analytics Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/analytics/overview")
async def analytics_overview(
    days: Optional[int] = Query(
        None, ge=1, le=365, description="Lookback days for recent metrics"
    ),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    data = AnalyticsService.overview(session=session, days=days)
    return {
        "success": True,
        "data": data,
        "message": f"Overview: {data['total_chunks']} chunks, {data['total_projects']} projects",
    }


@router.get("/analytics/time-series")
async def analytics_time_series(
    metric: str = Query(
        "chunks", description="Metric: chunks, projects, packets, activity"
    ),
    days: int = Query(30, ge=1, le=365),
    granularity: str = Query("day", description="day or week"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    if metric not in ("chunks", "projects", "packets", "activity"):
        raise HTTPException(
            status_code=400,
            detail="metric must be: chunks, projects, packets, activity",
        )
    if granularity not in ("day", "week"):
        raise HTTPException(status_code=400, detail="granularity must be: day or week")
    data = AnalyticsService.time_series(
        session=session, metric=metric, days=days, granularity=granularity
    )
    return {
        "success": True,
        "data": data,
        "message": f"Time series: {data['total_in_period']} {metric} in last {days} days",
    }


@router.get("/analytics/top-chunks")
async def analytics_top_chunks(
    limit: int = Query(10, ge=1, le=100),
    days: Optional[int] = Query(None, ge=1, le=365),
    domain: Optional[str] = Query(None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    data = AnalyticsService.top_chunks(
        session=session, limit=limit, days=days, domain=domain
    )
    return {
        "success": True,
        "data": data,
        "message": f"Top {data['total_returned']} chunks returned",
    }


@router.get("/analytics/agent-usage")
async def analytics_agent_usage(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    data = AnalyticsService.agent_usage(session=session)
    return {
        "success": True,
        "data": data,
        "message": f"{data['total_agents']} agents with {data['total_projects_with_agents']} projects",
    }


# ═══════════════════════════════════════════════════════════════════
# Sub-router includes — one include_router per domain sub-router
# ═══════════════════════════════════════════════════════════════════

from app.modules.knowledge.routes.learning import router as learning_router
from app.modules.knowledge.routes.chunks import router as chunks_router
from app.modules.knowledge.routes.security import router as security_router
from app.modules.knowledge.routes.conflicts import router as conflicts_router
from app.modules.knowledge.routes.quality import router as quality_router

router.include_router(learning_router)
router.include_router(chunks_router)
router.include_router(security_router)
router.include_router(conflicts_router)
router.include_router(quality_router)
