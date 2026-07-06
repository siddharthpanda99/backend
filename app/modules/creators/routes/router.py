"""Creator System API Routes — thin routes delegating to CreatorAdapter."""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request

from common_lib.modules.integration.adapters.creator_adapter import get_creator_adapter

router = APIRouter(tags=["creators"])

logger = logging.getLogger(__name__)

_adapter = get_creator_adapter()


def _get_current_user_id(request: Request) -> Optional[str]:
    """Extract current user ID from request state (set by auth middleware)."""
    return getattr(request.state, "user_id", None)


# =============================================================================
# Creator Profiles
# =============================================================================


@router.get("/")
async def list_creators(
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query(
        "avg_rating", pattern="^(avg_rating|total_sales|follower_count|total_views)$"
    ),
):
    """List all creators (leaderboard)."""
    try:
        creators = await _adapter.get_leaderboard(limit=limit, sort_by=sort_by)
        return {"status": "ok", "creators": creators, "count": len(creators)}
    except Exception as e:
        logger.error(f"Failed to list creators: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list creators")


@router.get("/ranking")
async def get_ranking(limit: int = Query(50, ge=1, le=100)):
    """Top creators leaderboard."""
    try:
        creators = await _adapter.get_leaderboard(limit=limit, sort_by="avg_rating")
        return {"status": "ok", "creators": creators, "count": len(creators)}
    except Exception as e:
        logger.error(f"Failed to get ranking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get ranking")


@router.get("/{username}")
async def get_creator_profile(username: str):
    """Get creator profile by username."""
    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")
        return {"status": "ok", "creator": profile}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get creator profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get creator profile")


