"""Reporting — workflow triggers (hooks / schedules / events / conditions).

Submodule of the reporting router. Mounted at ``/api/v1/reporting/triggers``.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from app.modules.reporting.routes.common import _b64, _workflow

router = APIRouter(prefix="/triggers", tags=["Reporting — Workflow Triggers"])


@router.post("", summary="Register a report trigger (hook/schedule/event)")
def register_trigger(payload: Dict[str, Any] = Body(...)):
    result = _workflow().register_trigger(
        template_id=payload.get("template_id", ""),
        trigger_type=payload.get("trigger_type", "hook"),
        output_format=payload.get("format", "pdf"),
        cron=payload.get("cron", ""),
        event=payload.get("event", ""),
        condition=payload.get("condition", ""),
        data_bindings=payload.get("data_bindings"),
    )
    if not result.get("ok", True):
        raise HTTPException(status_code=400, detail=result)
    return result


@router.get("", summary="List report triggers")
def list_triggers(trigger_type: str = Query("")):
    return {"triggers": _workflow().list_triggers(trigger_type)}


@router.post("/fire", summary="Fire event/condition triggers")
def fire_event(payload: Dict[str, Any] = Body(...)):
    results = _workflow().fire_event(payload.get("event", ""), payload.get("payload"))
    return {"results": [_b64(r) if r.get("outputs") else r for r in results]}
