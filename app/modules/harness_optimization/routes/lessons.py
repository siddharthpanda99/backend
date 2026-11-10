"""Lessons Routes.

Thin transport layer for lesson management.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from common_lib.modules.harness_optimization.service import (
    get_harness_optimization_service,
)
from common_lib.modules.harness_optimization.flags import (
    is_hos_enabled,
    is_lessons_enabled,
)
from common_lib.modules.harness_optimization.exceptions import FeatureDisabledError

from app.modules.harness_optimization.routes.schemas import (
    LessonCreate,
    LessonRead,
    LessonStatusUpdate,
    LessonsForHarnessQuery,
)

router = APIRouter(prefix="/lessons", tags=["Lessons"])


def _get_service():
    """Get HOS service instance."""
    if not is_hos_enabled() or not is_lessons_enabled():
        raise FeatureDisabledError(
            "Lessons feature is disabled",
            flag_name="HARNESS_OPT_LESSONS_ENABLED",
        )
    return get_harness_optimization_service()


# ════════════════════════════════════════════════════════════════════
# Lesson CRUD
# ═══════════════════════════════════════════════════════════════════


@router.post(
    "/",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lesson (CANDIDATE status)",
)
def create_lesson(payload: LessonCreate, service=Depends(_get_service)):
    """Create a new evidence-backed lesson."""
    lesson = service.create_lesson(
        tenant_id=payload.tenant_id,
        domain_scope=payload.domain_scope,
        statement=payload.statement,
        operational_recommendation=payload.operational_recommendation,
        evidence_refs=payload.evidence_refs,
        source_run_id=payload.source_run_id,
        source_task_id=payload.source_task_id,
        confidence=payload.confidence,
        known_counterexamples=payload.known_counterexamples,
        applicable_component_types=payload.applicable_component_types,
        applicability_conditions=payload.applicability_conditions,
        expiry_days=payload.expiry_days,
        revalidation_policy=payload.revalidation_policy,
        author_id=payload.author_id,
    )
    return LessonRead.model_validate(lesson)


@router.get(
    "/",
    response_model=List[LessonRead],
    summary="List lessons with filters",
)
def list_lessons(
    tenant_id: Optional[str] = Query(None),
    domain_scope: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    service=Depends(_get_service),
):
    """List lessons with optional filters."""
    lessons, total = service.list_lessons(
        tenant_id, domain_scope, status, page, page_size
    )
    return [LessonRead.model_validate(l) for l in lessons]


@router.get(
    "/{lesson_id}",
    response_model=LessonRead,
    summary="Get lesson by ID",
)
def get_lesson(lesson_id: UUID, service=Depends(_get_service)):
    """Get lesson by ID."""
    lesson = service.get_lesson(lesson_id)
    return LessonRead.model_validate(lesson)


@router.patch(
    "/{lesson_id}/status",
    response_model=LessonRead,
    summary="Update lesson status (CANDIDATE -> APPROVED -> DEPRECATED -> REJECTED)",
)
def update_lesson_status(
    lesson_id: UUID, payload: LessonStatusUpdate, service=Depends(_get_service)
):
    """Update lesson status."""
    lesson = service.update_lesson_status(
        lesson_id, payload.new_status, payload.approver_id
    )
    return LessonRead.model_validate(lesson)


# ════════════════════════════════════════════════════════════════════
# Lessons for Harness
# ═══════════════════════════════════════════════════════════════════


@router.get(
    "/for-harness/{harness_id}",
    response_model=List[LessonRead],
    summary="Get applicable lessons for a harness/component",
)
def get_lessons_for_harness(
    harness_id: UUID,
    component_type: Optional[str] = Query(None),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    service=Depends(_get_service),
):
    """Get approved lessons applicable to a harness/component."""
    lessons = service.get_lessons_for_harness(
        harness_id=harness_id,
        component_type=component_type,
        min_confidence=min_confidence,
    )
    return [LessonRead.model_validate(l) for l in lessons]


@router.get(
    "/{lesson_id}/evidence",
    response_model=dict,
    summary="Get supporting evidence for a lesson",
)
def get_lesson_evidence(lesson_id: UUID, service=Depends(_get_service)):
    """Get supporting evidence for a lesson."""
    # Note: service doesn't have get_lesson_evidence yet
    return {"evidence_refs": []}


__all__ = ["router"]
