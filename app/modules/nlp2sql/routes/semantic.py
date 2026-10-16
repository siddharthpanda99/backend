"""nlp2sql semantic-layer routes — thin transport (G1)."""

from __future__ import annotations

from fastapi import APIRouter

from app.modules.nlp2sql.routes import _shared as shared
from common_lib.modules.nlp2sql.schemas import JoinRead
from common_lib.modules.nlp2sql.schemas import JoinUpsert
from common_lib.modules.nlp2sql.schemas import MetricRead
from common_lib.modules.nlp2sql.schemas import MetricUpsert
from common_lib.modules.nlp2sql.schemas import SemanticTermRead
from common_lib.modules.nlp2sql.schemas import SemanticTermUpsert

router = APIRouter(prefix="/data-intelligence/semantic", tags=["NLP-to-SQL — Semantic"])


@router.post("/terms", status_code=201, response_model=SemanticTermRead)
async def upsert_term_route(payload: SemanticTermUpsert) -> dict:
    try:
        from common_lib.modules.nlp2sql.semantic import service

        return service.upsert_term(
            payload.workspace_id,
            payload.name,
            payload.synonyms,
            payload.definition,
            payload.owner,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/terms/{term_id}/approve", response_model=SemanticTermRead)
async def approve_term_route(term_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.semantic import service

        return service.approve_term(term_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/metrics", status_code=201, response_model=MetricRead)
async def upsert_metric_route(payload: MetricUpsert) -> dict:
    try:
        from common_lib.modules.nlp2sql.semantic import service

        return service.upsert_metric(
            payload.workspace_id,
            payload.name,
            payload.expression,
            payload.grain,
            payload.unit,
            payload.owner,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/metrics/{metric_id}/approve", response_model=MetricRead)
async def approve_metric_route(metric_id: str) -> dict:
    try:
        from common_lib.modules.nlp2sql.semantic import service

        return service.approve_metric(metric_id)
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise


@router.post("/joins", status_code=201, response_model=JoinRead)
async def upsert_join_route(payload: JoinUpsert) -> dict:
    """``join_keys`` is now typed ``list[list[str]]`` at the boundary (F2)."""
    try:
        from common_lib.modules.nlp2sql.semantic import service

        return service.upsert_join(
            payload.workspace_id,
            payload.left_object,
            payload.right_object,
            payload.join_keys,
            payload.cardinality,
        )
    except Exception as exc:
        from common_lib.modules.nlp2sql import errors as _errors

        if isinstance(exc, _errors.Nlp2SqlError):
            raise shared.to_http(exc)
        raise
