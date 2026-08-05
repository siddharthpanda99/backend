"""
Notification Routes — Inbox, Preferences, Mentions.

Endpoints:
- Inbox: GET/POST, GET /unread-count, PATCH /{id}/read, PATCH /read-all, PATCH /{id}/ack, PATCH /{id}/archive, DELETE /{id}
- Preferences: GET/PUT /preferences, GET /quiet-hours, POST /quiet-hours, DELETE /quiet-hours/{id}
- Mentions: POST /mentions/detect, GET /mentions, GET /mentions/stats
"""
from __future__ import annotations

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.modules.auth.dependencies import require_permission


def _get_session():
    from common_lib.modules.integration.adapters.database_adapter import get_db_port
    engine = get_db_port().get_engine()
    return Session(engine)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notification"])


# ===========================================================================
# Inbox
# ===========================================================================


@router.get("/inbox")
def list_notifications(
    user_id: str = Query("system"),
    unread_only: bool = Query(False),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _perm: None = require_permission("notification.read", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """List notifications in a user's inbox."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    items = svc.list_notifications(
        user_id=user_id, unread_only=unread_only,
        event_type=event_type, limit=limit, offset=offset,
    )
    return {"notifications": [i.model_dump() for i in items], "total": len(items)}


@router.post("/inbox")
def deliver_notification(
    user_id: str = Query(...),
    title: str = Query(...),
    body: str = Query(""),
    event_type: str = Query(""),
    priority: str = Query("normal"),
    action_url: Optional[str] = Query(None),
    group_key: Optional[str] = Query(None),
    _perm: None = require_permission("notification.create", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Deliver a notification to a user's inbox."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    item = svc.deliver(
        user_id=user_id, title=title, body=body,
        event_type=event_type, priority=priority,
        action_url=action_url, group_key=group_key,
    )
    return {"id": item.id, "title": item.title}


@router.get("/inbox/unread-count")
def get_unread_count(
    user_id: str = Query("system"),
    _perm: None = require_permission("notification.read", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Get unread notification count."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    return {"unread_count": svc.get_unread_count(user_id)}


@router.patch("/inbox/{notification_id}/read")
def mark_read(
    notification_id: str,
    _perm: None = require_permission("notification.update", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Mark a notification as read."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    success = svc.mark_read(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.patch("/inbox/read-all")
def mark_all_read(
    user_id: str = Query("system"),
    _perm: None = require_permission("notification.update", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Mark all notifications as read."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    return {"marked_count": svc.mark_all_read(user_id)}


@router.patch("/inbox/{notification_id}/acknowledge")
def acknowledge(
    notification_id: str,
    _perm: None = require_permission("notification.update", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Acknowledge a notification."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    success = svc.acknowledge(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.patch("/inbox/{notification_id}/archive")
def archive(
    notification_id: str,
    _perm: None = require_permission("notification.update", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Archive a notification."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    success = svc.archive(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


@router.delete("/inbox/{notification_id}")
def delete_notification(
    notification_id: str,
    _perm: None = require_permission("notification.delete", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Delete a notification."""
    from common_lib.modules.notification.center.service import NotificationCenterService
    svc = NotificationCenterService(session=session)
    success = svc.delete(notification_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"success": True}


# ===========================================================================
# Preferences
# ===========================================================================


@router.get("/preferences")
def get_preferences(
    user_id: str = Query("system"),
    _perm: None = require_permission("notification.read", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Get user notification preferences."""
    from common_lib.modules.notification.preferences.service import NotificationPreferencesService
    svc = NotificationPreferencesService(session=session)
    pref = svc.get_user_preferences(user_id)
    return {
        "user_id": pref.user_id,
        "email_enabled": pref.email_enabled,
        "push_enabled": pref.push_enabled,
        "in_app_enabled": pref.in_app_enabled,
        "sms_enabled": pref.sms_enabled,
        "digest_enabled": pref.digest_enabled,
        "digest_frequency": pref.digest_frequency,
        "quiet_hours_enabled": pref.quiet_hours_enabled,
        "quiet_hours_start": pref.quiet_hours_start,
        "quiet_hours_end": pref.quiet_hours_end,
    }


@router.put("/preferences")
def update_preferences(
    user_id: str = Query("system"),
    updates: dict = {},
    _perm: None = require_permission("notification.update", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Update user notification preferences."""
    from common_lib.modules.notification.preferences.service import NotificationPreferencesService
    svc = NotificationPreferencesService(session=session)
    pref = svc.update_user_preferences(user_id, updates)
    return {"success": True, "user_id": pref.user_id}


@router.get("/preferences/quiet-hours")
def list_quiet_hours(
    user_id: str = Query("system"),
    _perm: None = require_permission("notification.read", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """List quiet hours schedules for a user."""
    from common_lib.modules.notification.preferences.service import NotificationPreferencesService
    svc = NotificationPreferencesService(session=session)
    schedules = svc.list_quiet_hours(user_id)
    return {"schedules": [s.model_dump() for s in schedules], "total": len(schedules)}


@router.post("/preferences/quiet-hours")
def add_quiet_hours(
    user_id: str = Query("system"),
    name: str = Query("default"),
    start_time: str = Query("22:00"),
    end_time: str = Query("08:00"),
    timezone: str = Query("UTC"),
    _perm: None = require_permission("notification.create", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Add a quiet hours schedule."""
    from common_lib.modules.notification.preferences.service import NotificationPreferencesService
    svc = NotificationPreferencesService(session=session)
    schedule = svc.add_quiet_hours(user_id=user_id, name=name, start_time=start_time, end_time=end_time, timezone=timezone)
    return {"id": schedule.id, "name": schedule.name}


@router.delete("/preferences/quiet-hours/{schedule_id}")
def delete_quiet_hours(
    schedule_id: str,
    _perm: None = require_permission("notification.delete", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Delete a quiet hours schedule."""
    from common_lib.modules.notification.preferences.service import NotificationPreferencesService
    svc = NotificationPreferencesService(session=session)
    success = svc.delete_quiet_hours(schedule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {"success": True}


# ===========================================================================
# Mentions
# ===========================================================================


@router.post("/mentions/detect")
def detect_mentions(
    text: str = Query(...),
    entity_type: str = Query(...),
    entity_id: str = Query(...),
    entity_title: str = Query(""),
    mentioned_by_user_id: str = Query("system"),
    _perm: None = require_permission("notification.create", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Detect @mentions in text and deliver notifications."""
    from common_lib.modules.notification.mentions.service import MentionNotificationService
    svc = MentionNotificationService(session=session)
    results = svc.deliver_mentions(
        text=text, entity_type=entity_type, entity_id=entity_id,
        entity_title=entity_title, mentioned_by_user_id=mentioned_by_user_id,
    )
    return {"mentions": results, "count": len(results)}


@router.get("/mentions")
def list_mentions(
    user_id: str = Query("system"),
    entity_type: Optional[str] = Query(None),
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    _perm: None = require_permission("notification.read", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """List @mentions for a user."""
    from common_lib.modules.notification.mentions.service import MentionNotificationService
    svc = MentionNotificationService(session=session)
    items = svc.list_mentions_for_user(
        user_id=user_id, entity_type=entity_type,
        unread_only=unread_only, limit=limit,
    )
    return {"mentions": [i.model_dump() for i in items], "total": len(items)}


@router.get("/mentions/stats")
def mention_stats(
    user_id: str = Query("system"),
    _perm: None = require_permission("notification.read", "*", "notification"),
    session: Session = Depends(_get_session),
):
    """Get @mention statistics."""
    from common_lib.modules.notification.mentions.service import MentionNotificationService
    svc = MentionNotificationService(session=session)
    return svc.get_mention_stats(user_id)
