"""RIP Unified ETL Routes — FastAPI endpoints for unified pipeline orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from common_lib.modules.rip.rip_etl.orchestrator import UnifiedETLPipeline
from common_lib.modules.rip.rip_etl.presets import (
    list_unified_presets,
    get_unified_preset,
)
from common_lib.modules.rip.rip_etl.variants import (
    list_unified_variants,
    get_unified_variant,
)
from common_lib.modules.rip.rip_etl.comparison import get_comparison_engine
from common_lib.modules.rip.rip_etl.schemas import (
    UnifiedPipelineConfig,
    ExtractionSource,
    TargetConfig,
    ProcessingConfig,
    ChunkingConfig,
    EntityExtractionConfig,
    EmbeddingConfig,
    PIIConfig,
    DedupConfig,
    SourceType,
    TargetType,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/etl/unified", tags=["rip-etl-unified"])


# ── Schemas ────────────────────────────────────────────────────────


class CreateUnifiedPipelineBody(BaseModel):
    name: str
    description: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    processing: dict[str, Any] = Field(default_factory=dict)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ExecuteUnifiedBody(BaseModel):
    pipeline_id: str = ""
    preset_name: str = ""
    sources: list[dict[str, Any]] = Field(default_factory=list)
    processing: dict[str, Any] = Field(default_factory=dict)
    targets: list[dict[str, Any]] = Field(default_factory=list)


class PreviewBody(BaseModel):
    sources: list[dict[str, Any]]
    processing: dict[str, Any] = {}


class SourceListingBody(BaseModel):
    source_type: str = "chat_history"
    config: dict[str, Any] = {}


class CompareBody(BaseModel):
    variant_ids: list[str] = Field(default_factory=list)


# ── In-memory stores ────────────────────────────────────────────────

_UNIFIED_PIPELINES: dict[str, dict[str, Any]] = {}
_PIPELINE_RUNS: dict[str, dict[str, Any]] = {}


def _get_pipeline_config(
    body: CreateUnifiedPipelineBody | ExecuteUnifiedBody,
) -> UnifiedPipelineConfig:
    """Convert dict-based body to UnifiedPipelineConfig."""
    sources = []
    for s in body.sources:
        src = ExtractionSource(
            source_type=SourceType(s.get("source_type", "document")),
            source_id=s.get("source_id", ""),
            chat_config=s.get("chat_config"),
            memory_config=s.get("memory_config"),
            kb_config=s.get("kb_config"),
            document_path=s.get("document_path"),
        )
        sources.append(src)

    targets = []
    for t in body.targets:
        tgt = TargetConfig(
            target_type=TargetType(t.get("target_type", "knowledgebase")),
            enabled=t.get("enabled", True),
            memory_type=t.get("memory_type"),
        )
        targets.append(tgt)

    proc_dict = body.processing
    processing = ProcessingConfig(
        chunking=ChunkingConfig(**proc_dict.get("chunking", {})),
        entity_extraction=EntityExtractionConfig(
            **proc_dict.get("entity_extraction", {})
        ),
        embedding=EmbeddingConfig(**proc_dict.get("embedding", {})),
        pii=PIIConfig(**proc_dict.get("pii", {})),
        dedup=DedupConfig(**proc_dict.get("dedup", {})),
    )

    return UnifiedPipelineConfig(
        sources=sources,
        processing=processing,
        targets=targets,
    )


# ── Preset Management ──────────────────────────────────────────────


@router.get("/presets")
async def list_presets():
    presets = list_unified_presets()
    return {"items": presets, "total": len(presets)}


@router.get("/presets/{preset_name}")
async def get_preset_detail(preset_name: str):
    p = get_unified_preset(preset_name)
    if not p:
        raise HTTPException(404, "Preset not found")
    return p


# ── Variant Management ──────────────────────────────────────────────


@router.get("/variants")
async def list_variants():
    variants = list_unified_variants()
    return {"items": variants, "total": len(variants)}


@router.get("/variants/{variant_id}")
async def get_variant_detail(variant_id: str):
    v = get_unified_variant(variant_id)
    if not v:
        raise HTTPException(404, "Variant not found")
    return v


# ── Pipeline CRUD ──────────────────────────────────────────────────


@router.get("/pipelines")
async def list_pipelines():
    items = list(_UNIFIED_PIPELINES.values())
    return {"items": items, "total": len(items)}


@router.post("/pipelines")
async def create_pipeline(body: CreateUnifiedPipelineBody):
    pipeline_id = f"up_{uuid.uuid4().hex[:12]}"
    config = _get_pipeline_config(body)

    pipeline = {
        "id": pipeline_id,
        "name": body.name,
        "description": body.description,
        "config": config.model_dump(),
        "tags": body.tags,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    _UNIFIED_PIPELINES[pipeline_id] = pipeline
    return pipeline


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    p = _UNIFIED_PIPELINES.get(pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")
    return p


@router.put("/pipelines/{pipeline_id}")
async def update_pipeline(pipeline_id: str, body: CreateUnifiedPipelineBody):
    p = _UNIFIED_PIPELINES.get(pipeline_id)
    if not p:
        raise HTTPException(404, "Pipeline not found")

    config = _get_pipeline_config(body)
    p["name"] = body.name
    p["description"] = body.description
    p["config"] = config.model_dump()
    p["tags"] = body.tags
    p["updated_at"] = time.time()
    return p


@router.delete("/pipelines/{pipeline_id}")
async def delete_pipeline(pipeline_id: str):
    if pipeline_id not in _UNIFIED_PIPELINES:
        raise HTTPException(404, "Pipeline not found")
    del _UNIFIED_PIPELINES[pipeline_id]
    return {"deleted": True}


# ── Execute ────────────────────────────────────────────────────────


@router.post("/execute")
async def execute_pipeline(body: ExecuteUnifiedBody):
    """Execute a unified pipeline from config or preset."""
    run_id = f"urun_{uuid.uuid4().hex[:12]}"

    if body.preset_name:
        preset = get_unified_preset(body.preset_name)
        if not preset:
            raise HTTPException(404, f"Preset '{body.preset_name}' not found")
        config = _get_pipeline_config(
            CreateUnifiedPipelineBody(
                name=preset["name"],
                sources=preset["sources"],
                processing=preset["processing"],
                targets=preset["targets"],
            )
        )
    elif body.pipeline_id:
        p = _UNIFIED_PIPELINES.get(body.pipeline_id)
        if not p:
            raise HTTPException(404, "Pipeline not found")
        config = UnifiedPipelineConfig(**p["config"])
    else:
        config = _get_pipeline_config(body)

    _PIPELINE_RUNS[run_id] = {"status": "running", "started_at": time.time()}

    pipeline = UnifiedETLPipeline(config)
    result = await pipeline.run()

    _PIPELINE_RUNS[run_id] = {
        "status": result.status,
        "result": {
            "run_id": result.run_id,
            "status": result.status,
            "source_stats": result.source_stats,
            "target_stats": result.target_stats,
            "timing": result.timing,
            "errors": result.errors,
            "total_chunks": result.total_chunks,
            "total_entities": result.total_entities,
            "total_embeddings": result.total_embeddings,
        },
    }

    return _PIPELINE_RUNS[run_id]["result"]


# ── SSE Streaming ──────────────────────────────────────────────────


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """SSE stream for real-time pipeline progress."""

    async def event_generator():
        while True:
            run_data = _PIPELINE_RUNS.get(run_id)
            if not run_data:
                yield f"data: {json.dumps({'error': 'Run not found'})}\n\n"
                break

            yield f"data: {json.dumps({'status': run_data['status']})}\n\n"

            if run_data["status"] in ("completed", "error"):
                yield f"data: {json.dumps(run_data.get('result', {}))}\n\n"
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── Source Preview ──────────────────────────────────────────────────


@router.post("/preview")
async def preview_pipeline(body: PreviewBody):
    """Preview extraction without full processing."""
    config = _get_pipeline_config(
        CreateUnifiedPipelineBody(
            sources=body.sources,
            processing=body.processing,
        )
    )
    pipeline = UnifiedETLPipeline(config)
    preview = await pipeline.preview()

    return {
        "total_chunks": preview["total_chunks"],
        "total_sources": preview["total_sources"],
        "total_documents": preview["total_documents"],
        "sample_chunks": [
            {
                "chunk_id": c.chunk_id,
                "content": c.content[:200] + "..."
                if len(c.content) > 200
                else c.content,
                "source": c.source_id,
                "metadata": c.metadata,
            }
            for c in preview.get("sample_chunks", [])[:10]
        ],
    }


@router.post("/sources/chat-history/preview")
async def preview_chat_history(body: SourceListingBody):
    """Preview chat history extraction."""
    config = _get_pipeline_config(
        CreateUnifiedPipelineBody(
            sources=[
                {
                    "source_type": "chat_history",
                    "source_id": body.source_id if hasattr(body, "source_id") else "",
                    "chat_config": body.config,
                }
            ],
        )
    )
    pipeline = UnifiedETLPipeline(config)
    preview = await pipeline.preview()
    return {
        "source_type": "chat_history",
        "total_chunks": preview["total_chunks"],
        "sample_chunks": [
            {"content": c.content[:150], "metadata": c.metadata}
            for c in preview.get("sample_chunks", [])[:5]
        ],
    }


@router.post("/sources/memory/preview")
async def preview_memory(body: SourceListingBody):
    """Preview memory extraction."""
    config = _get_pipeline_config(
        CreateUnifiedPipelineBody(
            sources=[
                {
                    "source_type": "memory",
                    "source_id": body.source_id if hasattr(body, "source_id") else "",
                    "memory_config": body.config,
                }
            ],
        )
    )
    pipeline = UnifiedETLPipeline(config)
    preview = await pipeline.preview()
    return {
        "source_type": "memory",
        "total_chunks": preview["total_chunks"],
        "sample_chunks": [
            {"content": c.content[:150], "metadata": c.metadata}
            for c in preview.get("sample_chunks", [])[:5]
        ],
    }


@router.post("/sources/knowledgebase/preview")
async def preview_knowledgebase(body: SourceListingBody):
    """Preview knowledgebase extraction."""
    config = _get_pipeline_config(
        CreateUnifiedPipelineBody(
            sources=[
                {
                    "source_type": "knowledgebase",
                    "source_id": body.source_id if hasattr(body, "source_id") else "",
                }
            ],
        )
    )
    pipeline = UnifiedETLPipeline(config)
    preview = await pipeline.preview()
    return {
        "source_type": "knowledgebase",
        "total_chunks": preview["total_chunks"],
        "sample_chunks": [
            {"content": c.content[:150], "metadata": c.metadata}
            for c in preview.get("sample_chunks", [])[:5]
        ],
    }


# ── Source Listing ─────────────────────────────────────────────────


@router.post("/sources")
async def list_sources(body: SourceListingBody):
    """List available items from a source type."""
    source_type = SourceType(body.source_type)

    if source_type == SourceType.CHAT_HISTORY:
        try:
            from common_lib.modules.agents.session_service import SessionService

            svc = SessionService()
            sessions = svc.list_sessions()
            return {
                "source_type": body.source_type,
                "items": [
                    {
                        "id": s.id,
                        "title": s.title,
                        "created_at": s.created_at,
                        "message_count": len(s.messages),
                    }
                    for s in sessions
                ],
            }
        except Exception as e:
            logger.warning("Failed to list chat sessions: %s", e)
            return {"source_type": body.source_type, "items": [], "error": str(e)}

    elif source_type == SourceType.MEMORY:
        try:
            from common_lib.modules.memory.service import MemoryService

            svc = MemoryService()
            results = svc.search(query="", limit=100)
            return {
                "source_type": body.source_type,
                "items": [
                    {
                        "id": m.id,
                        "content": m.content[:100],
                        "memory_type": m.memory_type,
                        "importance": m.importance,
                    }
                    for m in results
                ],
            }
        except Exception as e:
            logger.warning("Failed to list memories: %s", e)
            return {"source_type": body.source_type, "items": [], "error": str(e)}

    elif source_type == SourceType.KNOWLEDGEBASE:
        try:
            from common_lib.modules.knowledge_engine.service import (
                KnowledgeEngineService,
            )

            svc = KnowledgeEngineService()
            chunks = svc.list_chunks(limit=100)
            return {
                "source_type": body.source_type,
                "items": [
                    {"id": c.id, "title": c.title, "source_type": c.source_type}
                    for c in chunks
                ],
            }
        except Exception as e:
            logger.warning("Failed to list KB chunks: %s", e)
            return {"source_type": body.source_type, "items": [], "error": str(e)}

    else:
        return {"source_type": body.source_type, "items": []}


# ── Compare ────────────────────────────────────────────────────────


@router.post("/compare")
async def compare_variants(body: CompareBody):
    """Compare multiple unified variants on same data."""
    comp = get_comparison_engine()
    result = await comp.compare_unified(variant_ids=body.variant_ids or None)
    return result


# ── Capabilities ────────────────────────────────────────────────────


@router.get("/capabilities")
async def get_capabilities():
    """List available strategies, models, and options."""
    return {
        "source_types": [
            {
                "value": "chat_history",
                "label": "Chat History",
                "description": "Agent messages and conversations",
            },
            {
                "value": "memory",
                "label": "Memory",
                "description": "Episodic and semantic memories",
            },
            {
                "value": "knowledgebase",
                "label": "Knowledgebase",
                "description": "Existing KB chunks",
            },
            {
                "value": "document",
                "label": "Document",
                "description": "Raw files and URLs",
            },
            {
                "value": "connector",
                "label": "Connector",
                "description": "MCP/DIP connectors",
            },
        ],
        "target_types": [
            {
                "value": "knowledgebase",
                "label": "Knowledgebase",
                "description": "KB chunks with search index",
            },
            {
                "value": "memory",
                "label": "Memory",
                "description": "Long-term memory records",
            },
            {
                "value": "vector_index",
                "label": "Vector Index",
                "description": "pgvector/HNSW/IVF indices",
            },
            {
                "value": "graph",
                "label": "Graph",
                "description": "Entities, relationships, communities",
            },
        ],
        "chunking_strategies": [
            "auto",
            "semantic",
            "recursive",
            "fixed",
            "code",
            "hierarchical",
            "late",
            "single",
        ],
        "embedding_models": ["bge-m3", "bge-large", "minilm", "e5-large", "e5-small"],
        "entity_methods": ["hybrid", "llm", "spacy", "rule"],
        "pii_strategies": ["redact", "mask", "hash", "remove"],
        "dedup_strategies": ["content_hash", "embedding_cosine", "semantic"],
    }
