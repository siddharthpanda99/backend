"""
Control Center API Routes — centralized platform observability.

Routes:
  GET  /api/v1/control-center/dashboard     — Dashboard summary
  GET  /api/v1/control-center/activity      — Activity feed with filters
  GET  /api/v1/control-center/activity/stats — Activity statistics
  GET  /api/v1/control-center/audit         — Audit trail with filters
  GET  /api/v1/control-center/audit/stats   — Audit statistics
  GET  /api/v1/control-center/users         — User list with roles
  GET  /api/v1/control-center/users/overview — User statistics
  GET  /api/v1/control-center/rbac          — RBAC overview
  POST /api/v1/control-center/activity      — Record an activity (internal)
  POST /api/v1/control-center/audit         — Record an audit entry (internal)
"""
import json
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from common_lib.modules.control_center.service import ControlCenterService

router = APIRouter(prefix="/api/v1/control-center", tags=["control-center"])


def get_db():
    """Dependency — yield a DB session from the connection pool."""
    from sqlmodel import Session as SQLSession
    from common_lib.modules.data_storage.database.connection import engine

    with SQLSession(engine) as session:
        yield session


def get_service(session: DbSession = Depends(get_db)) -> ControlCenterService:
    return ControlCenterService(session)


def require_admin_or_auditor():
    """Dependency — only admin or auditor roles may access control center.
    Bypassed in DEV_MODE for local development."""
    from app.modules.auth.dependencies import get_current_active_user
    from app.core.settings import get_settings

    async def _check(user=Depends(get_current_active_user)):
        if get_settings().DEV_MODE:
            return user
        role = getattr(user, "role", None)
        if role not in ("admin", "auditor", "super_admin"):
            raise HTTPException(status_code=403, detail="Requires admin or auditor role")
        return user

    return _check


# ── Dashboard ──────────────────────────────────────────────────────────────

@router.get("/dashboard", dependencies=[Depends(require_admin_or_auditor())])
def dashboard_summary(svc: ControlCenterService = Depends(get_service)):
    """Unified dashboard: activity, audit, users, RBAC at a glance."""
    return svc.get_dashboard_summary()


# ── Activity Feed ──────────────────────────────────────────────────────────

