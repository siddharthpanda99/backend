"""RIP Reranking routes — Cross-encoder and LLM reranking.

Implements endpoint 11.13 from the implementation tracker.
Uses real cross-encoder / LLM models via rip_connectors.
"""

from fastapi import APIRouter, HTTPException

from common_lib.modules.rip.rip_reranking.schemas import RerankRequest
from common_lib.modules.rip.rip_connectors import create_cross_encoder_fn, create_llm_fn

router = APIRouter(prefix="/rip/reranking", tags=["RIP — Reranking"])


@router.post("")
async def rerank_results(payload: RerankRequest):
    """Rerank retrieval results using cross-encoder or LLM scorer.

    Supports methods: cross_encoder, llm, pointwise, listwise.
    Uses real models via rip_connectors based on the model names in the request.
    """
    try:
        from common_lib.modules.rip.rip_reranking.service import (
            rerank_results as _rerank,
        )

        # Create the appropriate scoring function based on method
        cross_encoder_fn = None
        llm_fn = None

        if payload.method in ("cross_encoder", "pointwise"):
            cross_encoder_fn = await create_cross_encoder_fn(
                model_name=payload.cross_encoder_model,
                device="cpu",
            )
        elif payload.method in ("llm", "listwise"):
            llm_fn = await create_llm_fn(
                model_name=payload.llm_model,
                temperature=0.3,
                max_tokens=2048,
            )

        results = await _rerank(
            query=payload.query,
            candidates=payload.results,
            top_k=payload.top_k,
            method=payload.method,
            llm_fn=llm_fn,
            cross_encoder_fn=cross_encoder_fn,
        )

        return {
            "query": payload.query,
            "results": results,
            "count": len(results),
            "method": payload.method,
            "model": payload.cross_encoder_model if cross_encoder_fn else payload.llm_model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
