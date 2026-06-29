"""RIP Evaluation routes — Run and list retrieval evaluations.

Uses the Evaluation connector for real metric computation
(presision, recall, ndcg, mrr, faithfulness, etc.).
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from common_lib.modules.rip.rip_evaluation.schemas import EvaluationRequest, EvaluationResponse

router = APIRouter(prefix="/rip/evaluation", tags=["RIP — Evaluation"])


@router.post("", response_model=EvaluationResponse)
async def run_evaluation(payload: EvaluationRequest):
    """Run a retrieval evaluation against a set of queries + ground truth.

    Uses the Evaluation connector for real metric computation.
    Metrics: recall@k, precision@k, mrr, ndcg, faithfulness, hallucination_rate.
    """
    try:
        from common_lib.modules.rip.rip_connectors import create_evaluation_fn
        import time

        start = time.perf_counter()

        eval_fn = create_evaluation_fn()
        result = await eval_fn(
            queries=payload.queries,
            ground_truth=payload.ground_truth,
            metrics=payload.metrics,
            k_values=payload.k_values,
            retrieval_config=payload.retrieval_config,
            tenant_id=payload.tenant_id,
        )
        elapsed = (time.perf_counter() - start) * 1000

        return EvaluationResponse(
            id=result.get("id", ""),
            name=payload.name or "unnamed",
            dataset_size=len(payload.queries),
            metrics=result.get("metrics", {}),
            per_query_metrics=result.get("per_query_metrics"),
            average_latency_ms=result.get("average_latency_ms", elapsed),
            hallucination_rate=result.get("hallucination_rate"),
            retrieval_config=payload.retrieval_config,
            created_at=result.get("created_at"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("s", response_model=dict)
async def list_evaluations(limit: int = Query(20, ge=1, le=100)):
    """List recent evaluation runs."""
    try:
        from common_lib.modules.rip.rip_evaluation.service import list_evaluations

        results = await list_evaluations(limit=limit)
        count = len(results) if results else 0
        return {"evaluations": list(results), "total": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
