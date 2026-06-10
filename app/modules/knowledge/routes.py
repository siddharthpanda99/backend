"""
Knowledge Engine — API Routes.

FastAPI route definitions for the Knowledge Engine at /api/v1/knowledge/.

Endpoints:
    POST /retrieve                    — Full retrieval pipeline
    POST /retrieve/stream             — SSE-streamed retrieval pipeline
    POST /search                      — Direct knowledge base search
    POST /query-understand            — Query understanding analysis only
    POST /chunk                       — Document chunking
    POST /embed                       — Single text embedding
    POST /embed/batch                 — Batch text embedding
    GET  /models                      — List available embedding models
    GET  /config                      — Get current configuration
    PUT  /config                      — Update configuration
    GET  /health                      — Service health check
    POST /compress                    — Compress embedding vector
    POST /decompress                  — Decompress embedding vector
    POST /ingest/document             — Ingest a document into knowledge base
    GET  /chunks                      — List knowledge chunks (with optional filters)
    POST /chunks                      — Create a new knowledge chunk
    GET  /chunks/{chunk_id}           — Get a single knowledge chunk by ID
    PUT  /chunks/{chunk_id}           — Update a knowledge chunk
    DELETE /chunks/{chunk_id}         — Delete a knowledge chunk
    POST /validate                    — Run validation on chunks or documents
    GET  /communities                 — List detected graph communities
    GET  /communities/{community_id}  — Get community details and entities
    GET  /learning/quality-log        — Get retrieval quality log data
    POST /learning/quality-log        — Record a retrieval outcome
    GET  /learning/scorer             — Get retrieval method scores
    GET  /learning/strategies         — Get strategy weights
    POST /learning/evolve             — Trigger strategy evolution
    POST /learning/evolve/rollback    — Rollback last strategy evolution
    GET  /learning/introspection      — Run introspection on a past retrieval
    POST /learning/meta-reasoner      — Evaluate a retrieval plan
    POST /learning/failure-analysis   — Analyze a retrieval failure
    GET  /learning/beliefs            — Get learned beliefs about methods
    POST /learning/beliefs/prune      — Prune low-confidence beliefs
    POST /learning/self-assess        — Run comprehensive self-assessment
    GET  /learning/self-assess        — Get latest self-assessment report
    POST /security/pii/redact         — Detect and redact PII from text
    POST /security/pii/detect         — Detect PII entities in text
    POST /security/pii/redact/batch   — Batch redact PII from multiple texts
    GET  /security/pii/scans           — List PII scan history
    GET  /security/pii/scans/stats     — PII scan statistics
    DELETE /security/pii/scans/{id}    — Delete a single scan record
    DELETE /security/pii/scans         — Clear all scan history
    POST /nlp/ner/train                — Train custom NER model
    GET  /nlp/ner/entity-types         — List available NER entity types
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
from app.modules.knowledge.instance_routes import router as instance_router
from app.modules.knowledge.models import KnowledgeChunkRecord
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.knowledge_engine.config import KnowledgeEngineError
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Engine"])


# ── Request / Response Schemas ───────────────────────────────


class RetrieveRequest(BaseModel):
    """Request body for the full retrieval pipeline."""

    query: str = Field(..., description="Natural language query", min_length=1)
    top_k: int = Field(100, description="Number of initial candidates", ge=1, le=500)
    token_budget: Optional[int] = Field(
        None,
        description="Token budget for context (reserved, currently unused by engine)",
        ge=1000,
    )


class SearchRequest(BaseModel):
    """Request body for direct search."""

    query: str = Field(..., description="Search query", min_length=1)
    top_k: int = Field(20, description="Maximum results", ge=1, le=100)
    filters: Optional[dict[str, Any]] = Field(
        None, description="Optional metadata filters"
    )


class QueryUnderstandRequest(BaseModel):
    """Request body for query understanding analysis."""

    query: str = Field(..., description="Query to analyze", min_length=1)
    context: Optional[dict[str, Any]] = Field(
        None, description="Optional context (domain, tenant_id, etc.)"
    )


class ChunkRequest(BaseModel):
    """Request body for document chunking."""

    text: str = Field(..., description="Text to chunk", min_length=1)
    source_id: str = Field(..., description="Source document identifier")
    content_type: str = Field(
        "text", description="Content type (text, code, markdown, qa)"
    )
    strategy: str = Field(
        "auto", description="Chunking strategy (auto, semantic, code, etc.)"
    )


class EmbedRequest(BaseModel):
    """Request body for text embedding."""

    text: str = Field(..., description="Text to embed", min_length=1)
    model_id: str = Field("BAAI/bge-m3", description="Embedding model ID")


class EmbedBatchRequest(BaseModel):
    """Request body for batch embedding."""

    texts: list[str] = Field(
        ..., description="Texts to embed", min_length=1, max_length=100
    )
    model_id: str = Field("BAAI/bge-m3", description="Embedding model ID")


class CompressRequest(BaseModel):
    """Request body for vector compression."""

    vector: list[float] = Field(..., description="Float32 vector to compress")
    bits: int = Field(8, description="Quantization bits (4 or 8)")


class DecompressRequest(BaseModel):
    """Request body for vector decompression."""

    compressed: str = Field(..., description="Base64-encoded compressed bytes")
    bits: int = Field(8, description="Quantization bits used during compression")
    dimensions: int = Field(..., description="Original vector dimensions")


class ConfigUpdateRequest(BaseModel):
    """Request body for configuration updates."""

    updates: dict[str, Any] = Field(..., description="Config fields to update")


# ── Endpoints ─────────────────────────────────────────────────


@router.post("/retrieve")
async def retrieve(
    request: RetrieveRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    """Execute the full retrieval pipeline: query understanding → hybrid search → rerank → context fusion.

    Returns a structured ContextPackage with ranked knowledge chunks,
    graph summaries, entity context, validation results, and formatted
    markdown ready for LLM consumption.
    """
    try:
        result = await service.retrieve(
            query=request.query,
            top_k=request.top_k,
        )
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
    """Direct knowledge base search without the full retrieval pipeline.

    Useful for fast, lightweight searches where re-ranking and
    context assembly are not needed. Supports optional metadata filters.
    """
    try:
        results = await service.search(
            query=request.query,
            filters=request.filters,
            top_k=request.top_k,
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
async def query_understand(
    request: QueryUnderstandRequest,
) -> dict[str, Any]:
    """Analyze a query without executing retrieval.

    Returns the structured RetrievalPlan with query type classification,
    extracted entities, keywords, rewrites, sub-queries, budget allocation,
    and detected filters. Useful for debugging and UI previews.
    """
    try:
        from common_lib.modules.knowledge_engine.retrieval.query_understanding import (
            QueryUnderstanding,
        )

        qu = QueryUnderstanding()
        plan = await qu.analyze(
            query=request.query,
            context=request.context or {},
        )
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
    """Split text into knowledge chunks using the selected strategy.

    Supports auto-detection, semantic, hierarchical, proposition, code,
    late, and single chunking strategies.
    """
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
    """Generate a vector embedding for a single text string.

    Uses the specified model (default: BAAI/bge-m3, 1024-dim).
    Returns dense vector and optionally sparse + ColBERT vectors for BGE-M3.
    """
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
    """Generate vector embeddings for multiple texts in batch.

    More efficient than individual /embed calls for multiple texts.
    Max 100 texts per batch.
    """
    try:
        result = await service.embed_batch(
            texts=request.texts,
            model_id=request.model_id,
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
    """List all available embedding models with metadata.

    Returns model IDs, dimensions, capabilities, cost, latency, and
    availability status for all 7 registered models.
    """
    try:
        models = service.list_models()
        default = service.get_default_model()
        return {
            "success": True,
            "data": {
                "models": models,
                "default": default,
                "total": len(models),
            },
            "message": f"{len(models)} models available",
        }

    except Exception as e:
        logger.exception("Failed to list models")
        raise HTTPException(status_code=500, detail=f"Failed to list models: {str(e)}")


@router.get("/config")
async def get_config(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    """Get the current Knowledge Engine configuration.

    Returns all configurable parameters: chunking, embedding, retrieval,
    reranking, context, validation, and learning settings.
    """
    try:
        config = service.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Configuration retrieved",
        }

    except Exception as e:
        logger.exception("Failed to get config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/config")
async def update_config(
    request: ConfigUpdateRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    """Update Knowledge Engine configuration fields.

    Accepts a partial update — only the fields specified in `updates`
    will be modified. Returns the full updated configuration.
    """
    try:
        config = service.update_config(request.updates)
        return {
            "success": True,
            "data": config,
            "message": "Configuration updated",
        }

    except Exception as e:
        logger.exception("Failed to update config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.get("/health")
async def health_check(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
) -> dict[str, Any]:
    """Check Knowledge Engine health and return status.

    Returns initialization state, available models count, supported
    chunking strategies, and current configuration.
    """
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
    """Compress an embedding vector using TurboQuant quantization.

    8-bit compression: ~4x size reduction (near-lossless)
    4-bit compression: ~8x size reduction
    Returns base64-encoded compressed bytes.
    """
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
    """Decompress a TurboQuant-compressed vector.

    Reconstructs an approximate float32 vector from compressed bytes.
    Accepts base64-encoded compressed data.
    """
    try:
        import base64

        compressed_bytes = base64.b64decode(request.compressed)
        vector = service.decompress_vector(compressed_bytes, bits=request.bits)
        return {
            "success": True,
            "data": {
                "vector": vector[:10],  # First 10 elements as preview
                "dimensions": len(vector),
                "bits": request.bits,
            },
            "message": f"Vector decompressed ({len(vector)} dims)",
        }

    except Exception as e:
        logger.exception("Decompression failed")
        raise HTTPException(status_code=500, detail=f"Decompression failed: {str(e)}")


# =====================================================================
# NEW ENDPOINTS: ingest, chunks CRUD, validate, communities, learning
# =====================================================================

# ── Request / Response Schemas for new endpoints ─────────────────


class PIIRedactRequest(BaseModel):
    text: str = Field(..., description="Text content to redact", min_length=1)
    strategy: str = Field(
        "redact", description="Redaction strategy: redact, mask, hash, replace"
    )
    language: str = Field("en", description="Language code")


class PIIDetectRequest(BaseModel):
    text: str = Field(..., description="Text content to scan", min_length=1)
    language: str = Field("en", description="Language code")


class PIIBatchRedactRequest(BaseModel):
    texts: list[str] = Field(
        ..., description="List of texts to redact", min_length=1, max_length=100
    )
    strategy: str = Field("redact", description="Redaction strategy")


def _fetch_knowledge_chunks(session: Session) -> list[Any]:
    """Fetch all chunks from DB and convert to KnowledgeChunk objects."""
    from common_lib.modules.knowledge_engine.models.knowledge import KnowledgeChunk

    records = session.exec(select(KnowledgeChunkRecord)).all()
    chunks = []
    for rec in records:
        try:
            kc = KnowledgeChunk(
                chunk_id=UUID(rec.chunk_id),
                content=rec.content,
                source_id=rec.source_id,
                source_type=rec.source_type,
                entity_mentions=rec.entity_mentions or [],
                topics=rec.topics or [],
                domain=rec.domain,
            )
            chunks.append(kc)
        except Exception:
            continue
    return chunks


def _record_to_dict(rec: KnowledgeChunkRecord) -> dict[str, Any]:
    """Convert a KnowledgeChunkRecord to a serializable dict."""
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


class IngestDocumentRequest(BaseModel):
    source_id: str = Field(..., description="Source connector identifier")
    content: str = Field(..., description="Document content text")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata (title, author, content_type, etc.)",
    )
    strategy: str = Field("auto", description="Chunking strategy")


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


class ValidateRequest(BaseModel):
    chunks: list[str] = Field(
        ..., description="List of chunk IDs or contents to validate", min_length=1
    )
    query: str = Field("", description="Original query for context")
    query_type: str = Field(
        "factual", description="Type of query for validation thresholds"
    )


class QualityLogRecordRequest(BaseModel):
    query: str = Field(..., description="The retrieval query")
    result_count: int = Field(0, description="Number of results returned")
    latency_ms: float = Field(0.0, description="Retrieval latency")
    methods_used: list[str] = Field(default_factory=list)
    precision: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall: Optional[float] = Field(None, ge=0.0, le=1.0)
    user_rating: Optional[float] = Field(None, ge=0.0, le=1.0)
    error: Optional[str] = Field(None)


class IntrospectionRequest(BaseModel):
    query: str = Field(..., description="The original retrieval query")
    result_count: int = Field(0, description="Number of results returned")
    latency_ms: float = Field(0.0)
    methods_used: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class MetaReasonerRequest(BaseModel):
    query: str = Field(..., description="The query to evaluate")
    plan: dict[str, Any] = Field(
        default_factory=dict, description="Retrieval plan with methods, weights"
    )
    previous_outcomes: list[dict[str, Any]] = Field(default_factory=list)


class FailureAnalysisRequest(BaseModel):
    query: str = Field(..., description="The query that failed")
    error: str = Field(..., description="Error message")
    methods_used: list[str] = Field(default_factory=list)
    latency_ms: float = Field(0.0)


# ── Self-Assessment ──────────────────────────────────────────────


class SelfAssessRequest(BaseModel):
    """Optional overrides for self-assessment."""

    run_full: bool = Field(
        True,
        description="Whether to run a full assessment (gather from all subsystems)",
    )


# ── Database-backed Chunk Store ──────────────────────────────────
# Uses the knowledge_chunks table via SQLModel for persistence.
# Supports PostgreSQL (production) and SQLite (dev/testing).


# ═══════════════════════════════════════════════════════════════════
# POST /ingest/document
# ═══════════════════════════════════════════════════════════════════


@router.post("/ingest/document")
async def ingest_document(
    request: IngestDocumentRequest,
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Ingest a document into the knowledge base.

    Chunks the document, generates embeddings, and persists chunks
    to the database. Returns job status with count of chunks created.
    """
    try:
        metadata = {
            "source_id": request.source_id,
            "content_type": request.metadata.get("content_type", "text"),
            "title": request.metadata.get("title", ""),
            "author": request.metadata.get("author", ""),
        }
        if request.strategy != "auto":
            metadata["strategy"] = request.strategy

        # Chunk the document
        chunks = await service.chunk(text=request.content, metadata=metadata)

        # Persist chunks to database
        job_id = str(uuid4())
        stored_ids = []
        for chunk in chunks:
            chunk_data = chunk.model_dump() if hasattr(chunk, "model_dump") else {}
            cid = str(chunk_data.get("chunk_id", uuid4()))
            record = KnowledgeChunkRecord(
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
            session.add(record)
            stored_ids.append(cid)

        session.commit()

        return {
            "success": True,
            "data": {
                "job_id": job_id,
                "source_id": request.source_id,
                "chunks_created": len(stored_ids),
                "chunk_ids": stored_ids,
            },
            "message": f"Ingested document: {len(stored_ids)} chunks created",
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
    """Execute the retrieval pipeline with SSE streaming updates.

    Streams status updates for each stage of the pipeline:
    - query_understanding: Analyzing query intent
    - hybrid_search: Running retrievers
    - reranking: Re-ranking results
    - validation: Validating results
    - context_fusion: Assembling context
    - complete: Final result
    """

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            # Stage 1: Query Understanding
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

            # Stage 2: Hybrid Search
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

            # Stage 3: Complete
            yield _sse_event(
                "complete",
                {
                    "status": "success",
                    "result": result,
                },
            )

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
    """Format a Server-Sent Event string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


# ═══════════════════════════════════════════════════════════════════
# Chunks CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/chunks")
async def list_chunks(
    source_id: Optional[str] = Query(None, description="Filter by source ID"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List knowledge chunks with optional filtering.

    Supports filtering by source_id and domain, with pagination.
    """
    query = select(KnowledgeChunkRecord)

    if source_id:
        query = query.where(KnowledgeChunkRecord.source_id == source_id)
    if domain:
        query = query.where(KnowledgeChunkRecord.domain == domain)

    # Get total count (efficient single-row query)
    count_query = select(func.count(KnowledgeChunkRecord.id))
    if source_id:
        count_query = count_query.where(KnowledgeChunkRecord.source_id == source_id)
    if domain:
        count_query = count_query.where(KnowledgeChunkRecord.domain == domain)
    total = session.exec(count_query).scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)
    records = session.exec(query).all()

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
    """Create a new knowledge chunk.

    Persists the chunk to the database and optionally generates
    an embedding for the chunk content.
    """
    try:
        chunk_id = str(uuid4())

        # Optionally embed the content
        embedding = None
        try:
            embed_result = await service.embed(text=request.content)
            embedding = embed_result.dense if hasattr(embed_result, "dense") else None
        except Exception:
            pass

        record = KnowledgeChunkRecord(
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
        session.add(record)
        session.commit()
        session.refresh(record)

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
    """Get a single knowledge chunk by ID."""
    record = session.exec(
        select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.chunk_id == chunk_id)
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")

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
    """Update an existing knowledge chunk.

    Partial update — only specified fields are modified.
    """
    record = session.exec(
        select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.chunk_id == chunk_id)
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")

    update_data = request.model_dump(exclude_none=True)
    if "content" in update_data:
        record.content = update_data["content"]
    if "metadata" in update_data:
        record.metadata_json = update_data["metadata"]
    if "entity_mentions" in update_data:
        record.entity_mentions = update_data["entity_mentions"]
    if "topics" in update_data:
        record.topics = update_data["topics"]
    if "domain" in update_data:
        record.domain = update_data["domain"]
    if "classification" in update_data:
        record.classification = update_data["classification"]

    session.add(record)
    session.commit()
    session.refresh(record)

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
    """Delete a knowledge chunk by ID."""
    record = session.exec(
        select(KnowledgeChunkRecord).where(KnowledgeChunkRecord.chunk_id == chunk_id)
    ).first()

    if not record:
        raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")

    session.delete(record)
    session.commit()

    return {
        "success": True,
        "data": {"chunk_id": chunk_id},
        "message": f"Chunk {chunk_id[:8]} deleted",
    }


# ═══════════════════════════════════════════════════════════════════
# POST /validate
# ═══════════════════════════════════════════════════════════════════


@router.post("/validate")
async def validate_knowledge(
    request: ValidateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Run validation on chunks or documents.

    Checks for contradictions, staleness, low confidence, and
    hallucination risks. Returns a ValidationReport.
    """
    try:
        from common_lib.modules.knowledge_engine.validation.validator import (
            KnowledgeValidator,
        )

        validator = KnowledgeValidator()

        # Convert chunk IDs or content strings into RetrievedChunk-like dicts
        from common_lib.modules.knowledge_engine.models.validation import (
            ValidationReport,
        )

        # Build pseudo-chunks from the input — resolve chunk IDs from DB
        pseudo_chunks = []
        for item in request.chunks:
            # Check if it's a stored chunk ID
            record = session.exec(
                select(KnowledgeChunkRecord).where(
                    KnowledgeChunkRecord.chunk_id == item
                )
            ).first()
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
                # Treat as raw content
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

        return {
            "success": True,
            "data": report,
            "message": "Validation complete",
        }

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
    """List detected knowledge graph communities.

    Returns community metadata including member count, top keywords,
    and summary if available. Requires chunks to exist in the database.
    """
    try:
        from common_lib.modules.knowledge_engine.knowledge_graph.graphrag import (
            GraphRAGIndexer,
            GraphRAGConfig,
        )

        # Check if any chunks exist in the DB
        total_chunks = session.exec(select(KnowledgeChunkRecord)).all()
        if not total_chunks:
            return {
                "success": True,
                "data": {
                    "communities": [],
                    "total": 0,
                    "message": "No chunks indexed yet. Ingest documents first.",
                },
            }

        # Convert DB records to KnowledgeChunks
        knowledge_chunks = _fetch_knowledge_chunks(session)

        if not knowledge_chunks:
            return {
                "success": True,
                "data": {"communities": [], "total": 0},
            }

        indexer = GraphRAGIndexer(
            GraphRAGConfig(min_cooccurrence=1, min_community_size=min_members)
        )
        communities = indexer.build_communities(knowledge_chunks)

        community_list = []
        for c in communities:
            community_list.append(
                {
                    "community_id": c.community_id,
                    "label": c.label,
                    "member_count": c.member_count,
                    "chunk_count": len(c.chunk_ids),
                    "top_keywords": c.top_keywords[:10],
                    "summary": c.summary,
                }
            )

        return {
            "success": True,
            "data": {
                "communities": community_list,
                "total": len(community_list),
            },
            "message": f"Found {len(community_list)} communities",
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
    """Get detailed information about a specific community.

    Returns community entities, relationships, summary, and
    representative chunks.
    """
    try:
        from common_lib.modules.knowledge_engine.knowledge_graph.graphrag import (
            GraphRAGIndexer,
            GraphRAGConfig,
        )

        # Fetch chunks from DB
        all_chunks = session.exec(select(KnowledgeChunkRecord)).all()
        if not all_chunks:
            raise HTTPException(status_code=404, detail="No chunks indexed")

        knowledge_chunks = _fetch_knowledge_chunks(session)

        if not knowledge_chunks:
            raise HTTPException(status_code=404, detail="No valid chunks found")

        indexer = GraphRAGIndexer(GraphRAGConfig(min_cooccurrence=1))
        indexer.build_communities(knowledge_chunks)

        # Find the requested community
        community = None
        for c in indexer.get_all_communities():
            if c.community_id == community_id:
                community = c
                break

        if not community:
            raise HTTPException(
                status_code=404, detail=f"Community {community_id} not found"
            )

        summary = indexer.get_community_summary(community_id)
        entity_neighbors = {}
        for entity in list(community.entity_ids)[:20]:
            neighbors = indexer.get_entity_neighbors(entity, min_weight=1)
            if neighbors:
                entity_neighbors[entity] = [
                    {"entity": n, "weight": w} for n, w in neighbors[:10]
                ]

        return {
            "success": True,
            "data": {
                "community_id": community.community_id,
                "label": community.label,
                "member_count": community.member_count,
                "entity_ids": list(community.entity_ids),
                "chunk_count": len(community.chunk_ids),
                "top_keywords": community.top_keywords,
                "summary": summary.model_dump() if summary else None,
                "entity_neighbors": entity_neighbors,
            },
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
# Learning Endpoints
# ═══════════════════════════════════════════════════════════════════

# Lazy-initialized learning subsystem instances
_learning_instances: dict[str, Any] = {}


def _get_learning_instance(name: str) -> Any:
    """Get or create a lazy-initialized learning component."""
    if name not in _learning_instances:
        if name == "quality_log":
            from common_lib.modules.knowledge_engine.learning.quality_log import (
                RetrievalQualityLog,
            )

            _learning_instances[name] = RetrievalQualityLog()
        elif name == "scorer":
            from common_lib.modules.knowledge_engine.learning.scorer import (
                SelfLearningRetrievalScorer,
            )

            _learning_instances[name] = SelfLearningRetrievalScorer()
        elif name == "evolver":
            from common_lib.modules.knowledge_engine.learning.strategy_evolver import (
                RetrievalStrategyEvolver,
            )

            _learning_instances[name] = RetrievalStrategyEvolver()
        elif name == "introspection":
            from common_lib.modules.knowledge_engine.learning.introspection import (
                RetrievalIntrospection,
            )

            _learning_instances[name] = RetrievalIntrospection()
        elif name == "meta_reasoner":
            from common_lib.modules.knowledge_engine.learning.meta_reasoner import (
                RetrievalMetaReasoner,
            )

            _learning_instances[name] = RetrievalMetaReasoner()
        elif name == "failure_analyzer":
            from common_lib.modules.knowledge_engine.learning.failure_analysis import (
                RetrievalFailureAnalyzer,
            )

            _learning_instances[name] = RetrievalFailureAnalyzer()
        elif name == "belief_reviser":
            from common_lib.modules.knowledge_engine.learning.belief_reviser import (
                RetrievalBeliefReviser,
            )

            _learning_instances[name] = RetrievalBeliefReviser()
        elif name == "conflict_resolver":
            from common_lib.modules.knowledge_engine.learning.conflict_resolver import (
                RetrievalConflictResolver,
            )

            _learning_instances[name] = RetrievalConflictResolver()
        elif name == "evolution_branching":
            from common_lib.modules.knowledge_engine.learning.evolution_branching import (
                EvolutionBranching,
            )

            _learning_instances[name] = EvolutionBranching()
        elif name == "knowledge_pruner":
            from common_lib.modules.knowledge_engine.learning.knowledge_pruner import (
                RetrievalKnowledgePruner,
            )

            _learning_instances[name] = RetrievalKnowledgePruner()
        elif name == "self_assessment":
            from common_lib.modules.knowledge_engine.learning.self_assessment import (
                SelfAssessmentFinder,
            )

            finder = SelfAssessmentFinder()

            # Wire up DB persistence callback
            def _persist_assessment(report):
                try:
                    from app.modules.knowledge.models import SelfAssessmentRecord
                    import os
                    from sqlmodel import create_engine, Session

                    database_url = os.getenv("DATABASE_URL", "sqlite:///./test.db")
                    engine = create_engine(database_url)
                    with Session(engine) as sess:
                        rec = SelfAssessmentRecord(
                            report_id=report.report_id,
                            overall_health_score=report.overall_health_score,
                            strategy_generation=report.strategy_generation,
                            quality_metrics_json=report.quality_metrics,
                            method_scores_json=report.method_scores,
                            strategy_weights_json=report.strategy_weights,
                            failure_stats_json=report.failure_stats,
                            beliefs_json=report.beliefs,
                            findings_json=report.findings,
                            recommendations_json=report.recommendations,
                        )
                        sess.add(rec)
                        sess.commit()
                except Exception as e:
                    logger.warning(f"Failed to persist self-assessment report: {e}")

            finder.set_store_callback(_persist_assessment)
            _learning_instances[name] = finder
        elif name == "adaptive_strategy":
            from common_lib.modules.knowledge_engine.ingestion.adaptive_strategy import (
                AdaptiveIngestionStrategy,
            )

            _learning_instances[name] = AdaptiveIngestionStrategy()
    return _learning_instances[name]


@router.get("/learning/quality-log")
async def get_quality_log(
    n: int = Query(100, ge=1, le=1000, description="Number of recent entries"),
) -> dict[str, Any]:
    """Get recent retrieval quality log entries.

    Returns the most recent N outcomes from the quality log,
    along with aggregate method performance metrics.
    """
    try:
        log = _get_learning_instance("quality_log")
        recent = await log.get_recent(n=n)
        method_perf = await log.get_method_performance()
        failures = await log.get_failures()

        return {
            "success": True,
            "data": {
                "recent_outcomes": [o.model_dump() for o in recent],
                "total": len(recent),
                "method_performance": method_perf,
                "failure_count": len(failures),
            },
            "message": f"Quality log: {len(recent)} entries",
        }

    except Exception as e:
        logger.exception("Failed to get quality log")
        raise HTTPException(
            status_code=500, detail=f"Failed to get quality log: {str(e)}"
        )


@router.get("/learning/quality-log/config")
async def get_quality_log_config() -> dict[str, Any]:
    """Get the configuration for the Retrieval Quality Log.

    Returns the toggled state, current log storage folder, and
    enabled outcomes/fields.
    """
    try:
        log = _get_learning_instance("quality_log")
        config = log.get_config()
        return {
            "success": True,
            "data": config,
            "message": "Quality log configuration retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get quality log config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/quality-log/config")
async def update_quality_log_config(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update the configuration for the Retrieval Quality Log.

    Accepts partial updates:
    - enabled (bool): Enable or disable quality logging
    - log_dir (str): Folder path to store logs
    - enabled_fields (list[str]): Outcomes/metrics to record
    """
    try:
        log = _get_learning_instance("quality_log")

        enabled = request.updates.get("enabled")
        log_dir = request.updates.get("log_dir")
        enabled_fields = request.updates.get("enabled_fields")

        config = log.update_config(
            enabled=enabled if isinstance(enabled, bool) else None,
            log_dir=log_dir if isinstance(log_dir, str) else None,
            enabled_fields=enabled_fields if isinstance(enabled_fields, list) else None,
        )
        return {
            "success": True,
            "data": config,
            "message": "Quality log configuration updated",
        }
    except Exception as e:
        logger.exception("Failed to update quality log config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


from app.modules.knowledge.learning_routes import router as learning_router

router.include_router(learning_router)


@router.post("/learning/quality-log")
async def record_quality_log(
    request: QualityLogRecordRequest,
) -> dict[str, Any]:
    """Record a retrieval outcome in the quality log.

    Used by the self-learning system to track retrieval quality and
    improve future retrievals.
    """
    try:
        from common_lib.modules.knowledge_engine.learning.quality_log import (
            RetrievalOutcome,
        )

        log = _get_learning_instance("quality_log")
        outcome = RetrievalOutcome(
            query=request.query,
            result_count=request.result_count,
            latency_ms=request.latency_ms,
            methods_used=request.methods_used,
            precision=request.precision,
            recall=request.recall,
            user_rating=request.user_rating,
            error=request.error,
        )
        await log.record(outcome)

        # Check auto-evolution — tick query counter and evolve if threshold met
        method_scores: dict[str, float] = {}
        try:
            evolver = _get_learning_instance("evolver")
            scorer = _get_learning_instance("scorer")
            method_scores = await scorer.get_all_scores()
            auto_result = await evolver.tick_query(method_scores=method_scores)
            if auto_result:
                logger.info(
                    f"Auto-evolution triggered: gen {auto_result['generation']}"
                )
        except Exception:
            logger.warning("Auto-evolution tick failed (non-blocking)")

        # Feed quality log data to adaptive strategy
        try:
            adaptive = _get_learning_instance("adaptive_strategy")
            await adaptive.learn_from_quality_log(log)
            if method_scores:
                adaptive.learn_from_evolver(method_scores)
        except Exception:
            logger.warning("Adaptive strategy learning failed (non-blocking)")

        # Also update scorer and belief reviser
        if request.user_rating is not None:
            scorer = _get_learning_instance("scorer")
            for method in request.methods_used:
                await scorer.update(
                    method, rating=request.user_rating, latency_ms=request.latency_ms
                )
                reviser = _get_learning_instance("belief_reviser")
                await reviser.update(
                    method, effectiveness=request.user_rating, confidence=0.6
                )

        return {
            "success": True,
            "data": {"outcome_id": outcome.id},
            "message": "Outcome recorded",
        }

    except Exception as e:
        logger.exception("Failed to record quality log")
        raise HTTPException(status_code=500, detail=f"Failed to record: {str(e)}")


@router.get("/learning/scorer")
async def get_scorer_scores() -> dict[str, Any]:
    """Get current retrieval method scores.

    Returns ranked scores for each retrieval method based on
    historical feedback, used by the strategy evolver.
    """
    try:
        scorer = _get_learning_instance("scorer")
        scores = await scorer.get_all_scores()
        ranking = await scorer.get_ranking()

        return {
            "success": True,
            "data": {
                "scores": scores,
                "ranking": ranking,
            },
            "message": f"Scored {len(scores)} methods",
        }

    except Exception as e:
        logger.exception("Failed to get scorer scores")
        raise HTTPException(status_code=500, detail=f"Failed to get scores: {str(e)}")


@router.get("/learning/strategies")
async def get_strategies() -> dict[str, Any]:
    """Get current retrieval strategy weights.

    Returns the current weight distribution across retrieval methods
    (dense, sparse, graph, metadata, hyde) and the generation number.
    """
    try:
        evolver = _get_learning_instance("evolver")
        weights = await evolver.get_weights()
        generation = await evolver.get_generation()
        has_snapshot = await evolver.has_snapshot()

        return {
            "success": True,
            "data": {
                "weights": weights,
                "generation": generation,
                "default_weights": dict(evolver.DEFAULT_WEIGHTS),
                "has_snapshot": has_snapshot,
            },
            "message": f"Strategy generation {generation}",
        }

    except Exception as e:
        logger.exception("Failed to get strategies")
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategies: {str(e)}"
        )


@router.post("/learning/evolve")
async def evolve_strategies() -> dict[str, Any]:
    """Trigger strategy evolution.

    Analyzes historical retrieval quality data and adjusts method
    weights to optimize future retrieval performance.
    Returns the new weight distribution.
    """
    try:
        scorer = _get_learning_instance("scorer")
        evolver = _get_learning_instance("evolver")

        method_scores = await scorer.get_all_scores()
        new_weights = await evolver.evolve(method_scores)
        generation = await evolver.get_generation()

        return {
            "success": True,
            "data": {
                "weights": new_weights,
                "generation": generation,
                "previous_scores": method_scores,
            },
            "message": f"Strategies evolved to generation {generation}",
        }

    except Exception as e:
        logger.exception("Failed to evolve strategies")
        raise HTTPException(status_code=500, detail=f"Failed to evolve: {str(e)}")


@router.get("/learning/evolve/auto-config")
async def get_auto_evolve_config() -> dict[str, Any]:
    """Get auto-evolution configuration.

    Returns whether auto-evolution is enabled, the interval (in queries),
    and the current query progress toward the next evolution.
    """
    try:
        evolver = _get_learning_instance("evolver")
        config = await evolver.get_auto_config()

        return {
            "success": True,
            "data": config,
            "message": f"Auto-evolution {'enabled' if config['enabled'] else 'disabled'} every {config['interval']} queries",
        }

    except Exception as e:
        logger.exception("Failed to get auto-evolve config")
        raise HTTPException(status_code=500, detail=f"Failed to get config: {str(e)}")


@router.put("/learning/evolve/auto-config")
async def update_auto_evolve_config(request: ConfigUpdateRequest) -> dict[str, Any]:
    """Update auto-evolution configuration.

    Accepts partial updates with fields:
    - enabled (bool): Enable or disable auto-evolution
    - interval (int): Number of queries between evolutions (10-10000)

    When disabled, the query counter resets. When re-enabled,
    counting starts fresh.
    """
    try:
        evolver = _get_learning_instance("evolver")

        enabled = request.updates.get("enabled")
        interval = request.updates.get("interval")

        config = await evolver.set_auto_config(
            enabled=enabled if isinstance(enabled, bool) else None,
            interval=interval if isinstance(interval, int) else None,
        )

        return {
            "success": True,
            "data": config,
            "message": "Auto-evolution config updated",
        }

    except Exception as e:
        logger.exception("Failed to update auto-evolve config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.post("/learning/evolve/rollback")
async def rollback_evolve_strategies() -> dict[str, Any]:
    """Rollback the last strategy evolution.

    Restores the previous weight distribution from the snapshot
    taken before the last evolution. Returns the restored weights.
    """
    try:
        evolver = _get_learning_instance("evolver")

        has_snapshot = await evolver.has_snapshot()
        if not has_snapshot:
            raise HTTPException(
                status_code=400,
                detail="No snapshot available. Evolve strategies first before rolling back.",
            )

        restored_weights = await evolver.rollback()
        generation = await evolver.get_generation()

        return {
            "success": True,
            "data": {
                "weights": restored_weights,
                "generation": generation,
            },
            "message": f"Strategies rolled back to generation {generation}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to rollback strategies")
        raise HTTPException(status_code=500, detail=f"Failed to rollback: {str(e)}")


@router.get("/learning/introspection")
async def run_introspection(
    query: str = Query(..., description="Original retrieval query"),
    result_count: int = Query(0, ge=0),
    latency_ms: float = Query(0.0, ge=0.0),
) -> dict[str, Any]:
    """Run introspection on a past retrieval.

    Assesses retrieval quality and provides improvement suggestions.
    Returns an IntrospectionReport with quality scores and issues.
    """
    try:
        insp = _get_learning_instance("introspection")

        report = await insp.inspect(
            query=query,
            result_count=result_count,
            latency_ms=latency_ms,
            methods_used=["dense", "sparse"],
        )

        return {
            "success": True,
            "data": report.model_dump(),
            "message": f"Retrieval quality: {report.overall_retrieval_quality:.2f}",
        }

    except Exception as e:
        logger.exception("Failed to run introspection")
        raise HTTPException(status_code=500, detail=f"Introspection failed: {str(e)}")


@router.post("/learning/meta-reasoner")
async def evaluate_plan(
    request: MetaReasonerRequest,
) -> dict[str, Any]:
    """Evaluate a retrieval plan using the meta-reasoner.

    Analyzes the proposed retrieval plan for coverage, risks, and
    suggests improvements based on past outcomes.
    """
    try:
        reasoner = _get_learning_instance("meta_reasoner")

        result = await reasoner.evaluate_plan(
            query=request.query,
            plan=request.plan,
            previous_outcomes=request.previous_outcomes,
        )

        return {
            "success": True,
            "data": result,
            "message": f"Plan score: {result.get('plan_score', 0):.2f}",
        }

    except Exception as e:
        logger.exception("Failed to evaluate plan")
        raise HTTPException(status_code=500, detail=f"Plan evaluation failed: {str(e)}")


@router.post("/learning/failure-analysis")
async def analyze_failure(
    request: FailureAnalysisRequest,
) -> dict[str, Any]:
    """Analyze a retrieval failure.

    Classifies the failure, provides severity assessment, and
    suggests corrective actions.
    """
    try:
        analyzer = _get_learning_instance("failure_analyzer")

        result = await analyzer.analyze(
            query=request.query,
            error=request.error,
            methods_used=request.methods_used,
            latency_ms=request.latency_ms,
        )

        stats = await analyzer.get_stats()

        return {
            "success": True,
            "data": {
                "analysis": result,
                "stats": stats,
            },
            "message": f"Failure category: {result['category']}",
        }

    except Exception as e:
        logger.exception("Failed to analyze failure")
        raise HTTPException(
            status_code=500, detail=f"Failure analysis failed: {str(e)}"
        )


@router.get("/learning/beliefs")
async def get_beliefs(
    threshold: float = Query(
        0.6, ge=0.0, le=1.0, description="Confidence threshold for recommendations"
    ),
) -> dict[str, Any]:
    """Get learned beliefs about retrieval methods.

    Returns all learned beliefs and method recommendations
    based on accumulated evidence.
    """
    try:
        reviser = _get_learning_instance("belief_reviser")

        all_beliefs = await reviser.get_all_beliefs()
        recommendations = await reviser.recommend_methods(threshold=threshold)

        return {
            "success": True,
            "data": {
                "beliefs": all_beliefs,
                "recommendations": recommendations,
                "recommendation_threshold": threshold,
            },
            "message": f"{len(all_beliefs)} beliefs, {len(recommendations)} recommendations",
        }

    except Exception as e:
        logger.exception("Failed to get beliefs")
        raise HTTPException(status_code=500, detail=f"Failed to get beliefs: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# POST /learning/self-assess — Trigger comprehensive self-assessment
# ═══════════════════════════════════════════════════════════════════


@router.post("/learning/self-assess")
async def run_self_assessment(
    request: SelfAssessRequest | None = None,
) -> dict[str, Any]:
    """Run a comprehensive system self-assessment.

    Gathers metrics from all learning subsystems (quality log, scorer,
    evolver, failure analyzer, belief reviser) and produces a holistic
    health report with findings and recommendations.
    Results are stored in-memory for future retrieval.
    """
    try:
        finder = _get_learning_instance("self_assessment")

        quality_log = _get_learning_instance("quality_log")
        scorer = _get_learning_instance("scorer")
        evolver = _get_learning_instance("evolver")
        failure_analyzer = _get_learning_instance("failure_analyzer")
        belief_reviser = _get_learning_instance("belief_reviser")

        report = await finder.assess(
            quality_log=quality_log,
            scorer=scorer,
            evolver=evolver,
            failure_analyzer=failure_analyzer,
            belief_reviser=belief_reviser,
        )

        return {
            "success": True,
            "data": report.to_dict(),
            "message": (
                f"Self-assessment complete: health={report.overall_health_score:.2f}, "
                f"{len(report.findings)} findings, {len(report.recommendations)} recommendations"
            ),
        }

    except Exception as e:
        logger.exception("Self-assessment failed")
        raise HTTPException(status_code=500, detail=f"Self-assessment failed: {str(e)}")


@router.get("/learning/self-assess")
async def get_self_assessment(
    n: int = Query(1, ge=1, le=50, description="Number of recent reports to return"),
) -> dict[str, Any]:
    """Get stored self-assessment reports.

    Returns the latest N self-assessment reports without re-running.
    Use POST /learning/self-assess to trigger a fresh assessment.
    """
    try:
        finder = _get_learning_instance("self_assessment")
        reports = await finder.get_all_reports(n=n)
        total = await finder.get_report_count()

        return {
            "success": True,
            "data": {
                "reports": [r.to_dict() for r in reports],
                "total": total,
                "returned": len(reports),
            },
            "message": f"{len(reports)} report(s) retrieved",
        }

    except Exception as e:
        logger.exception("Failed to get self-assessment reports")
        raise HTTPException(status_code=500, detail=f"Failed to get reports: {str(e)}")


# ═══════════════════════════════════════════════════════════════════
# Self-Assessment Scheduler Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/learning/self-assess/schedule")
async def get_self_assess_schedule() -> dict[str, Any]:
    """Get self-assessment scheduler configuration.

    Returns whether periodic assessment is enabled and the
    interval in minutes.
    """
    try:
        finder = _get_learning_instance("self_assessment")
        schedule = await finder.get_schedule()
        return {
            "success": True,
            "data": schedule,
            "message": "Schedule config retrieved",
        }
    except Exception as e:
        logger.exception("Failed to get schedule")
        raise HTTPException(status_code=500, detail=f"Failed to get schedule: {str(e)}")


@router.put("/learning/self-assess/schedule")
async def update_self_assess_schedule(
    request: ConfigUpdateRequest,
) -> dict[str, Any]:
    """Update self-assessment scheduler configuration.

    Accepts partial updates:
    - enabled (bool): Enable or disable periodic assessments
    - interval_minutes (int): Interval between assessments (1-1440)

    When enabled, assessments run in the background on the configured
    interval. Health degradation is detected automatically.
    """
    try:
        finder = _get_learning_instance("self_assessment")

        enabled = request.updates.get("enabled")
        interval_minutes = request.updates.get("interval_minutes")

        schedule = await finder.set_schedule(
            enabled=enabled if isinstance(enabled, bool) else None,
            interval_minutes=interval_minutes
            if isinstance(interval_minutes, int)
            else None,
        )

        return {
            "success": True,
            "data": schedule,
            "message": f"Self-assessment scheduler {'enabled' if schedule['enabled'] else 'disabled'}",
        }

    except Exception as e:
        logger.exception("Failed to update schedule")
        raise HTTPException(
            status_code=500, detail=f"Failed to update schedule: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════
# Adaptive Strategy Endpoint
# ═══════════════════════════════════════════════════════════════════


@router.get("/learning/adaptive-strategy")
async def get_adaptive_strategy_status() -> dict[str, Any]:
    """Get adaptive ingestion strategy status.

    Returns the current state of the adaptive strategy engine,
    including feedback registry, learned patterns from query
    quality logs, evolver weights, and last selected strategy.
    """
    try:
        adaptive = _get_learning_instance("adaptive_strategy")
        status = adaptive.get_status()
        return {
            "success": True,
            "data": status,
            "message": f"Adaptive strategy: {status['selection_count']} selections, "
            f"{len(status['feedback_entries'])} doc types tracked",
        }
    except Exception as e:
        logger.exception("Failed to get adaptive strategy status")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get adaptive strategy status: {str(e)}",
        )


@router.post("/learning/adaptive-strategy/learn")
async def trigger_adaptive_learning() -> dict[str, Any]:
    """Trigger adaptive strategy to learn from the quality log.

    Manually triggers the adaptive strategy to analyze recent
    retrieval outcomes and update its strategy selection criteria.
    """
    try:
        adaptive = _get_learning_instance("adaptive_strategy")
        quality_log = _get_learning_instance("quality_log")
        evolver = _get_learning_instance("evolver")

        updated = await adaptive.learn_from_quality_log(quality_log)

        try:
            weights = await evolver.get_weights()
            if weights:
                adaptive.learn_from_evolver(weights)
        except Exception:
            pass

        return {
            "success": True,
            "data": {
                "feedback_records_updated": updated,
                "status": adaptive.get_status(),
            },
            "message": f"Adaptive strategy learned from {updated} quality log records",
        }
    except Exception as e:
        logger.exception("Failed to trigger adaptive learning")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger adaptive learning: {str(e)}",
        )


# ═══════════════════════════════════════════════════════════════════
# Security: PII Redaction Endpoints
# ═══════════════════════════════════════════════════════════════════


# Lazy singleton for the PII redactor
_pii_redactor: KnowledgePIIRedactor | None = None


def _get_pii_redactor() -> KnowledgePIIRedactor:
    global _pii_redactor
    if _pii_redactor is None:
        from common_lib.modules.knowledge_engine.security import (
            KnowledgePIIRedactor,
        )

        _pii_redactor = KnowledgePIIRedactor(use_presidio=True)
    return _pii_redactor


@router.post("/security/pii/redact")
async def redact_pii(
    request: PIIRedactRequest,
) -> dict[str, Any]:
    """Detect and redact PII from text using Presidio.

    Scans text for personally identifiable information (emails, phone
    numbers, SSNs, credit cards, etc.) and redacts them using the
    specified strategy:
    - redact: Replace with [REDACTED]
    - mask: Partially mask sensitive portions
    - hash: Replace with SHA-256 hash
    - replace: Replace with realistic fake values

    Falls back to regex detection if Presidio is unavailable.
    """
    try:
        redactor = _get_pii_redactor()
        result = redactor.redact(
            text=request.text,
            strategy=request.strategy,
        )

        return {
            "success": True,
            "data": result,
            "message": f"Redacted {result['entity_count']} PII entities",
        }

    except Exception as e:
        logger.exception("PII redaction failed")
        raise HTTPException(status_code=500, detail=f"PII redaction failed: {str(e)}")


@router.post("/security/pii/detect")
async def detect_pii(
    request: PIIDetectRequest,
) -> dict[str, Any]:
    """Detect PII entities in text without redacting.

    Scans text and returns detected PII entities with their types,
    confidence scores, and positions. Useful for preview before redaction.
    """
    try:
        redactor = _get_pii_redactor()
        result = redactor.detect(text=request.text)

        return {
            "success": True,
            "data": result,
            "message": f"Detected {result['entity_count']} PII entities",
        }

    except Exception as e:
        logger.exception("PII detection failed")
        raise HTTPException(status_code=500, detail=f"PII detection failed: {str(e)}")


@router.post("/security/pii/redact/batch")
async def batch_redact_pii(
    request: PIIBatchRedactRequest,
) -> dict[str, Any]:
    """Batch redact PII from multiple texts.

    More efficient than individual calls for multiple texts.
    Maximum 100 texts per batch.
    """
    try:
        redactor = _get_pii_redactor()
        results = redactor.batch_redact(
            texts=request.texts,
            strategy=request.strategy,
        )

        total_entities = sum(r["entity_count"] for r in results)

        return {
            "success": True,
            "data": {
                "results": results,
                "count": len(results),
                "total_entities": total_entities,
            },
            "message": f"Redacted {total_entities} PII entities across {len(results)} texts",
        }

    except Exception as e:
        logger.exception("Batch PII redaction failed")
        raise HTTPException(
            status_code=500, detail=f"Batch PII redaction failed: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════
# Heatmap Endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/heatmap/query-scores")
async def get_heatmap_query_scores(
    n_queries: int = Query(
        50, ge=1, le=500, description="Number of recent queries to analyze"
    ),
    start_date: Optional[str] = Query(
        None, description="ISO date filter start (inclusive), e.g. 2026-01-01"
    ),
    end_date: Optional[str] = Query(
        None, description="ISO date filter end (inclusive), e.g. 2026-06-30"
    ),
    method: Optional[str] = Query(
        None,
        description="Filter by retrieval method (dense, sparse, graph, hyde, metadata)",
    ),
) -> dict[str, Any]:
    """Get query-level score distribution data for the relevance heatmap.

    Aggregates recent retrieval outcomes from the quality log and returns
    score distributions bucketed by relevance tiers, plus per-query
    performance stats. Supports optional date range and method filtering.
    """
    try:
        log = _get_learning_instance("quality_log")
        recent = await log.get_recent(n=n_queries)

        # Apply date range filter
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date).replace(
                    tzinfo=timezone.utc
                )
                recent = [
                    o
                    for o in recent
                    if hasattr(o, "timestamp")
                    and o.timestamp
                    and o.timestamp >= start_dt
                ]
            except (ValueError, TypeError):
                pass

        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date).replace(
                    hour=23, minute=59, second=59, tzinfo=timezone.utc
                )
                recent = [
                    o
                    for o in recent
                    if hasattr(o, "timestamp") and o.timestamp and o.timestamp <= end_dt
                ]
            except (ValueError, TypeError):
                pass

        # Apply method filter
        if method and method.lower() != "all":
            method_lower = method.lower()
            recent = [
                o
                for o in recent
                if hasattr(o, "methods_used")
                and o.methods_used
                and any(m.lower() == method_lower for m in o.methods_used)
            ]

        # Build score distribution across 5 bands
        bands = [
            {"label": "0.9-1.0", "min": 0.9, "count": 0},
            {"label": "0.75-0.9", "min": 0.75, "count": 0},
            {"label": "0.6-0.75", "min": 0.6, "count": 0},
            {"label": "0.4-0.6", "min": 0.4, "count": 0},
            {"label": "0.0-0.4", "min": 0.0, "count": 0},
        ]

        query_records = []
        scores = []
        for outcome in recent:
            # Use precision as the primary score if available, else user_rating
            score = None
            if hasattr(outcome, "precision") and outcome.precision is not None:
                score = outcome.precision
            elif hasattr(outcome, "user_rating") and outcome.user_rating is not None:
                score = outcome.user_rating

            if score is not None:
                scores.append(score)
                for b in bands:
                    if score >= b["min"]:
                        b["count"] += 1
                        break

                query_records.append(
                    {
                        "query": outcome.query[:80]
                        if hasattr(outcome, "query")
                        else "",
                        "score": score,
                        "result_count": outcome.result_count
                        if hasattr(outcome, "result_count")
                        else 0,
                        "latency_ms": outcome.latency_ms
                        if hasattr(outcome, "latency_ms")
                        else 0.0,
                        "methods_used": outcome.methods_used
                        if hasattr(outcome, "methods_used")
                        else [],
                        "error": outcome.error if hasattr(outcome, "error") else None,
                    }
                )

        avg_score = sum(scores) / len(scores) if scores else 0
        sorted_scores = sorted(scores)
        median_score = sorted_scores[len(sorted_scores) // 2] if sorted_scores else 0

        # Method performance breakdown
        method_perf = (
            await log.get_method_performance()
            if hasattr(log, "get_method_performance")
            else {}
        )

        return {
            "success": True,
            "data": {
                "distribution": bands,
                "total_queries": len(scores),
                "avg_score": round(avg_score, 4),
                "median_score": round(median_score, 4),
                "high_count": sum(b["count"] for b in bands if b["min"] >= 0.75),
                "recent_queries": query_records[-20:],  # Last 20 for detail view
                "method_performance": method_perf,
            },
            "message": f"Heatmap data for {len(scores)} queries",
        }

    except Exception as e:
        logger.exception("Failed to get heatmap query scores")
        raise HTTPException(
            status_code=500, detail=f"Failed to get heatmap data: {str(e)}"
        )


@router.get("/heatmap/document-stats")
async def get_heatmap_document_stats(
    limit: int = Query(
        50, ge=1, le=200, description="Number of top documents to return"
    ),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get per-document retrieval statistics for the relevance heatmap.

    Computes how often each document is retrieved, average relevance
    score, and retrieval frequency trends based on stored chunk data
    and quality log interactions.
    """
    try:
        # Fetch all chunks from DB
        records = session.exec(select(KnowledgeChunkRecord)).all()

        # Group by source_id (document)
        doc_groups: dict[str, dict[str, Any]] = {}
        for rec in records:
            source_id = rec.source_id or "unknown"
            if source_id not in doc_groups:
                doc_groups[source_id] = {
                    "document_id": source_id,
                    "chunk_count": 0,
                    "total_chunks": 0,
                    "source_type": rec.source_type or "text",
                    "domain": rec.domain or "",
                    "avg_score": 0.0,
                    "retrieval_count": 0,
                    "last_retrieved": None,
                    "topics": list(set(rec.topics or [])),
                }
            doc_groups[source_id]["total_chunks"] += 1
            doc_groups[source_id]["chunk_count"] += 1

            # Collect unique topics across chunks
            if rec.topics:
                existing = set(doc_groups[source_id]["topics"])
                existing.update(rec.topics)
                doc_groups[source_id]["topics"] = list(existing)

        # Try to enrich with quality log data
        try:
            log = _get_learning_instance("quality_log")
            recent = await log.get_recent(n=200)
            source_query_count: dict[str, int] = {}
            for outcome in recent:
                methods = (
                    outcome.methods_used if hasattr(outcome, "methods_used") else []
                )
                # Count source mentions from query context
                query_text = outcome.query if hasattr(outcome, "query") else ""
                for src_id in doc_groups:
                    if src_id.lower() in query_text.lower():
                        source_query_count[src_id] = (
                            source_query_count.get(src_id, 0) + 1
                        )

            for src_id, count in source_query_count.items():
                if src_id in doc_groups:
                    doc_groups[src_id]["retrieval_count"] = count

        except Exception:
            pass

        # Calculate an estimated avg score based on chunk metadata
        for src_id, info in doc_groups.items():
            # Score estimation: use retrieval count as a proxy for relevance
            retrieval_rate = info["retrieval_count"] / max(1, len(records))
            info["avg_score"] = round(min(1.0, 0.5 + retrieval_rate * 5), 4)

        # Sort by retrieval count descending
        sorted_docs = sorted(
            doc_groups.values(),
            key=lambda d: (d["retrieval_count"], d["chunk_count"]),
            reverse=True,
        )

        return {
            "success": True,
            "data": {
                "documents": sorted_docs[:limit],
                "total_documents": len(doc_groups),
                "total_chunks": len(records),
            },
            "message": f"Stats for {min(limit, len(sorted_docs))} documents",
        }

    except Exception as e:
        logger.exception("Failed to get document stats")
        raise HTTPException(
            status_code=500, detail=f"Failed to get document stats: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════
# PII Scan History Endpoints (thin routing — logic in common_lib)
# ═══════════════════════════════════════════════════════════════════


class PIIScanHistoryQueryParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    mode: Optional[str] = Field(None, description="Filter by mode: detect or redact")
    has_pii: Optional[bool] = Field(None, description="Filter by PII presence")
    batch_id: Optional[str] = Field(None, description="Filter by batch upload ID")
    source_filename: Optional[str] = Field(
        None, description="Filter by source filename"
    )


@router.get("/security/pii/scans")
async def list_pii_scans(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    mode: Optional[str] = Query(None, description="Filter: detect or redact"),
    has_pii: Optional[bool] = Query(None, description="Filter by PII found"),
    batch_id: Optional[str] = Query(None),
    source_filename: Optional[str] = Query(None),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List PII scan history with optional filters.

    All business logic delegated to common_lib.
    """
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            get_pii_scan_history,
        )

        records, total = get_pii_scan_history(
            session=session,
            limit=limit,
            offset=offset,
            mode=mode,
            has_pii=has_pii,
            batch_id=batch_id,
            source_filename=source_filename,
        )

        return {
            "success": True,
            "data": {
                "scans": [
                    {
                        "scan_id": r.scan_id,
                        "text_length": r.text_length,
                        "mode": r.mode,
                        "strategy": r.strategy,
                        "has_pii": r.has_pii,
                        "entity_count": r.entity_count,
                        "entity_type_counts": r.entity_type_counts,
                        "batch_id": r.batch_id,
                        "batch_line": r.batch_line,
                        "source_filename": r.source_filename,
                        "created_at": r.created_at.isoformat()
                        if r.created_at
                        else None,
                    }
                    for r in records
                ],
                "total": total,
                "limit": limit,
                "offset": offset,
            },
            "message": f"Found {total} PII scan records",
        }
    except Exception as e:
        logger.exception("Failed to list PII scans")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/security/pii/scans/stats")
async def get_pii_scan_stats(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get aggregate PII scan statistics.

    All business logic delegated to common_lib.
    """
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            get_pii_scan_stats,
        )

        stats = get_pii_scan_stats(session=session)
        return {
            "success": True,
            "data": stats,
            "message": f"{stats['total_scans']} total scans, {stats['scans_with_pii']} with PII",
        }
    except Exception as e:
        logger.exception("Failed to get PII scan stats")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/security/pii/scans/{scan_id}")
async def delete_pii_scan(
    scan_id: str = Path(..., description="Scan ID to delete"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete a single PII scan record.

    All business logic delegated to common_lib.
    """
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            PIIScanHistoryService,
        )

        service = PIIScanHistoryService(session)
        deleted = service.delete_scan(scan_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
        return {
            "success": True,
            "data": {"scan_id": scan_id},
            "message": "Scan record deleted",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete PII scan")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/security/pii/scans")
async def clear_pii_scan_history(
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Clear all PII scan history.

    All business logic delegated to common_lib.
    """
    try:
        from common_lib.modules.knowledge_engine.security.pii_scan_history import (
            PIIScanHistoryService,
        )

        service = PIIScanHistoryService(session)
        deleted = service.clear_history()
        return {
            "success": True,
            "data": {"deleted": deleted},
            "message": f"Cleared {deleted} scan records",
        }
    except Exception as e:
        logger.exception("Failed to clear PII scan history")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# NER Training Endpoints (thin routing — logic in common_lib)
# ═══════════════════════════════════════════════════════════════════


class NERTrainRequest(BaseModel):
    """Request body for NER model training."""

    examples: list[dict[str, Any]] = Field(
        ..., description="Training examples with text and entities"
    )
    entity_types: Optional[list[str]] = Field(
        None, description="Custom entity types to train"
    )
    output_dir: Optional[str] = Field(None, description="Model output directory")
    n_iter: int = Field(default=100, ge=10, le=1000, description="Training iterations")
    model_name: str = Field(default="en_core_web_sm", description="Base spaCy model")


@router.post("/nlp/ner/train")
async def train_ner_model_endpoint(
    request: NERTrainRequest,
) -> dict[str, Any]:
    """Train a custom NER model with labeled examples.

    All business logic delegated to common_lib. spaCy must be
    installed on the server for real training; without it, a
    simulated result with instructions is returned.
    """
    try:
        from common_lib.modules.knowledge_engine.nlp.ner_trainer import (
            NERTrainingPipeline,
            NERTrainingExample,
        )

        # Validate examples
        valid_examples = []
        for ex in request.examples:
            if "text" not in ex or "entities" not in ex:
                continue
            valid_examples.append(
                NERTrainingExample(
                    text=ex["text"],
                    entities=ex["entities"],
                )
            )

        if not valid_examples:
            raise HTTPException(
                status_code=400,
                detail="No valid training examples provided. Each example needs 'text' and 'entities'.",
            )

        pipeline = NERTrainingPipeline(
            entity_types=request.entity_types,
            model_name=request.model_name,
        )

        result = pipeline.train(
            examples=valid_examples,
            output_dir=request.output_dir,
            n_iter=request.n_iter,
        )

        return {
            "success": result.success,
            "data": {
                "model_path": result.model_path,
                "entity_types": result.entity_types,
                "num_examples": result.num_examples,
                "num_epochs": result.num_epochs,
                "training_time_seconds": result.training_time_seconds,
                "metrics": result.metrics,
                "created_at": result.created_at,
            },
            "message": f"NER model trained ({result.num_examples} examples, {result.num_epochs} epochs)"
            if result.success
            else f"Training failed: {result.error}",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("NER training failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/nlp/ner/entity-types")
async def list_ner_entity_types() -> dict[str, Any]:
    """List all configurable NER entity types with descriptions.

    All business logic delegated to common_lib.
    """
    try:
        from common_lib.modules.knowledge_engine.nlp.ner_trainer import (
            NERTrainingPipeline,
        )

        types = NERTrainingPipeline.get_entity_types_config()
        return {
            "success": True,
            "data": {
                "entity_types": types,
                "count": len(types),
            },
            "message": f"{len(types)} entity types available",
        }
    except Exception as e:
        logger.exception("Failed to list NER entity types")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# POST /learning/beliefs/prune
# ═══════════════════════════════════════════════════════════════════


@router.post("/learning/beliefs/prune")
async def prune_beliefs(
    min_confidence: float = Query(
        0.3, ge=0.0, le=1.0, description="Minimum confidence to retain"
    ),
) -> dict[str, Any]:
    """Prune low-confidence beliefs.

    Removes beliefs with confidence below the threshold,
    keeping only well-established knowledge.
    """
    try:
        reviser = _get_learning_instance("belief_reviser")
        pruned = await reviser.prune_low_confidence(min_confidence=min_confidence)
        remaining = await reviser.get_all_beliefs()

        return {
            "success": True,
            "data": {
                "pruned": pruned,
                "remaining": len(remaining),
            },
            "message": f"Pruned {pruned} low-confidence beliefs",
        }

    except Exception as e:
        logger.exception("Failed to prune beliefs")
        raise HTTPException(
            status_code=500, detail=f"Failed to prune beliefs: {str(e)}"
        )
