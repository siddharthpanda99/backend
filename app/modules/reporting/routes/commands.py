"""Reporting — agentic command palette (/report-*) + workflow XML run.

Submodule of the reporting router. Mounted at ``/api/v1/reporting`` with the
``/command`` and ``/workflow/run`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException

from app.modules.reporting.routes.common import _b64, _commands

router = APIRouter(tags=["Reporting — Agentic Commands"])


@router.post("/command", summary="Dispatch a /report-* command")
def dispatch_command(payload: Dict[str, Any] = Body(...)):
    command = payload.get("command", "")
    if not command:
        raise HTTPException(status_code=400, detail="'command' is required")
    result = _commands().handle_command(command, payload.get("payload") or {})
    if not result.get("ok", True):
        raise HTTPException(status_code=400, detail=result)
    return _b64(result)


@router.post("/workflow/run", summary="Run a report workflow XML")
def run_workflow(payload: Dict[str, Any] = Body(...)):
    xml = payload.get("xml", "")
    if not xml:
        raise HTTPException(status_code=400, detail="'xml' is required")
    formats = ",".join(payload.get("formats", [payload.get("format", "pdf")]))
    result = _commands().run_workflow_xml(xml, formats, payload.get("data"))
    if not result.get("ok", True):
        raise HTTPException(status_code=400, detail=result)
    return _b64(result)