@router.get("/activity", dependencies=[Depends(require_admin_or_auditor())])
def activity_feed(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    category: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    hours: Optional[int] = Query(None, ge=1, le=168),
    svc: ControlCenterService = Depends(get_service),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None
    return {
        "items": svc.get_activity_feed(
            limit=limit, offset=offset, category=category,
            severity=severity, user_id=user_id, resource_type=resource_type,
            since=since,
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/activity/stats", dependencies=[Depends(require_admin_or_auditor())])
def activity_stats(
    hours: int = Query(24, ge=1, le=168),
    svc: ControlCenterService = Depends(get_service),
):
    return svc.get_activity_stats(hours=hours)


# ── Audit Trail ────────────────────────────────────────────────────────────

@router.get("/audit", dependencies=[Depends(require_admin_or_auditor())])
def audit_trail(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action_category: Optional[str] = None,
    severity: Optional[str] = None,
    user_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    success_only: Optional[bool] = None,
    hours: Optional[int] = Query(None, ge=1, le=168),
    svc: ControlCenterService = Depends(get_service),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours) if hours else None
    return {
        "items": svc.get_audit_trail(
            limit=limit, offset=offset, action_category=action_category,
            severity=severity, user_id=user_id, resource_type=resource_type,
            success_only=success_only, since=since,
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit/stats", dependencies=[Depends(require_admin_or_auditor())])
def audit_stats(
    hours: int = Query(24, ge=1, le=168),
    svc: ControlCenterService = Depends(get_service),
):
    return svc.get_audit_stats(hours=hours)


# ── Users ──────────────────────────────────────────────────────────────────

@router.get("/users", dependencies=[Depends(require_admin_or_auditor())])
def user_list(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    svc: ControlCenterService = Depends(get_service),
):
    return {
        "items": svc.get_user_list(limit=limit, offset=offset),
        "limit": limit,
        "offset": offset,
    }


@router.get("/users/overview", dependencies=[Depends(require_admin_or_auditor())])
def user_overview(svc: ControlCenterService = Depends(get_service)):
    return svc.get_users_overview()


# ── RBAC ───────────────────────────────────────────────────────────────────

@router.get("/rbac", dependencies=[Depends(require_admin_or_auditor())])
def rbac_overview(svc: ControlCenterService = Depends(get_service)):
    return svc.get_rbac_overview()


# ── Entity Audit (cross-system integration) ─────────────────────────────────

@router.get("/entity-audit", dependencies=[Depends(require_admin_or_auditor())])
def entity_audit_recent(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    entity_type: Optional[str] = None,
    action: Optional[str] = None,
    actor_id: Optional[str] = None,
    svc: ControlCenterService = Depends(get_service),
):
    """Recent entity-level audit entries (from entity_audit_log table)."""
    return {
        "items": svc.get_entity_audit_recent(
            limit=limit, offset=offset, entity_type=entity_type,
            action=action, actor_id=actor_id,
        ),
        "limit": limit,
        "offset": offset,
    }


@router.get("/entity-audit/stats", dependencies=[Depends(require_admin_or_auditor())])
def entity_audit_stats(
    hours: int = Query(24, ge=1, le=168),
    svc: ControlCenterService = Depends(get_service),
):
    """Aggregate entity audit statistics."""
    return svc.get_entity_audit_stats(hours=hours)


@router.get("/entity-audit/versions", dependencies=[Depends(require_admin_or_auditor())])
def entity_versions_summary(
    hours: int = Query(24, ge=1, le=168),
    svc: ControlCenterService = Depends(get_service),
):
    """Aggregate version snapshot statistics."""
    return svc.get_entity_versions_summary(hours=hours)


# ── SSE Streaming ─────────────────────────────────────────────────────────

@router.get("/stream", dependencies=[Depends(require_admin_or_auditor())])
def control_center_stream():
    """Server-Sent Events stream for real-time Control Center updates.

    Pushes dashboard summary every N seconds and new activity/audit entries
    as they appear. Clients connect with EventSource and receive:
      - event: dashboard  → full dashboard refresh data
      - event: activity   → new activity log entries
      - event: audit      → new audit trail entries
      - event: heartbeat  → keepalive every 15s
    """
    import time

    async def event_generator():
        from sqlmodel import Session as SQLSession
        from common_lib.modules.data_storage.database.connection import engine
        # Initialize to current time so only new entries are pushed after connection
        now_iso = datetime.now(timezone.utc).isoformat()
        last_activity_ts = now_iso
        last_audit_ts = now_iso
        last_entity_audit_ts = now_iso
        tick = 0

        while True:
            tick += 1
            try:
                with SQLSession(engine) as session:
                    svc = ControlCenterService(session)

                    # Every 3rd tick (≈30s at 10s interval): full dashboard
                    if tick % 3 == 0:
                        dashboard = svc.get_dashboard_summary()
                        yield f"event: dashboard\ndata: {json.dumps(dashboard)}\n\n"

                    # Every tick: check for new activity entries (by timestamp, not ID)
                    new_activities = svc.get_activity_feed(limit=20, offset=0)
                    fresh_activities = [
                        a for a in new_activities
                        if a.get("timestamp") and (not last_activity_ts or a["timestamp"] > last_activity_ts)
                    ]
                    if fresh_activities:
                        last_activity_ts = max(a["timestamp"] for a in fresh_activities)
                        yield f"event: activity\ndata: {json.dumps(fresh_activities)}\n\n"

                    # Every tick: check for new audit entries (by timestamp)
                    new_audits = svc.get_audit_trail(limit=20, offset=0)
                    fresh_audits = [
                        a for a in new_audits
                        if a.get("timestamp") and (not last_audit_ts or a["timestamp"] > last_audit_ts)
                    ]
                    if fresh_audits:
                        last_audit_ts = max(a["timestamp"] for a in fresh_audits)
                        yield f"event: audit\ndata: {json.dumps(fresh_audits)}\n\n"

                    # Every tick: check for new entity audit entries (by created_at timestamp)
                    new_entity = svc.get_entity_audit_recent(limit=20, offset=0)
                    fresh_entity = [
                        e for e in new_entity
                        if e.get("created_at") and (not last_entity_audit_ts or e["created_at"] > last_entity_audit_ts)
                    ]
                    if fresh_entity:
                        last_entity_audit_ts = max(e["created_at"] for e in fresh_entity)
                        yield f"event: entity_audit\ndata: {json.dumps(fresh_entity)}\n\n"

            except Exception as exc:
                yield f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n"

            # Heartbeat every tick to keep connection alive
            yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now(timezone.utc).isoformat()})}\n\n"

            await asyncio.sleep(10)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
