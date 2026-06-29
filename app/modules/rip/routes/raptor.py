"""RIP RAPTOR routes — Recursive Abstractive Processing tree.

Uses the RAPTOR connector for real tree building and retrieval.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_synthesis.schemas import (
    RAPTORBuildRequest,
    RAPTORRetrieveRequest,
)
from common_lib.modules.rip.rip_synthesis.service import (
    get_raptor_tree,
    store_raptor_tree,
)

router = APIRouter(prefix="/rip/raptor", tags=["RIP — RAPTOR"])


@router.post("/build")
async def build_raptor_tree(payload: RAPTORBuildRequest):
    """Build a RAPTOR hierarchical summary tree from chunks.

    Uses the RAPTOR connector for real tree building.
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_raptor_build_fn
        import uuid
        import time

        start = time.perf_counter()
        build_fn = await create_raptor_build_fn(
            max_levels=payload.max_levels,
            summary_max_tokens=payload.summary_max_tokens,
        )
        tree = await build_fn(chunks=payload.chunks)
        elapsed = (time.perf_counter() - start) * 1000

        tree_id = f"raptor_{uuid.uuid4().hex[:8]}"
        store_raptor_tree(tree_id, tree)

        stats = tree.get_stats()
        return {
            "tree_id": tree_id,
            "stats": stats,
            "total_nodes": stats.get("total_nodes", 0),
            "levels": stats.get("levels", 0),
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrieve")
async def retrieve_from_raptor(payload: RAPTORRetrieveRequest):
    """Retrieve from a RAPTOR tree at specified levels.

    Uses the RAPTOR connector for real tree retrieval.
    """
    try:
        if get_raptor_tree(payload.tree_id) is None:
            raise HTTPException(
                status_code=404, detail=f"RAPTOR tree '{payload.tree_id}' not found"
            )

        from common_lib.modules.rip.rip_connectors import create_raptor_query_fn
        import time

        start = time.perf_counter()
        query_fn = create_raptor_query_fn()
        tree = get_raptor_tree(payload.tree_id)
        results = await query_fn(
            tree=tree,
            query=payload.query,
            top_k=payload.top_k,
            levels=payload.levels,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "tree_id": payload.tree_id,
            "results": results,
            "total_results": len(results),
            "levels_queried": payload.levels or "all",
            "latency_ms": elapsed,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
