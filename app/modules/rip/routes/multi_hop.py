"""RIP Multi-Hop routes — IRCoT and beam search multi-step retrieval.

Uses the existing multi-hop service layer with the Synthesis connector
for final answer synthesis.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional

from common_lib.modules.rip.rip_synthesis.schemas import MultiHopRequest

router = APIRouter(prefix="/rip/multi-hop", tags=["RIP — Multi-Hop Retrieval"])


@router.post("")
async def multi_hop_retrieve(payload: MultiHopRequest):
    """Multi-hop retrieval — chained retrieval with interleaved reasoning.

    Strategy: 'irco t' (IRCoT-style), 'beam_search', or 'sequential'.
    Uses the multi-hop service with connector-backed LLM for reasoning.
    """
    try:
        from common_lib.modules.rip.rip_synthesis.multi_hop import (
            multi_hop_retrieve as _multi_hop,
        )
        import time

        start = time.perf_counter()
        result = await _multi_hop(
            query=payload.query,
            max_hops=payload.max_hops,
            top_k_per_hop=payload.top_k_per_hop,
            strategy=payload.strategy,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "findings": result.get("findings", []),
            "reasoning_chain": result.get("reasoning_chain", []),
            "total_hops": result.get("total_hops", 0),
            "total_findings": result.get("total_findings", 0),
            "strategy": payload.strategy,
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
