"""RIP Context routes — Context assembly, compression, and ordering.

Uses the Context connector for real context assembly strategies:
standard, deduped, compressed, lost_in_middle.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_context.schemas import (
    ContextAssemblyRequest,
    DedupRequest,
)

router = APIRouter(prefix="/rip/context", tags=["RIP — Context"])


@router.post("/assemble")
async def assemble_context(payload: ContextAssemblyRequest):
    """Assemble, deduplicate, compress, and order retrieved chunks for LLM context.

    Strategies:
      - standard: Rank-order truncation
      - deduped: Deduplicate then truncate
      - compressed: Truncate to max_tokens with compression
      - lost_in_middle: Place best results at start and end
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_context_fn
        import time

        start = time.perf_counter()
        context_fn = create_context_fn(strategy=payload.strategy)
        result = await context_fn(
            results=payload.results,
            query=payload.query or "",
            max_tokens=payload.max_tokens,
            strategy=payload.strategy,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "context": result.get("context", ""),
            "used_tokens": result.get("used_tokens", 0),
            "num_chunks": result.get("num_chunks", 0),
            "strategy": payload.strategy,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dedup")
async def deduplicate_results(payload: DedupRequest):
    """Deduplicate retrieved results based on content similarity."""
    try:
        from common_lib.modules.rip.rip_context.context import (
            deduplicate_results as _dedup,
        )
        import time

        start = time.perf_counter()
        results = _dedup(
            payload.results,
            similarity_threshold=payload.similarity_threshold,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "original_count": len(payload.results),
            "deduped_count": len(results),
            "results": results,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
