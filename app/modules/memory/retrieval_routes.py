"""Memory Retrieval API Routes."""

import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Body

router = APIRouter(prefix="/retrieval", tags=["Memory Retrieval"])

logger = logging.getLogger(__name__)


@router.post("/search")
async def search(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_retrieval.service import (
            get_retrieval_service,
        )

        svc = get_retrieval_service()
        return await svc.search(**payload)
    except Exception as e:
        logger.error(f"Failed to search memories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/vector-search")
async def vector_search(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_retrieval.service import (
            get_retrieval_service,
        )

        svc = get_retrieval_service()
        return await svc.vector_search(**payload)
    except Exception as e:
        logger.error(f"Failed to vector search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rerank")
async def rerank(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_retrieval.service import (
            get_retrieval_service,
        )

        svc = get_retrieval_service()
        return await svc.rerank(**payload)
    except Exception as e:
        logger.error(f"Failed to rerank: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rewrite")
async def rewrite_query(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_retrieval.service import (
            get_retrieval_service,
        )

        svc = get_retrieval_service()
        return await svc.rewrite_query(**payload)
    except Exception as e:
        logger.error(f"Failed to rewrite query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hybrid")
async def hybrid_search(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_retrieval.service import (
            get_retrieval_service,
        )

        svc = get_retrieval_service()
        return await svc.hybrid_search(**payload)
    except Exception as e:
        logger.error(f"Failed to hybrid search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/negative-search")
async def negative_search(payload: Dict[str, Any] = Body(...)):
    try:
        from common_lib.modules.memory.memory_retrieval.service import (
            get_retrieval_service,
        )

        svc = get_retrieval_service()
        return await svc.negative_search(**payload)
    except Exception as e:
        logger.error(f"Failed to negative search: {e}")
        raise HTTPException(status_code=500, detail=str(e))
