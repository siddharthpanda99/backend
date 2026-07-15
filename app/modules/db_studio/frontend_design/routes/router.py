"""Module 30 — Frontend Architecture & Design System routes (thin wrappers)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.frontend_design.service import DesignSystemService
from common_lib.modules.db_studio.frontend_design.schemas import (
    UserPreferenceCreate, UserPreferenceOut,
    RecentItemCreate, RecentItemOut,
    UiStateCreate, UiStateOut,
    LayoutPresetCreate, LayoutPresetOut,
    NotificationCreate, NotificationOut,
    CachedQueryCreate, CachedQueryOut,
    DesignDashboardOut,
)

router = APIRouter(tags=["UDS — Frontend Architecture & Design System"])
svc = DesignSystemService()


# ── User Preferences ───────────────────────────────────────────

@router.post("/preferences", response_model=UserPreferenceOut)
def set_preference(body: UserPreferenceCreate):
    return svc.set_preference(body)

@router.get("/preferences/{user_id}/{category}/{key}", response_model=Optional[UserPreferenceOut])
def get_preference(user_id: str, category: str, key: str):
    result = svc.get_preference(user_id, category, key)
    if not result:
        raise HTTPException(404, "Preference not found")
    return result

@router.get("/preferences", response_model=Dict[str, Any])
def list_preferences(user_id: Optional[str] = None, category: Optional[str] = None, limit: int = 100):
    items, total = svc.list_preferences(user_id=user_id, category=category, limit=limit)
    return {"total": total, "items": items}

@router.delete("/preferences/{pref_id}")
def delete_preference(pref_id: str):
    if not svc.delete_preference(pref_id):
        raise HTTPException(404, "Preference not found")
    return {"ok": True}


# ── Recent Items ───────────────────────────────────────────────

@router.post("/recent-items", response_model=RecentItemOut)
def add_recent_item(body: RecentItemCreate):
    return svc.add_recent_item(body)

@router.get("/recent-items/{user_id}", response_model=List[RecentItemOut])
def list_recent_items(user_id: str, item_type: Optional[str] = None, limit: int = 20):
    return svc.list_recent_items(user_id, item_type=item_type, limit=limit)

@router.delete("/recent-items/{user_id}")
def clear_recent_items(user_id: str, item_type: Optional[str] = None):
    count = svc.clear_recent_items(user_id, item_type=item_type)
    return {"deleted": count}


# ── UI State ───────────────────────────────────────────────────

@router.post("/ui-state", response_model=UiStateOut)
def set_ui_state(body: UiStateCreate):
    return svc.set_ui_state(body)

@router.get("/ui-state/{user_id}/{state_key}", response_model=Optional[UiStateOut])
def get_ui_state(user_id: str, state_key: str):
    result = svc.get_ui_state(user_id, state_key)
    if not result:
        raise HTTPException(404, "UI state not found")
    return result

@router.get("/ui-state/{user_id}", response_model=List[UiStateOut])
def list_ui_states(user_id: str):
    return svc.list_ui_states(user_id)

@router.delete("/ui-state/{state_id}")
def delete_ui_state(state_id: str):
    if not svc.delete_ui_state(state_id):
        raise HTTPException(404, "UI state not found")
    return {"ok": True}


# ── Layout Presets ─────────────────────────────────────────────

@router.post("/layout-presets", response_model=LayoutPresetOut)
def create_layout_preset(body: LayoutPresetCreate):
    return svc.create_layout_preset(body)

@router.get("/layout-presets", response_model=Dict[str, Any])
def list_layout_presets(user_id: Optional[str] = None, is_public: Optional[bool] = None, limit: int = 50):
    items, total = svc.list_layout_presets(user_id=user_id, is_public=is_public, limit=limit)
    return {"total": total, "items": items}

@router.delete("/layout-presets/{preset_id}")
def delete_layout_preset(preset_id: str):
    if not svc.delete_layout_preset(preset_id):
        raise HTTPException(404, "Layout preset not found")
    return {"ok": True}


# ── Notifications ──────────────────────────────────────────────

@router.post("/notifications", response_model=NotificationOut)
def create_notification(body: NotificationCreate):
    return svc.create_notification(body)

@router.get("/notifications/{user_id}", response_model=Dict[str, Any])
def list_notifications(
    user_id: str, is_read: Optional[bool] = None,
    notification_type: Optional[str] = None, limit: int = 50,
):
    items, total = svc.list_notifications(
        user_id=user_id, is_read=is_read,
        notification_type=notification_type, limit=limit,
    )
    return {"total": total, "items": items}

@router.put("/notifications/{notification_id}/read", response_model=Optional[NotificationOut])
def mark_notification_read(notification_id: str):
    result = svc.mark_notification_read(notification_id)
    if not result:
        raise HTTPException(404, "Notification not found")
    return result

@router.put("/notifications/{notification_id}/dismiss")
def dismiss_notification(notification_id: str):
    if not svc.dismiss_notification(notification_id):
        raise HTTPException(404, "Notification not found")
    return {"ok": True}

@router.put("/notifications/{user_id}/read-all")
def mark_all_read(user_id: str):
    count = svc.mark_all_read(user_id)
    return {"marked_read": count}


# ── Cached Queries ─────────────────────────────────────────────

@router.post("/cached-queries", response_model=CachedQueryOut)
def cache_query(body: CachedQueryCreate):
    return svc.cache_query(body)

@router.get("/cached-queries/{query_hash}", response_model=Optional[CachedQueryOut])
def get_cached_query(query_hash: str):
    result = svc.get_cached_query(query_hash)
    if not result:
        raise HTTPException(404, "Cached query not found or expired")
    return result

@router.get("/cached-queries", response_model=List[CachedQueryOut])
def list_cached_queries(user_id: Optional[str] = None, limit: int = 50):
    return svc.list_cached_queries(user_id=user_id, limit=limit)

@router.delete("/cached-queries/{cache_id}")
def delete_cached_query(cache_id: str):
    if not svc.delete_cached_query(cache_id):
        raise HTTPException(404, "Cached query not found")
    return {"ok": True}

@router.post("/cached-queries/purge")
def purge_expired_queries():
    count = svc.purge_expired_queries()
    return {"purged": count}


# ── Dashboard ──────────────────────────────────────────────────

@router.get("/dashboard", response_model=DesignDashboardOut)
def design_dashboard():
    return svc.get_dashboard()


# ── Seed ───────────────────────────────────────────────────────

@router.post("/seed")
def seed_frontend_design():
    count = svc.seed_defaults()
    return {"seeded": count}
