"""TurboVec management API routes.

Provides endpoints for inspecting the TurboVec vector store backend:
status, stats, search diagnostics, and backend switching.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from common_lib.modules.memory.service import MemoryService as CognitiveMemoryService
from common_lib.vectorstores.factory import VectorStoreFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vectorstores", tags=["Vector Stores"])


def _get_memory_service() -> Optional[CognitiveMemoryService]:
    try:
        from common_lib.modules.memory.service import get_memory_service as _gms

        return _gms()
    except Exception:
        return None


def _get_turbovec_adapter():
    svc = _get_memory_service()
    if svc and hasattr(svc, "turbovec_adapter") and svc.turbovec_adapter:
        return svc.turbovec_adapter
    return None


@router.get("/turbovec/status")
async def turbovec_status():
    """Get TurboVec backend status and health."""
    adapter = _get_turbovec_adapter()
    if not adapter:
        return {
            "available": False,
            "message": "TurboVec adapter not initialized. Set VECTOR_BACKEND=turbovec and ensure pip install turbovec.",
        }
    try:
        healthy = await adapter.health_check()
        stats = await adapter.get_stats()
        return {"available": True, "healthy": healthy, **stats}
    except Exception as e:
        return {"available": True, "healthy": False, "error": str(e)}


@router.get("/turbovec/stats")
async def turbovec_stats():
    """Get detailed TurboVec index statistics."""
    adapter = _get_turbovec_adapter()
    if not adapter:
        raise HTTPException(status_code=404, detail="TurboVec not configured")
    try:
        return await adapter.get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/turbovec/count")
async def turbovec_count():
    """Get document count in TurboVec index."""
    adapter = _get_turbovec_adapter()
    if not adapter:
        return {"count": 0, "available": False}
    try:
        count = await adapter.count()
        return {"count": count, "available": True}
    except Exception as e:
        return {"count": 0, "available": False, "error": str(e)}


@router.post("/turbovec/rebuild")
async def turbovec_rebuild():
    """Rebuild the TurboVec index from scratch."""
    adapter = _get_turbovec_adapter()
    if not adapter:
        raise HTTPException(status_code=404, detail="TurboVec not configured")
    try:
        if hasattr(adapter, "_initialize_index"):
            adapter._initialize_index()
            return {"status": "rebuilt", "message": "TurboVec index reinitialized"}
        return {"status": "skipped", "message": "Rebuild not supported by this adapter"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/backends")
async def list_backends():
    """List all registered vector backends and their availability."""
    backends = [
        {
            "name": "turbovec",
            "available": _get_turbovec_adapter() is not None,
            "description": "2-bit quantized compressed vector search (16x compression)",
        },
        {
            "name": "pgvector",
            "available": True,
            "description": "PostgreSQL pgvector extension (existing backend)",
        },
    ]
    cfg = {
        "VECTOR_BACKEND": os.getenv("VECTOR_BACKEND", "auto"),
        "EMBEDDING_DIMENSION": int(os.getenv("EMBEDDING_DIMENSION", "768")),
        "TURBOVEC_INDEX_PATH": os.getenv("TURBOVEC_INDEX_PATH", "/data/turbovec"),
        "TURBOVEC_BIT_WIDTH": int(os.getenv("TURBOVEC_BIT_WIDTH", "2")),
    }
    return {"backends": backends, "config": cfg}
