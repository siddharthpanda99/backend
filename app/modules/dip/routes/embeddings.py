from fastapi import APIRouter, Depends, Query
from typing import List, Dict, Any

router = APIRouter(prefix="/dip/embeddings", tags=["dip/embeddings"])

@router.get("/models")
async def list_embedding_models():
    """List available and active embedding models."""
    return {
        "data": [
            {"id": "text-embedding-3-small", "provider": "openai", "dims": 1536, "status": "active"},
            {"id": "bge-large-en-v1.5", "provider": "local", "dims": 1024, "status": "active"},
            {"id": "clip-vit-b-32", "provider": "local", "dims": 512, "status": "idle"}
        ]
    }

@router.get("/queues")
async def get_embedding_queues():
    """Get status of the asynchronous embedding processing queues."""
    return {
        "data": {
            "pending_tasks": 0,
            "failed_tasks": 12,
            "processed_today": 4500,
            "status": "clear"
        }
    }

@router.get("/metrics")
async def get_embedding_metrics():
    """Get embedding generation performance metrics."""
    return {
        "data": {
            "avg_generation_time_ms": 22,
            "throughput_per_sec": 45,
            "error_rate": 0.001
        }
    }
