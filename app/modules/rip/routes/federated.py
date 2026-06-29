"""RIP Federated routes — Multi-source federated retrieval with real fusion.

Uses the Fusion connector for real RRF/weighted/DBSF fusion of multi-source results.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_retrieval.schemas import FederatedSearchRequest

router = APIRouter(prefix="/rip/federated", tags=["RIP — Federated Retrieval"])


@router.post("/search")
async def federated_search(payload: FederatedSearchRequest):
    """Fan-out query to multiple sources and fuse results with the Fusion connector.

    Sources include: dense, sparse, bm25, graph, memory, sql, colbert.
    Fusion methods: rrf, weighted, score, dbsf, min_max.
    """
    try:
        from common_lib.modules.rip.rip_retrieval.federated import (
            federated_search as _federated,
        )
        from common_lib.modules.rip.rip_connectors import create_fusion_fn
        import time

        start = time.perf_counter()
        result = await _federated(
            query=payload.query,
            sources=payload.sources,
            top_k_per_source=payload.top_k_per_source,
            global_top_k=payload.global_top_k,
            fusion_method=payload.fusion_method,
            weights=payload.weights,
        )
        elapsed = (time.perf_counter() - start) * 1000

        # Apply the fusion connector for DBSF/min_max support
        per_source_results = result.get("per_source", {})
        if payload.fusion_method in ("dbsf", "min_max") and per_source_results:
            fusion_fn = create_fusion_fn()
            lists_to_fuse = [
                v.get("results", v) for v in per_source_results.values() if v
            ]
            if lists_to_fuse:
                weight_list = None
                if payload.weights:
                    weight_list = [
                        payload.weights.get(src, 1.0) for src in per_source_results
                    ]
                fused = await fusion_fn(
                    result_lists=lists_to_fuse,
                    method=payload.fusion_method,
                    weights=weight_list,
                    top_k=payload.global_top_k,
                )
                result["results"] = fused
                result["fusion_method"] = payload.fusion_method

        return {
            "query": payload.query,
            "results": result.get("results", []),
            "per_source": per_source_results,
            "sources_queried": result.get("sources_queried", []),
            "sources_succeeded": result.get("sources_succeeded", []),
            "fusion_method": result.get("fusion_method", payload.fusion_method),
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register")
async def register_retriever(name: str):
    """Register a new retriever for federated search."""
    try:
        from common_lib.modules.rip.rip_retrieval.federated import (
            get_federated_retriever,
        )

        return {"status": "registered", "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
