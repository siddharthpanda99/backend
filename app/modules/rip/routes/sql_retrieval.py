"""RIP SQL Retrieval routes — Text-to-SQL and metadata filtering.

Uses the Filter connector for real pre_filter/post_filter/hybrid_filter strategies.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_retrieval.schemas import (
    TextToSQLRequest,
    MetadataFilterRequest,
)

router = APIRouter(prefix="/rip/sql", tags=["RIP — SQL Retrieval"])


@router.post("/text-to-sql")
async def text_to_sql(payload: TextToSQLRequest):
    """Convert natural language to SQL and execute against the schema."""
    try:
        from common_lib.modules.rip.rip_retrieval.sql_retrieval import (
            text_to_sql as _t2s,
        )
        import time

        start = time.perf_counter()
        result = await _t2s(
            query=payload.query,
            schema=payload.schema or {},
            top_k=payload.top_k,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "sql": result.get("sql", ""),
            "results": result.get("results", []),
            "columns": result.get("columns", []),
            "total_results": result.get("total_results", 0),
            "execution_time_ms": result.get("execution_time_ms", 0),
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metadata-filter")
async def metadata_filter_search(payload: MetadataFilterRequest):
    """Search with metadata filtering.

    Strategies:
      - pre_filter: Filter before ANN (query-building)
      - post_filter: Filter after ANN (prune ranked results)
      - hybrid_filter: Pre-filter first, post-filter fallback for low results
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_filter_fn
        from common_lib.modules.rip.rip_retrieval.sql_retrieval import (
            metadata_filter_retrieve,
        )
        import time

        start = time.perf_counter()

        # First retrieve candidates
        raw_results = await metadata_filter_retrieve(
            query=payload.query,
            metadata_filters=payload.filters,
            top_k=payload.top_k * 2,
            tenant_id=payload.tenant_id,
        )

        # Then apply filter connector for refined strategy
        filter_fn = create_filter_fn(strategy=payload.strategy)
        results = await filter_fn(
            results=list(raw_results) if raw_results else [],
            filters=payload.filters,
            strategy=payload.strategy,
            min_results=payload.min_results,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "results": results[: payload.top_k],
            "total_results": len(results),
            "filters_applied": payload.filters,
            "strategy": payload.strategy,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
