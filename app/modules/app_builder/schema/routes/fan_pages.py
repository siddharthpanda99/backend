"""
App Ecosystem — Fan Pages & Activity Feed Routes

/api/v1/fan-pages — Fan page data, activity feed, follow/unfollow.
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
    AppListingRecord,
    AppFollowerRecord,
    AppActivityRecord,
    AppReviewRecord,
    AppBlogPostRecord,
    AppGuideRecord,
    ForumThreadRecord,
    AppListingResponse,
    AppListingStatsResponse,
    ReviewResponse,
    BlogPostResponse,
    GuideResponse,
    ThreadResponse,
    ActivityResponse,
    FollowerResponse,
    FanPageDataResponse,
    APIResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["App Fan Pages"])


@router.get("/apps/{app_id}/fan-page", response_model=FanPageDataResponse)
async def get_fan_page(app_id: str, db: Session = Depends(get_session)):
    """Composite fan page data — listing, stats, recent content, activity."""
    listing = db.execute(
        select(AppListingRecord).where(AppListingRecord.app_id == app_id)
    ).scalar_one_or_none()

    if not listing:
        raise HTTPException(status_code=404, detail="App listing not found")

    # Stats
    stats = AppListingStatsResponse(
        installs_today=listing.install_count // 30,
        installs_week=listing.install_count // 4,
        installs_month=listing.install_count,
        views_today=listing.view_count // 30,
        rating_distribution={"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
        trending_score=listing.install_count * 0.6 + listing.view_count * 0.4,
    )

    # Recent reviews (top 5)
    recent_reviews = db.execute(
        select(AppReviewRecord)
        .where(AppReviewRecord.app_id == app_id, AppReviewRecord.status == "visible")
        .order_by(desc(AppReviewRecord.created_at))
        .limit(5)
    ).scalars().all()

    # Recent blogs (top 5)
    recent_blogs = db.execute(
        select(AppBlogPostRecord)
        .where(AppBlogPostRecord.app_id == app_id, AppBlogPostRecord.status == "published")
        .order_by(desc(AppBlogPostRecord.created_at))
        .limit(5)
    ).scalars().all()

    # Recent guides (top 5)
    recent_guides = db.execute(
        select(AppGuideRecord)
        .where(AppGuideRecord.app_id == app_id, AppGuideRecord.status == "published")
        .order_by(desc(AppGuideRecord.created_at))
        .limit(5)
    ).scalars().all()

    # Recent threads (top 5)
    recent_threads = db.execute(
        select(ForumThreadRecord)
        .where(ForumThreadRecord.app_id == app_id)
        .order_by(desc(ForumThreadRecord.is_pinned), desc(ForumThreadRecord.created_at))
        .limit(5)
    ).scalars().all()

    # Activity feed (top 10)
    activity = db.execute(
        select(AppActivityRecord)
        .where(AppActivityRecord.app_id == app_id)
        .order_by(desc(AppActivityRecord.created_at))
        .limit(10)
    ).scalars().all()

    # Follower count
    follower_count = db.execute(
        select(sqlfunc.count(AppFollowerRecord.id))
        .where(AppFollowerRecord.app_id == app_id)
    ).scalar() or 0

    # Check if current user follows
    is_following = False  # TODO: check against auth token
    # user_id = "current-user"
    # is_following = db.execute(
    #     select(AppFollowerRecord).where(
    #         AppFollowerRecord.app_id == app_id,
    #         AppFollowerRecord.user_id == user_id,
    #     )
    # ).scalar_one_or_none() is not None

    return FanPageDataResponse(
        listing=AppListingResponse.model_validate(listing),
        stats=stats,
        recent_reviews=[ReviewResponse.model_validate(r) for r in recent_reviews],
        recent_blogs=[BlogPostResponse.model_validate(b) for b in recent_blogs],
        recent_guides=[GuideResponse.model_validate(g) for g in recent_guides],
        recent_threads=[ThreadResponse.model_validate(t) for t in recent_threads],
        activity=[ActivityResponse.model_validate(a) for a in activity],
        follower_count=follower_count,
        is_following=is_following,
    )


@router.get("/apps/{app_id}/activity", response_model=list[ActivityResponse])
async def get_activity_feed(
    app_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_session),
):
    items = db.execute(
        select(AppActivityRecord)
        .where(AppActivityRecord.app_id == app_id)
        .order_by(desc(AppActivityRecord.created_at))
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return [ActivityResponse.model_validate(a) for a in items]


# ─── Follow / Unfollow ──────────────────────────────────────────

@router.post("/apps/{app_id}/follow", response_model=APIResponse)
async def follow_app(app_id: str, db: Session = Depends(get_session)):
    user_id = "current-user"
    existing = db.execute(
        select(AppFollowerRecord).where(
            AppFollowerRecord.app_id == app_id,
            AppFollowerRecord.user_id == user_id,
        )
    ).scalar_one_or_none()
    if existing:
        return APIResponse(message="Already following")

    db.add(AppFollowerRecord(id=str(uuid.uuid4()), app_id=app_id, user_id=user_id))
    db.commit()
    return APIResponse(message="Following app")


@router.delete("/apps/{app_id}/follow", response_model=APIResponse)
async def unfollow_app(app_id: str, db: Session = Depends(get_session)):
    user_id = "current-user"
    existing = db.execute(
        select(AppFollowerRecord).where(
            AppFollowerRecord.app_id == app_id,
            AppFollowerRecord.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not existing:
        return APIResponse(message="Not following")
    db.delete(existing)
    db.commit()
    return APIResponse(message="Unfollowed app")


@router.get("/apps/{app_id}/followers", response_model=list[FollowerResponse])
async def list_followers(
    app_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_session),
):
    items = db.execute(
        select(AppFollowerRecord)
        .where(AppFollowerRecord.app_id == app_id)
        .order_by(desc(AppFollowerRecord.created_at))
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return [FollowerResponse.model_validate(f) for f in items]
