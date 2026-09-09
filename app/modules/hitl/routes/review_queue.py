"""HITL knowledge review queue — thin FastAPI routes (F6).

All business logic lives in common_lib.modules.governance.hitl.review_service.
Routes only handle HTTP concerns: parsing, status codes, response shaping.
"""

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from common_lib.modules.governance.hitl.review_errors import (
    ConflictError,
    FeatureDisabledError,
    InvalidArgumentError,
    KnowledgeReviewError,
    ResourceNotFoundError,
)
from common_lib.modules.governance.hitl.review_service import (
    get_knowledge_review_service,
)

router = APIRouter(prefix="/review", tags=["HITL - Review Queue"])


def _translate(exc: KnowledgeReviewError) -> HTTPException:
    if isinstance(exc, InvalidArgumentError):
        return HTTPException(status_code=400, detail=exc.message)
    if isinstance(exc, ResourceNotFoundError):
        return HTTPException(status_code=404, detail=exc.message)
    if isinstance(exc, FeatureDisabledError):
        return HTTPException(status_code=403, detail=exc.message)
    if isinstance(exc, ConflictError):
        return HTTPException(status_code=409, detail=exc.message)
    return HTTPException(status_code=500, detail=exc.message)


class PendingCreate(BaseModel):
    kb_id: str
    text: str
    occurred_at: str | None = None
    occurred_at_precision: str = "day"
    source_chunk: str | None = None
    source_doc: str | None = None
    created_by: str = "system"


class PendingDecide(BaseModel):
    decision: str
    reviewer: str
    mapping: dict[str, Any] | None = None
    reason: str = ""


class ReviewItemCreate(BaseModel):
    kb_id: str
    kind: str
    subject_refs: list[str]
    candidate_a: dict[str, Any] | None = None
    candidate_b: dict[str, Any] | None = None
    score: float | None = None
    reason: str = ""
    priority: int = 0
    context: dict[str, Any] | None = None
    created_by: str = "system"


class ReviewItemDecide(BaseModel):
    decision: str
    reviewer: str
    resolution: str = ""


class BatchAdjudicate(BaseModel):
    review_ids: list[str]
    reviewer: str = "batch-adjudicator"
    auto_apply: bool = False


class FactVerdict(BaseModel):
    reviewer: str
    reason: str = ""
    resolution: str = "withdrawn"


@router.post("/pending", status_code=201)
def submit_pending(body: PendingCreate):
    try:
        return get_knowledge_review_service().submit_pending_fact(**body.model_dump())
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/remember", status_code=201)
def remember(body: PendingCreate):
    try:
        svc = get_knowledge_review_service()
        return svc.remember(
            body.kb_id,
            body.text,
            source_chunk=body.source_chunk,
            source_doc=body.source_doc,
            occurred_at=body.occurred_at,
            created_by=body.created_by,
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.get("/pending")
def list_pending(
    kb_id: str = Query(...),
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        return get_knowledge_review_service().list_pending_facts(
            kb_id, status=status, limit=limit, offset=offset
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/pending/{pending_id}/decide")
def decide_pending(pending_id: str, body: PendingDecide):
    try:
        return get_knowledge_review_service().decide_pending_fact(
            pending_id,
            body.decision,
            body.reviewer,
            mapping=body.mapping,
            reason=body.reason,
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/items", status_code=201)
def submit_item(body: ReviewItemCreate):
    try:
        return get_knowledge_review_service().submit_review_item(**body.model_dump())
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.get("/items")
def list_items(
    kb_id: str = Query(...),
    status: str = Query(default="pending"),
    kind: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    try:
        return get_knowledge_review_service().list_review_items(
            kb_id, status=status, kind=kind, limit=limit, offset=offset
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/items/{review_id}/decide")
def decide_item(review_id: str, body: ReviewItemDecide):
    try:
        return get_knowledge_review_service().decide_review_item(
            review_id, body.decision, body.reviewer, resolution=body.resolution
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/items/adjudicate")
def adjudicate(body: BatchAdjudicate):
    try:
        return get_knowledge_review_service().adjudicate_batch(
            body.review_ids, reviewer=body.reviewer, auto_apply=body.auto_apply
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/facts/{fact_id}/confirm")
def confirm_fact(fact_id: str, body: FactVerdict, kb_id: str = Query(...)):
    try:
        return get_knowledge_review_service().confirm_fact(
            kb_id, fact_id, body.reviewer
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/facts/{fact_id}/reject")
def reject_fact(fact_id: str, body: FactVerdict, kb_id: str = Query(...)):
    try:
        return get_knowledge_review_service().reject_fact(
            kb_id, fact_id, body.reviewer, reason=body.reason
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


@router.post("/facts/{fact_id}/close")
def close_fact(fact_id: str, body: FactVerdict, kb_id: str = Query(...)):
    try:
        return get_knowledge_review_service().close_fact(
            kb_id, fact_id, body.reviewer, resolution=body.resolution
        )
    except KnowledgeReviewError as exc:
        raise _translate(exc)


__all__ = ["router"]
