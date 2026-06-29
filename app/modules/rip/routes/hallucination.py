"""RIP Hallucination routes — Detect hallucinations in generated text.

Uses the Hallucination connector for real NLI (transformers) and LLM-based
hallucination detection with configurable methods.
"""

from fastapi import APIRouter, HTTPException
from typing import Any, Optional

from common_lib.modules.rip.rip_evaluation.schemas import HallucinationScoreRequest

router = APIRouter(prefix="/rip/hallucination", tags=["RIP — Hallucination Detection"])


@router.post("/score")
async def hallucination_score(payload: HallucinationScoreRequest):
    """Score a generated response for hallucination against context chunks.

    Methods:
      - nli: NLI model via transformers (roberta-large-mnli)
      - llm: LLM-based faithfulness evaluation
      - hybrid: NLI first, LLM fallback for low-confidence
    """
    try:
        from common_lib.modules.rip.rip_connectors import (
            create_hallucination_fn,
            create_llm_fn,
        )
        import time

        start = time.perf_counter()

        llm_fn = None
        if payload.method in ("llm", "hybrid"):
            llm_fn = await create_llm_fn(
                model_name=payload.llm_model or "gpt-4o-mini",
                temperature=0.2,
                max_tokens=512,
            )

        hallucination_fn = await create_hallucination_fn(method=payload.method)
        result = await hallucination_fn(
            generated=payload.generated,
            context_chunks=payload.context_chunks,
            llm_fn=llm_fn,
        )
        elapsed = (time.perf_counter() - start) * 1000

        hallucination_score = result.get("score", 0.0)
        detected = hallucination_score >= payload.threshold

        return {
            "generated": payload.generated[:200],
            "score": hallucination_score,
            "detected": detected,
            "threshold": payload.threshold,
            "method": payload.method,
            "details": result.get("details", []),
            "contradictions": result.get("contradictions", []),
            "latency_ms": elapsed,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