@router.post("/")
async def become_creator(request: Request, data: Dict[str, Any] = {}):
    """Become a creator (create profile)."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        existing = await _adapter.get_profile("user", user_id)
        if existing:
            raise HTTPException(status_code=409, detail="Already a creator")

        profile = await _adapter.become_creator("user", user_id, data)
        return {"status": "ok", "creator": profile}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to become creator: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create creator profile")


@router.put("/{username}")
async def update_creator_profile(
    username: str, request: Request, data: Dict[str, Any] = {}
):
    """Update own creator profile."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")
        if profile.get("entity_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        updated = await _adapter.update_profile(profile["id"], data)
        return {"status": "ok", "creator": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update creator profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update profile")


# =============================================================================
# Similar Creators
# =============================================================================


@router.get("/{username}/similar")
async def get_similar_creators(
    username: str,
    limit: int = Query(6, ge=1, le=20),
):
    """Find creators with similar specialties and audience profiles."""
    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        similar = await _adapter.find_similar(profile["id"], limit=limit)
        return {"status": "ok", "creators": similar, "count": len(similar)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to find similar creators: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to find similar creators")


# =============================================================================
# Creator Items
# =============================================================================


@router.get("/{username}/items")
async def get_creator_items(
    username: str,
    item_type: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get items published by a creator."""
    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        items = await _adapter.get_creator_items(
            profile["id"], item_type=item_type, limit=limit
        )
        return {"status": "ok", "items": items, "count": len(items)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get creator items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get creator items")


# =============================================================================
# Reviews
# =============================================================================


@router.get("/{username}/reviews")
async def get_creator_reviews(
    username: str,
    limit: int = Query(20, ge=1, le=100),
):
    """Get reviews for a creator."""
    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        reviews = await _adapter.get_reviews(profile["id"], limit=limit)
        return {"status": "ok", "reviews": reviews, "count": len(reviews)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get creator reviews: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get reviews")


@router.post("/{username}/reviews")
async def leave_review(username: str, request: Request, data: Dict[str, Any] = {}):
    """Leave a review on a creator."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    if "rating" not in data or not (1 <= data["rating"] <= 5):
        raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")

    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")
        if profile.get("entity_id") == user_id:
            raise HTTPException(status_code=400, detail="Cannot review yourself")

        review = await _adapter.leave_review(
            creator_id=profile["id"],
            reviewer_type="user",
            reviewer_id=user_id,
            data=data,
        )
        return {"status": "ok", "review": review}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to leave review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to leave review")


@router.post("/{username}/reviews/{review_id}/respond")
async def respond_to_review(
    username: str,
    review_id: str,
    request: Request,
    data: Dict[str, Any] = {},
):
    """Creator responds to a review."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    comment = data.get("comment", "").strip()
    if not comment:
        raise HTTPException(status_code=400, detail="Comment is required")

    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")
        if profile.get("entity_id") != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")

        response = await _adapter.respond_to_review(
            review_id=review_id,
            creator_id=profile["id"],
            comment=comment,
        )
        return {"status": "ok", "response": response}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to respond to review: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to respond to review")


# =============================================================================
# Follows
# =============================================================================


@router.post("/{username}/follow")
async def follow_creator(username: str, request: Request):
    """Follow a creator."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")
        if profile.get("entity_id") == user_id:
            raise HTTPException(status_code=400, detail="Cannot follow yourself")

        result = await _adapter.follow(
            follower_type="user",
            follower_id=user_id,
            following_type="user",
            following_id=profile["entity_id"],
        )
        return {"status": "ok", "followed": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to follow creator: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to follow")


@router.delete("/{username}/follow")
async def unfollow_creator(username: str, request: Request):
    """Unfollow a creator."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        result = await _adapter.unfollow(
            follower_type="user",
            follower_id=user_id,
            following_type="user",
            following_id=profile["entity_id"],
        )
        return {"status": "ok", "unfollowed": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unfollow creator: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unfollow")


@router.get("/{username}/followers")
async def get_followers(
    username: str,
    limit: int = Query(50, ge=1, le=100),
):
    """Get followers of a creator."""
    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        followers = await _adapter.get_followers(profile["id"], limit=limit)
        return {"status": "ok", "followers": followers, "count": len(followers)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get followers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get followers")


@router.get("/{username}/following")
async def get_following(
    username: str,
    limit: int = Query(50, ge=1, le=100),
):
    """Get entities that a creator is following."""
    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        following = await _adapter.get_following(profile["id"], limit=limit)
        return {"status": "ok", "following": following, "count": len(following)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get following: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get following")


@router.get("/{username}/is-following")
async def check_following(username: str, request: Request):
    """Check if current user follows this creator."""
    user_id = _get_current_user_id(request)
    if not user_id:
        return {"status": "ok", "is_following": False}

    try:
        profile = await _adapter.get_profile_by_username(username)
        if not profile:
            raise HTTPException(status_code=404, detail="Creator not found")

        is_following = await _adapter.is_following(
            follower_type="user",
            follower_id=user_id,
            following_type="user",
            following_id=profile["entity_id"],
        )
        return {"status": "ok", "is_following": is_following}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check following: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check following")


# =============================================================================
# My Creations (cross-entity query)
# =============================================================================


@router.get("/me/creations")
async def get_my_creations(
    request: Request,
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Get all entities owned by the current user across all types."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        items = await _adapter.get_my_creations(
            user_id, entity_type=entity_type, limit=limit, offset=offset
        )
        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Failed to get my creations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get creations")


@router.get("/me/creations/counts")
async def get_my_creation_counts(request: Request):
    """Get count of entities owned by the current user per type."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        counts = await _adapter.get_my_creation_counts(user_id)
        total = sum(counts.values())
        return {"status": "ok", "counts": counts, "total": total}
    except Exception as e:
        logger.error(f"Failed to get creation counts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get counts")


# =============================================================================
# Entity Follow (follow individual prompts/skills/agents)
# =============================================================================


@router.post("/entities/{entity_type}/{entity_id}/follow")
async def follow_entity(
    entity_type: str, entity_id: str, request: Request
):
    """Follow an individual entity (prompt, skill, agent, etc.)."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    if entity_type not in ("prompt", "skill", "agent", "workflow", "tool"):
        raise HTTPException(status_code=400, detail="Invalid entity type")

    try:
        result = await _adapter.follow(
            follower_type="user",
            follower_id=user_id,
            following_type=entity_type,
            following_id=entity_id,
        )
        return {"status": "ok", "followed": result}
    except Exception as e:
        logger.error(f"Failed to follow entity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to follow entity")


@router.delete("/entities/{entity_type}/{entity_id}/follow")
async def unfollow_entity(
    entity_type: str, entity_id: str, request: Request
):
    """Unfollow an individual entity."""
    user_id = _get_current_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        result = await _adapter.unfollow(
            follower_type="user",
            follower_id=user_id,
            following_type=entity_type,
            following_id=entity_id,
        )
        return {"status": "ok", "unfollowed": result}
    except Exception as e:
        logger.error(f"Failed to unfollow entity: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to unfollow entity")


@router.get("/entities/{entity_type}/{entity_id}/is-following")
async def check_entity_following(
    entity_type: str, entity_id: str, request: Request
):
    """Check if current user follows this entity."""
    user_id = _get_current_user_id(request)
    if not user_id:
        return {"status": "ok", "is_following": False}

    try:
        is_following = await _adapter.is_following(
            follower_type="user",
            follower_id=user_id,
            following_type=entity_type,
            following_id=entity_id,
        )
        return {"status": "ok", "is_following": is_following}
    except Exception as e:
        logger.error(f"Failed to check entity following: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check following")
