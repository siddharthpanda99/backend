"""HTTP surface for the durable cron engine.

Thin router, per the platform's architecture boundary: every route here is a
pydantic request model plus a call into
:mod:`common_lib.modules.triggers.cron`, which owns all logic. No scheduling
arithmetic, no SQL, no flag interpretation lives in this file.

The router is mounted unconditionally so the URLs exist and Swagger documents
them, but every mutating endpoint is gated by ``triggers.cron_durable_schedules``
and answers ``503`` with the flag name when it is off. Returning 503 rather than
silently succeeding is deliberate: a client that created a schedule and got a 200
would reasonably believe it was scheduled.

Registered in ``app/core/routers.py`` as a *separate* router from the existing
``app.modules.triggers.routes`` rather than being appended to it, so this change
does not touch a file another session may be editing.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.triggers.cron.expression import CronError
from common_lib.modules.triggers.cron.service import CronService
from common_lib.modules.triggers.feature_flags import (
    cron_durable_schedules_enabled,
    cron_resolve_targets_enabled,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/triggers/cron", tags=["Cron Schedules"])


# ── Schemas ─────────────────────────────────────────────────────────


class CronScheduleCreate(BaseModel):
    cron_expression: str = Field(
        ...,
        description="Standard 5-field cron: 'minute hour day-of-month month "
        "day-of-week'. Supports *, ranges, steps, lists, and month/day names.",
        examples=["0 9 * * mon-fri"],
    )
    target_id: str = Field(
        ...,
        description="A registered @node name, or a registered workflow id.",
    )
    target_type: str = Field(
        default="node",
        description="'node' (a @node name) or 'workflow' (a workflow id)",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA zone the expression is evaluated in. Storage is always UTC.",
    )
    name: str = ""
    description: str = ""
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Keyword arguments passed to the target on each fire.",
    )
    max_fires: Optional[int] = Field(
        default=None, description="Stop after this many fires. Omit for unlimited."
    )
    schedule_id: Optional[str] = Field(
        default=None, description="Supply your own id instead of a generated one."
    )
    enabled: bool = True


class CronScheduleUpdate(BaseModel):
    enabled: bool


class CronValidateRequest(BaseModel):
    cron_expression: str
    timezone: str = "UTC"
    count: int = Field(default=5, ge=1, le=50)


# ── Helpers ─────────────────────────────────────────────────────────


def _require_flag() -> None:
    """Refuse with 503 when durable cron is off.

    A 200 here would be a lie: the write would not happen, or would land
    somewhere that does not survive a restart.
    """
    if not cron_durable_schedules_enabled():
        raise HTTPException(
            status_code=503,
            detail=(
                "Durable cron schedules are disabled. Enable the "
                "'triggers.cron_durable_schedules' feature flag to use this "
                "endpoint."
            ),
        )


def _service() -> CronService:
    return CronService()


def _reject(result: dict[str, Any]) -> None:
    """Turn a service-level rejection into the right HTTP status.

    422 for a bad request (invalid cron, unsupported type, unresolvable target),
    404 for a missing schedule. Only then is 200 the correct answer.
    """
    status = result.get("status")
    if status in ("rejected", "error"):
        detail = result.get("error") or result.get("reason") or status
        code = 422 if status == "rejected" else 503
        raise HTTPException(status_code=code, detail=f"{status}: {detail}")
    if status == "not_found":
        raise HTTPException(
            status_code=404, detail=f"schedule {result.get('schedule_id')!r} not found"
        )


# ── Endpoints ───────────────────────────────────────────────────────


@router.post("/validate")
def validate_cron(body: CronValidateRequest):
    """Validate a cron expression and preview its next fire times.

    Read-only and never flag-gated: checking whether an expression is valid
    should not require turning a feature on, and this endpoint writes nothing.
    """
    from common_lib.modules.triggers.cron.expression import CronExpression
    from common_lib.modules.triggers.cron.models import utcnow

    try:
        parsed = CronExpression.parse(body.cron_expression, body.timezone)
    except CronError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    upcoming = []
    cursor = utcnow()
    try:
        for _ in range(body.count):
            cursor = parsed.next_fire_after(cursor)
            upcoming.append(cursor.isoformat())
    except CronError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "valid": True,
        "expression": parsed.expression,
        "timezone": parsed.timezone_name,
        "upcoming": upcoming,
    }


@router.post("")
def create_schedule(body: CronScheduleCreate, session: Session = Depends(get_session)):
    """Create a durable cron schedule.

    Returns 201 with the persisted schedule. If the target cannot be resolved and
    ``triggers.cron_resolve_targets`` is on, returns 422 and writes nothing — a
    schedule that can never fire is worse than no schedule, because it reads as
    configured work that is silently not happening.
    """
    _require_flag()
    result = _service().create_schedule(
        session,
        cron_expression=body.cron_expression,
        target_id=body.target_id,
        target_type=body.target_type,
        timezone_name=body.timezone,
        name=body.name,
        description=body.description,
        payload=body.payload or None,
        enabled=body.enabled,
        max_fires=body.max_fires,
        schedule_id=body.schedule_id,
        require_resolved_target=cron_resolve_targets_enabled(),
    )
    _reject(result)
    return result


@router.get("")
def list_schedules(
    enabled_only: bool = False,
    target_type: Optional[str] = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    """List durable schedules with their next fire time and target state."""
    _require_flag()
    service = _service()
    rows = service.list_schedules(
        session, enabled_only=enabled_only, target_type=target_type, limit=limit
    )
    schedules = [service._schedule_dict(r) for r in rows]  # noqa: SLF001
    return {"count": len(schedules), "schedules": schedules}


@router.get("/{schedule_id}")
def get_schedule(schedule_id: str, session: Session = Depends(get_session)):
    """Fetch one schedule by id."""
    _require_flag()
    service = _service()
    row = service.get_schedule(session, schedule_id)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"schedule {schedule_id!r} not found"
        )
    return service._schedule_dict(row)  # noqa: SLF001


@router.get("/{schedule_id}/preview")
def preview_schedule(
    schedule_id: str,
    count: int = Query(default=5, ge=1, le=50),
    session: Session = Depends(get_session),
):
    """The next N fire times, without claiming, firing, or changing anything."""
    _require_flag()
    result = _service().preview(session, schedule_id, count)
    _reject(result)
    return result


@router.patch("/{schedule_id}")
def update_schedule(
    schedule_id: str, body: CronScheduleUpdate, session: Session = Depends(get_session)
):
    """Enable or disable a schedule **without deleting it**.

    Disabling keeps the definition and its full execution history.
    """
    _require_flag()
    result = _service().set_enabled(session, schedule_id, body.enabled)
    _reject(result)
    return result


@router.post("/{schedule_id}/run")
def run_schedule_now(schedule_id: str, session: Session = Depends(get_session)):
    """Fire a schedule immediately (runbook manual trigger).

    The regular next-fire cursor is not disturbed, so a manual fire does not
    shift the timetable. The fire is recorded in history with ``manual=true``.
    """
    _require_flag()
    result = _service().run_now(session, schedule_id)
    _reject(result)
    return result


@router.get("/{schedule_id}/history")
def schedule_history(
    schedule_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """Execution history, most recent first.

    Each entry carries the *scheduled* time, the actual start and finish, the
    outcome, and any error. The gap between ``scheduled_for`` and ``started_at``
    is the honest measure of whether a worker was healthy.
    """
    _require_flag()
    service = _service()
    if service.get_schedule(session, schedule_id) is None:
        raise HTTPException(
            status_code=404, detail=f"schedule {schedule_id!r} not found"
        )
    rows = service.history(session, schedule_id, limit)
    return {"count": len(rows), "history": rows}


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: str, session: Session = Depends(get_session)):
    """Permanently delete a schedule. Prefer disabling: this keeps no history."""
    _require_flag()
    result = _service().delete_schedule(session, schedule_id)
    _reject(result)
    return result


@router.get("/-/engine")
def engine_status():
    """Background engine status: running state, worker id, sleep policy."""
    from common_lib.modules.triggers.cron.engine import get_engine

    return {
        **get_engine().status(),
        "durable_schedules_enabled": cron_durable_schedules_enabled(),
        "resolve_targets_enabled": cron_resolve_targets_enabled(),
    }
