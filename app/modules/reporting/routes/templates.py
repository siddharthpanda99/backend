"""Reporting — template CRUD, versioning, seeding + office-source create.

Submodule of the reporting router (mirrors the ``routes/`` layout used by
``dip``/``hitl``/``knowledge``). Mounted at ``/api/v1/reporting/templates``.
"""

from __future__ import annotations

import base64
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Query

from app.modules.reporting.routes.common import _templates

router = APIRouter(prefix="/templates", tags=["Reporting — Templates"])


@router.get("", summary="List report templates")
def list_templates(
    category: str = Query("", description="Filter by category"),
    status: str = Query("", description="Filter by status"),
):
    return {
        "templates": _templates().list(category=category or None, status=status or None)
    }


@router.post("/seed", summary="Seed built-in report templates")
def seed_templates(force: bool = Body(False, embed=True)):
    return {"seeded": _templates().seed_all(force=force)}


@router.get("/{template_id}", summary="Get a report template")
def get_template(template_id: str):
    template = _templates().get(template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )
    return template.to_dict()


@router.post("", summary="Create a report template")
def create_template(payload: Dict[str, Any] = Body(...)):
    definition = payload.get("definition")
    if not definition:
        raise HTTPException(status_code=400, detail="'definition' is required")
    from common_lib.modules.reporting.core.models import TemplateDefinition

    template = _templates().create(
        TemplateDefinition.from_dict(definition),
        key=payload.get("key", ""),
        author=payload.get("author", ""),
    )
    return template.to_dict()


@router.post(
    "/office", summary="Create an office_source template from an uploaded file"
)
def create_office_template(payload: Dict[str, Any] = Body(...)):
    source_b64 = payload.get("source_b64", "")
    if not source_b64:
        raise HTTPException(status_code=400, detail="'source_b64' is required")
    try:
        template = _templates().create_from_office(
            base64.b64decode(source_b64),
            source_format=payload.get("source_format", "docx"),
            title=payload.get("title", ""),
            category=payload.get("category", "general"),
            key=payload.get("key", ""),
            author=payload.get("author", ""),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=400, detail=f"Office template create failed: {exc}"
        ) from exc
    return template.to_dict()


@router.post("/{template_id}/publish", summary="Publish a template")
def publish_template(template_id: str):
    template = _templates().publish(template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )
    return template.to_dict()


@router.post("/{template_id}/archive", summary="Archive a template")
def archive_template(template_id: str):
    template = _templates().archive(template_id)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )
    return template.to_dict()


@router.get("/{template_id}/versions", summary="Template version history (Phase 14)")
def template_history(template_id: str):
    return {"versions": _templates().version_history(template_id)}


@router.get(
    "/{template_id}/diff",
    summary="Structural diff between two template versions (Phase 14)",
)
def template_diff(
    template_id: str, from_version: int = Query(1), to_version: int = Query(2)
):
    result = _templates().diff_versions(template_id, from_version, to_version)
    if not result.get("ok"):
        raise HTTPException(status_code=404, detail=result.get("error", "diff failed"))
    return result


@router.post(
    "/{template_id}/rollback", summary="Roll a template back to a version (Phase 14)"
)
def template_rollback(template_id: str, payload: Dict[str, Any] = Body(...)):
    version = int(payload.get("version", 1))
    template = _templates().rollback(template_id, version)
    if template is None:
        raise HTTPException(
            status_code=404, detail=f"Template not found: {template_id}"
        )
    return template.to_dict()
