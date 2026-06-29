"""
Workflow Compiler Routes — Phase 2 of the AAR Implementation

Adds compiler endpoints directly onto the existing /workflows router:

  POST   /api/v1/workflows/{workflow_id}/compile
  GET    /api/v1/workflows/{workflow_id}/compile/status
  GET    /api/v1/workflows/{workflow_id}/app
  DELETE /api/v1/workflows/{workflow_id}/app        (removes compiled app)

The compile endpoint runs all 5 WorkflowCompiler phases synchronously
and returns the full AppManifest, ready for the frontend to use as
scaffoldedApp state in AppBuilderWorkspacePage.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.compiler import WorkflowCompiler
from common_lib.modules.app_builder.ecosystem.models import AppRecord

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class CompileRequest(BaseModel):
    """Optional overrides for the compile operation."""
    overwrite: bool = False
    """If True, delete and recompile an existing app for this workflow."""


class CompileResponse(BaseModel):
    """Full response from a compile operation."""
    status: str
    message: str
    app_id: str
    workflow_id: str
    is_new: bool
    complexity: str
    layout_template: str
    preset_count: int
    binding_count: int
    manifest: Dict[str, Any]


class CompileStatusResponse(BaseModel):
    """Summary of the compilation status for a workflow."""
    workflow_id: str
    compiled: bool
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    complexity: Optional[str] = None
    layout_template: Optional[str] = None
    input_count: Optional[int] = None
    output_count: Optional[int] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "/{workflow_id}/compile",
    response_model=CompileResponse,
    status_code=200,
    summary="Compile a workflow into a deployable App",
    description=(
        "Runs the full WorkflowCompiler pipeline (5 phases):\n\n"
        "1. **Graph Analysis** — parse YAML, detect terminal nodes, compute DAG metrics\n"
        "2. **Schema Inference** — map parameters → InputFields, terminal nodes → OutputWidgets\n"
        "3. **Complexity Score** — SPA_SIMPLE / SPA_STANDARD / MPA_MODERATE / MPA_FULL\n"
        "4. **Manifest Generation** — assemble full AppManifest (canvas tree, data sources)\n"
        "5. **DB Persistence** — create AppRecord + CanvasPresets + DataBindings + DesignTokens\n\n"
        "The returned `manifest` object can be passed directly as `scaffoldedApp` state "
        "when navigating to AppBuilderWorkspacePage."
    ),
)
async def compile_workflow(
    workflow_id: str,
    body: CompileRequest = Body(default=CompileRequest()),
    db: Session = Depends(get_session),
) -> CompileResponse:
    """
    Compile workflow YAML → deployable App.

    Returns the AppManifest and a summary of what was created.
    If the workflow has already been compiled and `overwrite=False`,
    returns the existing app info immediately (idempotent).
    """
    logger.info(
        f"[CompileRoute] Compile request: workflow_id={workflow_id!r} "
        f"overwrite={body.overwrite}"
    )

    try:
        compiler = WorkflowCompiler(db)
        result = compiler.compile(workflow_id, overwrite=body.overwrite)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_id}' not found. "
                   f"Make sure its YAML file exists in templates/workflows/executable/. "
                   f"Detail: {exc}",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Workflow YAML is invalid: {exc}",
        )
    except RuntimeError as exc:
        logger.exception(f"[CompileRoute] Compilation failed for '{workflow_id}'")
        raise HTTPException(
            status_code=500,
            detail=f"Compilation failed: {exc}",
        )

    manifest = result["manifest"]
    input_count = len(manifest.get("input_schema", []))
    output_count = len(manifest.get("output_schema", []))

    verb = "Compiled" if result["is_new"] else "Already compiled"
    message = (
        f"{verb} workflow '{workflow_id}' → app '{result['app_id']}' "
        f"({result['complexity']}, {input_count} inputs, {output_count} outputs)"
    )

    logger.info(f"[CompileRoute] {message}")

    return CompileResponse(
        status="success",
        message=message,
        app_id=result["app_id"],
        workflow_id=workflow_id,
        is_new=result["is_new"],
        complexity=result["complexity"],
        layout_template=result["layout_template"],
        preset_count=len(result.get("preset_ids", [])),
        binding_count=len(result.get("binding_ids", [])),
        manifest=manifest,
    )


@router.get(
    "/{workflow_id}/compile/status",
    response_model=CompileStatusResponse,
    summary="Check if a workflow has been compiled into an App",
)
async def get_compile_status(
    workflow_id: str,
    db: Session = Depends(get_session),
) -> CompileStatusResponse:
    """
    Check whether a workflow has already been compiled.
    Does NOT trigger compilation — use POST to compile.
    """
    app_id = f"app-{workflow_id}"
    record: Optional[AppRecord] = db.execute(
        select(AppRecord).where(AppRecord.id == app_id)
    ).scalar_one_or_none()

    if not record:
        return CompileStatusResponse(
            workflow_id=workflow_id,
            compiled=False,
        )

    # Reconstruct summary from the DB record description (no YAML re-parse needed)
    description = record.description or ""
    complexity = "unknown"
    layout_template = "unknown"

    if "Template:" in description:
        try:
            layout_template = description.split("Template:")[-1].strip().rstrip(".")
        except Exception:
            pass

    return CompileStatusResponse(
        workflow_id=workflow_id,
        compiled=True,
        app_id=record.id,
        app_name=record.name,
        complexity=complexity,
        layout_template=layout_template,
    )


@router.get(
    "/{workflow_id}/app",
    summary="Get the compiled App manifest for a workflow",
)
async def get_workflow_app(
    workflow_id: str,
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Return the existing compiled app record for a workflow.
    Returns 404 if the workflow has not yet been compiled.
    Use `POST /{workflow_id}/compile` to compile it first.
    """
    app_id = f"app-{workflow_id}"
    record: Optional[AppRecord] = db.execute(
        select(AppRecord).where(AppRecord.id == app_id)
    ).scalar_one_or_none()

    if not record:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No compiled app found for workflow '{workflow_id}'. "
                f"Call POST /workflows/{workflow_id}/compile first."
            ),
        )

    return {
        "status": "success",
        "data": {
            "app_id": record.id,
            "workflow_id": workflow_id,
            "name": record.name,
            "description": record.description,
            "icon": record.icon,
            "category": record.category,
            "version": record.version,
            "status": record.status,
            "pages": record.pages,
        },
    }


