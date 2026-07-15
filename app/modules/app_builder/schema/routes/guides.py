"""
App Ecosystem — Guides & Walkthroughs Routes

/api/v1/guides — CRUD, steps, publish, completion tracking.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc, desc

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    AppGuideRecord,
    AppGuideStepRecord,
    AppGuideCompletionRecord,
    AppActivityRecord,
    GuideCreate,
    GuideUpdate,
    GuideResponse,
    GuideDetailResponse,
    GuideListResponse,
    GuideStepCreate,
    GuideStepUpdate,
    GuideStepResponse,
    GuideCompleteRequest,
    GuideCompletionResponse,
    APIResponse,
)
from app.modules.app_builder.schema.routes.ecosystem_utils import (
    generate_unique_slug,
    record_activity,
    resolve_actor_user_id,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["App Guides"])


# ─── Guides CRUD ────────────────────────────────────────────────

@router.get("/apps/{app_id}/guides", response_model=GuideListResponse)
async def list_guides(
    app_id: str,
    category: Optional[str] = None,
    difficulty: Optional[str] = Query(None, pattern=r"^(beginner|intermediate|advanced)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    query = select(AppGuideRecord).where(AppGuideRecord.app_id == app_id)
    if category:
        query = query.where(AppGuideRecord.category == category)
    if difficulty:
        query = query.where(AppGuideRecord.difficulty == difficulty)
    query = query.order_by(desc(AppGuideRecord.created_at))

    count_q = select(sqlfunc.count()).select_from(query.subquery())
    total = db.execute(count_q).scalar() or 0
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return GuideListResponse(
        items=[GuideResponse.model_validate(i) for i in items],
        total=total,
    )


@router.post("/apps/{app_id}/guides", response_model=GuideResponse, status_code=201)
async def create_guide(
    app_id: str,
    data: GuideCreate,
    request: Request,
    db: Session = Depends(get_session),
):
    slug = generate_unique_slug(db, AppGuideRecord, data.title)

    author_id = resolve_actor_user_id(request)
    record = AppGuideRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        author_id=author_id,
        slug=slug,
        title=data.title,
        description=data.description,
        category=data.category,
        difficulty=data.difficulty,
        estimated_minutes=data.estimated_minutes,
    )
    db.add(record)
    db.flush()

    # Create steps if provided
    for step_data in (data.steps or []):
        step = AppGuideStepRecord(
            id=str(uuid.uuid4()),
            guide_id=record.id,
            **step_data.model_dump(),
        )
        db.add(step)

    record_activity(db, AppActivityRecord, app_id=app_id, actor_id=author_id, action="posted_guide", entity_type="guide", entity_id=record.id, entity_title=data.title)
    db.commit()
    db.refresh(record)
    return GuideResponse.model_validate(record)


@router.get("/guides/{slug}", response_model=GuideDetailResponse)
async def get_guide(slug: str, db: Session = Depends(get_session)):
    guide = db.execute(
        select(AppGuideRecord).where(AppGuideRecord.slug == slug)
    ).scalar_one_or_none()
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")

    guide.view_count += 1
    db.commit()

    steps = db.execute(
        select(AppGuideStepRecord)
        .where(AppGuideStepRecord.guide_id == guide.id)
        .order_by(AppGuideStepRecord.step_number)
    ).scalars().all()

    result = GuideDetailResponse.model_validate(guide)
    result.steps = [GuideStepResponse.model_validate(s) for s in steps]
    return result


@router.put("/guides/{guide_id}", response_model=GuideResponse)
async def update_guide(guide_id: str, data: GuideUpdate, db: Session = Depends(get_session)):
    guide = db.get(AppGuideRecord, guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(guide, k, v)
    guide.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(guide)
    return GuideResponse.model_validate(guide)


@router.delete("/guides/{guide_id}", response_model=APIResponse)
async def delete_guide(guide_id: str, db: Session = Depends(get_session)):
    guide = db.get(AppGuideRecord, guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    # Delete associated steps
    steps = db.execute(
        select(AppGuideStepRecord).where(AppGuideStepRecord.guide_id == guide_id)
    ).scalars().all()
    for s in steps:
        db.delete(s)
    db.delete(guide)
    db.commit()
    return APIResponse(message="Guide deleted")


@router.post("/guides/{guide_id}/publish", response_model=GuideResponse)
async def publish_guide(guide_id: str, db: Session = Depends(get_session)):
    guide = db.get(AppGuideRecord, guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    guide.status = "published"
    guide.published_at = datetime.now(timezone.utc)
    guide.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(guide)
    return GuideResponse.model_validate(guide)


# ─── Steps ──────────────────────────────────────────────────────

@router.get("/guides/{guide_id}/steps", response_model=list[GuideStepResponse])
async def list_steps(guide_id: str, db: Session = Depends(get_session)):
    steps = db.execute(
        select(AppGuideStepRecord)
        .where(AppGuideStepRecord.guide_id == guide_id)
        .order_by(AppGuideStepRecord.step_number)
    ).scalars().all()
    return [GuideStepResponse.model_validate(s) for s in steps]


@router.post("/guides/{guide_id}/steps", response_model=GuideStepResponse, status_code=201)
async def add_step(
    guide_id: str, data: GuideStepCreate, db: Session = Depends(get_session)
):
    guide = db.get(AppGuideRecord, guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")
    step = AppGuideStepRecord(
        id=str(uuid.uuid4()),
        guide_id=guide_id,
        **data.model_dump(),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return GuideStepResponse.model_validate(step)


@router.put("/guide-steps/{step_id}", response_model=GuideStepResponse)
async def update_step(step_id: str, data: GuideStepUpdate, db: Session = Depends(get_session)):
    step = db.get(AppGuideStepRecord, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(step, k, v)
    db.commit()
    db.refresh(step)
    return GuideStepResponse.model_validate(step)


@router.delete("/guide-steps/{step_id}", response_model=APIResponse)
async def delete_step(step_id: str, db: Session = Depends(get_session)):
    step = db.get(AppGuideStepRecord, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")
    db.delete(step)
    db.commit()
    return APIResponse(message="Step deleted")


# ─── Completion Tracking ────────────────────────────────────────

@router.post("/guides/{guide_id}/complete", response_model=GuideCompletionResponse)
async def mark_complete(
    guide_id: str,
    data: GuideCompleteRequest,
    request: Request,
    db: Session = Depends(get_session),
):
    guide = db.get(AppGuideRecord, guide_id)
    if not guide:
        raise HTTPException(status_code=404, detail="Guide not found")

    user_id = resolve_actor_user_id(request)
    existing = db.execute(
        select(AppGuideCompletionRecord).where(
            AppGuideCompletionRecord.guide_id == guide_id,
            AppGuideCompletionRecord.user_id == user_id,
        )
    ).scalar_one_or_none()

    total_steps = db.execute(
        select(sqlfunc.count(AppGuideStepRecord.id)).where(AppGuideStepRecord.guide_id == guide_id)
    ).scalar() or 0

    is_complete = len(data.completed_steps) >= total_steps and total_steps > 0

    if existing:
        existing.completed_steps = data.completed_steps
        existing.is_complete = is_complete
        if is_complete and not existing.completed_at:
            existing.completed_at = datetime.now(timezone.utc)
            guide.completion_count += 1
        record = existing
    else:
        record = AppGuideCompletionRecord(
            id=str(uuid.uuid4()),
            guide_id=guide_id,
            user_id=user_id,
            completed_steps=data.completed_steps,
            is_complete=is_complete,
            completed_at=datetime.now(timezone.utc) if is_complete else None,
        )
        db.add(record)
        if is_complete:
            guide.completion_count += 1

    db.commit()
    db.refresh(record)
    return GuideCompletionResponse.model_validate(record)
