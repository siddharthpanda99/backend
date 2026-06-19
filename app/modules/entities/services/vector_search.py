"""
Registry Search Service — App-level re-export.

All search/index logic lives in
``common_lib.modules.orchestration.registry.search``.

This module re-exports the public surface so that FastAPI route handlers
which already import from here continue to work with zero changes.

Any new code should import directly from common_lib::

    from common_lib.modules.orchestration.registry.search import get_search_service
"""

from common_lib.modules.orchestration.registry.search import (  # noqa: F401
    RegistrySearchService,
    SyncProgressTracker,
    get_search_service,
)

__all__ = ["RegistrySearchService", "SyncProgressTracker", "get_search_service"]
