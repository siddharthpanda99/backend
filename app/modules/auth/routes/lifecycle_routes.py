"""Auth User Lifecycle — FastAPI routes for profile and account management.

Provides profile CRUD, deactivation/reactivation, and activity log.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlmodel import Session
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session
from app.modules.auth.dependencies import get_current_active_user
from common_lib.modules.users.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/profile", tags=["auth-lifecycle"])


class ProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    metadata: Optional[dict] = None


class ProfileResponse(BaseModel):
    user_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    phone_number: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"
    department: Optional[str] = None
    job_title: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class DeactivateRequest(BaseModel):
    reason: Optional[str] = None


@router.get("")
def get_profile(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Get the current user's profile."""
    from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
    svc = UserLifecycleService(session)
    profile = svc.get_profile(str(current_user.id))
    if not profile:
        return {"user_id": str(current_user.id)}
    return profile


@router.put("")
def update_profile(
    data: ProfileUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Update the current user's profile."""
    from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
    svc = UserLifecycleService(session)
    updates = data.model_dump(exclude_none=True)
    if "metadata" in updates:
        updates["metadata_json"] = updates.pop("metadata")
    result = svc.update_profile(str(current_user.id), updates)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result


@router.get("/activity")
def get_activity_log(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent activity log for the current user."""
    from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
    svc = UserLifecycleService(session)
    activities = svc.get_activity_log(str(current_user.id), limit=limit)
    return {"activities": activities, "total": len(activities)}


@router.post("/deactivate")
def deactivate_account(
    data: DeactivateRequest = DeactivateRequest(),
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Deactivate the current user's account."""
    from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
    svc = UserLifecycleService(session)
    result = svc.deactivate_user(str(current_user.id), reason=data.reason)
    return result


@router.post("/reactivate")
def reactivate_account(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
    reason: str = Query(None),
):
    """Reactivate the current user's account."""
    from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
    svc = UserLifecycleService(session)
    result = svc.reactivate_user(str(current_user.id), reason=reason)
    return result


@router.get("/deactivation-history")
def get_deactivation_history(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    """Get deactivation/reactivation history."""
    from common_lib.modules.auth.user_lifecycle.service import UserLifecycleService
    svc = UserLifecycleService(session)
    history = svc.get_deactivation_history(str(current_user.id))
    return {"history": history}
