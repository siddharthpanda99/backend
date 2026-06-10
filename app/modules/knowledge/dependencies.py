"""
Knowledge Engine — FastAPI Dependencies.

Provides the KnowledgeEngineService as a FastAPI dependency,
ensuring a single shared instance across all route handlers.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import AsyncGenerator

from common_lib.modules.knowledge_engine.service import KnowledgeEngineService

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_service_instance() -> KnowledgeEngineService:
    """Create or retrieve the singleton KnowledgeEngineService instance.

    Uses lru_cache to ensure only one instance is created.
    The service is lazily initialized — initialize() is called
    asynchronously on first use.
    """
    return KnowledgeEngineService()


async def get_knowledge_engine_service() -> AsyncGenerator[KnowledgeEngineService, None]:
    """FastAPI dependency that provides a shared KnowledgeEngineService.

    Usage in routes:
        @router.post("/retrieve")
        async def retrieve(
            request: RetrieveRequest,
            service: KnowledgeEngineService = Depends(get_knowledge_engine_service),
        ):
            result = await service.retrieve(request.query)
    """
    service = _get_service_instance()
    # Ensure initialized on first request (initialize() is idempotent)
    await service.initialize()
    yield service
