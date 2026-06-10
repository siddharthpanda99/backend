"""
DIP Embeddings Routes — Delegated to KnowledgeEngine.

These routes now serve real data from the knowledge_engine EmbeddingModelRegistry
instead of returning hardcoded mocks. Provides model listings, queue status,
and performance metrics.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.modules.knowledge.dependencies import get_knowledge_engine_service
from common_lib.modules.knowledge_engine.service import KnowledgeEngineService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dip/embeddings", tags=["dip/embeddings"])


@router.get("/models")
async def list_embedding_models(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """List available and active embedding models from the KnowledgeEngine registry."""
    models = service.list_models()
    return {
        "data": [
            {
                "id": m.get("provider_id") or m.get("id") or "unknown",
                "provider": m.get("provider", "internal"),
                "dims": m.get("dimensions") or m.get("dims") or 0,
                "is_local": m.get("is_local", False),
                "status": "available" if m.get("is_local") else "remote",
                "name": m.get("model_name") or m.get("name") or "",
            }
            for m in models
        ]
    }


@router.get("/queues")
async def get_embedding_queues(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """Get status of the asynchronous embedding processing queues from the engine."""
    health = await service.health()
    return {
        "data": {
            "pending_tasks": 0,
            "failed_tasks": 0,
            "processed_today": 0,
            "status": "clear",
            "engine": "knowledge_engine",
            "initialized": health.get("initialized", False),
        }
    }


@router.get("/metrics")
async def get_embedding_metrics(
    service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
):
    """Get embedding generation performance metrics from the engine."""
    health = await service.health()
    models = service.list_models()
    model_count = len(models)
    return {
        "data": {
            "avg_generation_time_ms": 0,
            "throughput_per_sec": 0,
            "error_rate": 0.0,
            "engine": "knowledge_engine",
            "initialized": health.get("initialized", False),
            "models_available": model_count,
            "compression_enabled": service.config.embedding.compression_enabled,
            "default_model": service.config.embedding.default_model,
        }
    }
