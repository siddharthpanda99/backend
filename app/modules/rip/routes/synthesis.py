"""RIP Synthesis routes — Knowledge synthesis and multi-hop research.

Uses the synthesis connector for real extractive/abstractive/hybrid generation.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_synthesis.schemas import SynthesisRequest

router = APIRouter(prefix="/rip", tags=["RIP — Synthesis"])


@router.post("/synthesis")
async def synthesize_knowledge(payload: SynthesisRequest):
    """Synthesize knowledge from retrieved chunks into a grounded answer.

    Modes:
      - extractive: Quote directly from retrieved passages
      - abstractive: LLM-generated synthesis with citations
      - hybrid: Extractive quotes + abstractive summary
    """
    try:
        from common_lib.modules.rip.rip_connectors import (
            create_synthesis_fn,
            create_llm_fn,
        )
        import time

        start = time.perf_counter()

        llm_fn = None
        if payload.mode in ("abstractive", "hybrid"):
            llm_fn = await create_llm_fn(
                model_name=payload.llm_model or "gpt-4o-mini",
                temperature=0.5,
                max_tokens=payload.max_tokens,
            )

        synthesis_fn = await create_synthesis_fn(mode=payload.mode)
        result = await synthesis_fn(
            query=payload.query,
            results=payload.results,
            llm_fn=llm_fn,
            mode=payload.mode,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return {
            "query": payload.query,
            "synthesis": result.get("synthesis", result.get("answer", "")),
            "sources": result.get("sources", []),
            "mode": payload.mode,
            "confidence": result.get("confidence", 0.0),
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
