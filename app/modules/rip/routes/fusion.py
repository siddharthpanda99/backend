"""RIP Fusion routes — Result fusion (RRF, weighted, score, DBSF, min_max).

Provides a standalone fusion endpoint for combining multiple ranked lists.
Uses the fusion connector for real implementation of all 5 methods.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_fusion.schemas import FusionRequest

router = APIRouter(prefix="/rip", tags=["RIP — Fusion"])


@router.post("/fusion")
async def fuse_results(payload: FusionRequest):
    """Fuse multiple ranked result lists into a single ranking.

    Methods:
      - rrf: Reciprocal Rank Fusion (parameter-free, robust)
      - weighted: Min-max normalize + weighted score blending
      - score: Score normalization then weighted fusion
      - dbsf: Distribution-Based Score Fusion (z-score normalisation)
      - min_max: Min-max normalize then RRF
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_fusion_fn
        import time

        start = time.perf_counter()
        fusion_fn = create_fusion_fn()
        fused = await fusion_fn(
            result_lists=payload.results,
            method=payload.method,
            weights=payload.weights,
            top_k=payload.top_k,
            k=payload.k,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "results": fused,
            "count": len(fused),
            "method": payload.method,
            "input_lists": len(payload.results),
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
