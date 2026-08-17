"""Reporting — generation (template/definition → formats), office merge, health.

Submodule of the reporting router. Mounted at ``/api/v1/reporting`` with the
``/generate`` / ``/generate/office`` / ``/formats`` / ``/health`` endpoints.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Body, HTTPException

from app.modules.reporting.routes.common import _b64, _rendering

router = APIRouter(tags=["Reporting — Generation"])


@router.post("/generate", summary="Generate a report (template or definition)")
def generate(payload: Dict[str, Any] = Body(...)):
    from common_lib.modules.reporting.core.models import GenerationRequest, OutputFormat

    try:
        request = GenerationRequest(
            template_id=payload.get("template_id", ""),
            data=payload.get("data") or {},
            output_format=OutputFormat.parse(payload.get("format", "pdf")),
            output_formats=[OutputFormat.parse(f) for f in payload.get("formats", [])],
            variables=payload.get("variables") or {},
            title=payload.get("title", ""),
            options=payload.get("options") or {},
        )
        if payload.get("definition"):
            from common_lib.modules.reporting.core.models import TemplateDefinition

            request.definition = TemplateDefinition.from_dict(payload["definition"])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        result = _rendering().generate(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _b64(result.to_dict())


@router.post("/generate/office", summary="Merge data into an office_source template")
def generate_office(payload: Dict[str, Any] = Body(...)):
    template_id = payload.get("template_id", "")
    if not template_id:
        raise HTTPException(status_code=400, detail="'template_id' is required")
    try:
        result = _rendering().generate_office_source(
            template_id,
            payload.get("data") or {},
            target_format=payload.get("format", ""),
            variables=payload.get("variables"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _b64(result.to_dict())


@router.get("/formats", summary="List supported output formats")
def list_formats():
    return {"formats": _rendering().available_formats()}


@router.get("/health", summary="Renderer health + fallback telemetry")
def renderer_health():
    return {"health": _rendering().renderer_health(), "events": _registry_events()}


def _registry_events() -> List[Dict[str, Any]]:
    from common_lib.modules.reporting.render.registry import RendererRegistry

    return RendererRegistry().events()
