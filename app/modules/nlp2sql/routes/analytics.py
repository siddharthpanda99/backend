"""nlp2sql analytics / visualizations / reports / saved / feedback — thin (G1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import AnalyzeRequest
from common_lib.modules.nlp2sql.schemas import ChartSpec
from common_lib.modules.nlp2sql.schemas import FeedbackCreate
from common_lib.modules.nlp2sql.schemas import ReportCreate

router = APIRouter(prefix="/data-intelligence", tags=["NLP-to-SQL — Analytics"])


class AnalyzeBody(AnalyzeRequest):
    """Analyze body — imports the source contract (G10)."""


@router.post("/query-runs/analyze", response_model=dict)
async def analyze_route(payload: AnalyzeBody) -> dict:
    from common_lib.modules.nlp2sql.analytics.service import analyze_result

    return analyze_result(
        payload.columns, [tuple(r) for r in payload.rows], truncated=payload.truncated
    )


@router.post("/visualizations", status_code=201, response_model=ChartSpec)
async def create_viz_route(payload: ChartSpec) -> dict:
    """Request body IS the source contract (G10): ``aggregation``,
    ``x_label``/``y_label`` and ``accessibility_description`` now round-trip."""
    try:
        from common_lib.modules.nlp2sql.visualization.specs import validate_spec

        return validate_spec(payload).model_dump()
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/reports", status_code=201, response_model=dict)
async def create_report_route(payload: ReportCreate) -> dict:
    """Raw-``dict`` body replaced by ``ReportCreate`` (SSOT §12: no arbitrary
    dicts for critical ops). Wire response unchanged (G4)."""
    return {"report": payload.model_dump(), "status": "saved"}


@router.get("/saved-queries", response_model=dict)
async def saved_queries_route(workspace_id: str = "default") -> dict:
    from common_lib.modules.nlp2sql.semantic import service

    _ = workspace_id
    return {"queries": service.approved_examples(workspace_id)}


@router.post("/feedback", status_code=201, response_model=dict)
async def feedback_route(payload: FeedbackCreate) -> dict:
    try:
        from common_lib.modules.nlp2sql.memory import store

        candidate = store.record_candidate(
            payload.workspace_id,
            payload.comment or "(feedback)",
            f"-- feedback for {payload.query_run_id}",
        )
        store.submit_feedback(candidate["id"], payload.rating)
        return {"candidate_id": candidate["id"], "status": "recorded"}
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