@router.delete(
    "/{workflow_id}/app",
    status_code=200,
    summary="Delete a compiled App for a workflow",
    description=(
        "Removes all DB records created by the compiler for this workflow's app "
        "(CanvasPresets, DataBindings, DesignTokens, AppSettings, AppRecord). "
        "Does NOT delete the workflow YAML itself."
    ),
)
async def delete_workflow_app(
    workflow_id: str,
    db: Session = Depends(get_session),
) -> Dict[str, Any]:
    """
    Delete the compiled App for a workflow.
    Idempotent — returns success even if the app doesn't exist.
    """
    app_id = f"app-{workflow_id}"
    record: Optional[AppRecord] = db.execute(
        select(AppRecord).where(AppRecord.id == app_id)
    ).scalar_one_or_none()

    if not record:
        return {
            "status": "success",
            "message": f"No compiled app found for workflow '{workflow_id}' — nothing to delete.",
            "app_id": app_id,
            "deleted": False,
        }

    try:
        compiler = WorkflowCompiler(db)
        compiler._delete_app_records(app_id)
        logger.info(f"[CompileRoute] Deleted compiled app '{app_id}' for workflow '{workflow_id}'")
    except Exception as exc:
        db.rollback()
        logger.exception(f"[CompileRoute] Delete failed for '{app_id}'")
        raise HTTPException(status_code=500, detail=f"Delete failed: {exc}")

    return {
        "status": "success",
        "message": f"Compiled app '{app_id}' deleted for workflow '{workflow_id}'.",
        "app_id": app_id,
        "deleted": True,
    }
