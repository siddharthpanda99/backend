"""
App Ecosystem — Reviews & Ratings Routes

/api/v1/reviews — CRUD, voting, developer responses, rating stats.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc, desc

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    AppReviewRecord,
    AppReviewVoteRecord,
    AppListingRecord,
    ReviewCreate,
    ReviewUpdate,
    ReviewResponse,
    ReviewListResponse,
    ReviewStatsResponse,
    ReviewVoteRequest,
    ReviewRespondRequest,
    APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["App Reviews"])


def _recalculate_listing_rating(db: Session, app_id: str) -> None:
    """Recalculate avg_rating and review_count on the listing after a review change."""
    listing = db.execute(
        select(AppListingRecord).where(AppListingRecord.app_id == app_id)
    ).scalar_one_or_none()
    if not listing:
        return
    result = db.execute(
        select(
            sqlfunc.count(AppReviewRecord.id),
            sqlfunc.coalesce(sqlfunc.avg(AppReviewRecord.rating), 0),
        ).where(
            AppReviewRecord.app_id == app_id,
            AppReviewRecord.status == "visible",
        )
    ).one_or_none()
    if result:
        listing.review_count = result[0]
        listing.avg_rating = round(float(result[1]), 2)
        db.commit()


# ─── Reviews CRUD ───────────────────────────────────────────────

@router.get("/apps/{app_id}/reviews", response_model=ReviewListResponse)
async def list_reviews(
    app_id: str,
    sort: Optional[str] = Query(None, pattern=r"^(newest|oldest|highest|lowest|helpful)$"),
    rating: Optional[int] = Query(None, ge=1, le=5),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    query = select(AppReviewRecord).where(
        AppReviewRecord.app_id == app_id,
        AppReviewRecord.status == "visible",
    )
    if rating:
        query = query.where(AppReviewRecord.rating == rating)

    if sort == "oldest":
        query = query.order_by(AppReviewRecord.created_at)
    elif sort == "highest":
        query = query.order_by(desc(AppReviewRecord.rating), desc(AppReviewRecord.created_at))
    elif sort == "lowest":
        query = query.order_by(AppReviewRecord.rating, desc(AppReviewRecord.created_at))
    elif sort == "helpful":
        query = query.order_by(desc(AppReviewRecord.helpful_count), desc(AppReviewRecord.created_at))
    else:
        query = query.order_by(desc(AppReviewRecord.created_at))

    count_q = select(sqlfunc.count()).select_from(query.subquery())
    total = db.execute(count_q).scalar() or 0
    items = db.execute(query.offset(offset).limit(limit)).scalars().all()

    return ReviewListResponse(
        items=[ReviewResponse.model_validate(i) for i in items],
        total=total,
    )


@router.post("/apps/{app_id}/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    app_id: str, data: ReviewCreate, db: Session = Depends(get_session)
):
    record = AppReviewRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        user_id="current-user",  # TODO: extract from auth token
        **data.model_dump(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    _recalculate_listing_rating(db, app_id)
    logger.info(f"Created review for app '{app_id}' rating={data.rating}")
    return ReviewResponse.model_validate(record)


@router.put("/reviews/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str, data: ReviewUpdate, db: Session = Depends(get_session)
):
    review = db.get(AppReviewRecord, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(review, k, v)
    review.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    _recalculate_listing_rating(db, review.app_id)
    return ReviewResponse.model_validate(review)


@router.delete("/reviews/{review_id}", response_model=APIResponse)
async def delete_review(review_id: str, db: Session = Depends(get_session)):
    review = db.get(AppReviewRecord, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    app_id = review.app_id
    db.delete(review)
    db.commit()
    _recalculate_listing_rating(db, app_id)
    return APIResponse(message="Review deleted")


# ─── Voting ─────────────────────────────────────────────────────

@router.post("/reviews/{review_id}/vote", response_model=ReviewResponse)
async def vote_review(
    review_id: str, data: ReviewVoteRequest, db: Session = Depends(get_session)
):
    review = db.get(AppReviewRecord, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    user_id = "current-user"  # TODO: extract from auth token

    # Check existing vote
    existing = db.execute(
        select(AppReviewVoteRecord).where(
            AppReviewVoteRecord.review_id == review_id,
            AppReviewVoteRecord.user_id == user_id,
        )
    ).scalar_one_or_none()

    if existing:
        # Toggle off if same vote
        if existing.vote == data.vote:
            db.delete(existing)
            if data.vote == "helpful":
                review.helpful_count = max(0, review.helpful_count - 1)
            else:
                review.not_helpful_count = max(0, review.not_helpful_count - 1)
        else:
            # Switch vote
            if existing.vote == "helpful":
                review.helpful_count = max(0, review.helpful_count - 1)
            else:
                review.not_helpful_count = max(0, review.not_helpful_count - 1)
            existing.vote = data.vote
            if data.vote == "helpful":
                review.helpful_count += 1
            else:
                review.not_helpful_count += 1
    else:
        vote_record = AppReviewVoteRecord(
            id=str(uuid.uuid4()),
            review_id=review_id,
            user_id=user_id,
            vote=data.vote,
        )
        db.add(vote_record)
        if data.vote == "helpful":
            review.helpful_count += 1
        else:
            review.not_helpful_count += 1

    db.commit()
    db.refresh(review)
    return ReviewResponse.model_validate(review)


# ─── Developer Response ─────────────────────────────────────────

@router.post("/reviews/{review_id}/respond", response_model=ReviewResponse)
async def respond_to_review(
    review_id: str, data: ReviewRespondRequest, db: Session = Depends(get_session)
):
    review = db.get(AppReviewRecord, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.developer_response = data.response
    review.developer_response_at = datetime.now(timezone.utc)
    review.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(review)
    return ReviewResponse.model_validate(review)


# ─── Stats ──────────────────────────────────────────────────────

@router.get("/apps/{app_id}/reviews/stats", response_model=ReviewStatsResponse)
async def get_review_stats(app_id: str, db: Session = Depends(get_session)):
    result = db.execute(
        select(
            sqlfunc.count(AppReviewRecord.id),
            sqlfunc.coalesce(sqlfunc.avg(AppReviewRecord.rating), 0),
        ).where(
            AppReviewRecord.app_id == app_id,
            AppReviewRecord.status == "visible",
        )
    ).one_or_none()

    total = result[0] if result else 0
    avg = round(float(result[1]), 2) if result else 0.0

    distribution = {}
    for r in range(1, 6):
        cnt = db.execute(
            select(sqlfunc.count(AppReviewRecord.id)).where(
                AppReviewRecord.app_id == app_id,
                AppReviewRecord.rating == r,
                AppReviewRecord.status == "visible",
            )
        ).scalar() or 0
        distribution[str(r)] = cnt

    recommend = 0
    if total > 0:
        positive = sum(v for k, v in distribution.items() if int(k) >= 4)
        recommend = round(positive / total * 100, 1)

    return ReviewStatsResponse(
        total_reviews=total,
        avg_rating=avg,
        distribution=distribution,
        recommend_percentage=recommend,
    )
