"""RIP Cache routes — Cache statistics and management.

Implements endpoints 11.29–11.30 from the implementation tracker.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from common_lib.modules.rip.rip_cache.schemas import (
    CacheStatsRequest,
    CacheStatsResponse,
    CacheClearRequest,
)

router = APIRouter(prefix="/rip/cache", tags=["RIP — Cache"])


@router.get("/stats", response_model=CacheStatsResponse)
async def cache_stats():
    """Get cache statistics — entry count, hit rate, memory usage, breakdown by type."""
    try:
        from common_lib.modules.rip.rip_cache.service import get_cache_stats

        stats = await get_cache_stats()
        return CacheStatsResponse(
            entries=stats.get("entries", 0),
            hit_rate=stats.get("hit_rate", 0.0),
            memory_usage_bytes=stats.get("memory_usage_bytes", 0),
            by_type=stats.get("by_type", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{cache_key}")
async def clear_cache_entry(
    cache_key: str,
    cache_type: Optional[str] = Query(None),
    tenant_id: Optional[str] = Query(None),
):
    """Clear a specific cache entry or all entries of a type."""
    try:
        from common_lib.modules.rip.rip_cache.service import clear_cache

        cleared = await clear_cache(
            cache_key=cache_key,
            cache_type=cache_type,
            tenant_id=tenant_id,
        )
        return {"cleared": cleared, "cache_key": cache_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
