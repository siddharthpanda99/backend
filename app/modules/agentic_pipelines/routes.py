"""Agentic Pipelines — REST API routes.

Mounted at ``/api/v1/agentic-pipelines``. Thin-router convention: all logic
delegates to ``common_lib.modules.agentic_pipelines``.

Endpoints:
* Definitions — POST /, GET /, GET /{id}, PATCH /{id}, DELETE /{id}, POST /sync
* Runs — POST /runs (execute), GET /runs, GET /runs/{id}, DELETE /runs/{id}
* Artifacts — GET /runs/{id}/artifacts, GET /artifacts/{id}
* Self-learning — POST /runs/{id}/gaps, GET /requirements, POST /requirements/{id}/done
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from common_lib.modules.agentic_pipelines.schemas import (
    ArtifactExportRequest,
    PipelineDefinitionCreate,
    PipelineDefinitionUpdate,
    PipelineRunCreate,
    RequirementCreate,
)
from common_lib.modules.agentic_pipelines.service import (
    AgenticPipelineService,
    get_agentic_pipeline_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _service() -> AgenticPipelineService:
    return get_agentic_pipeline_service()


# ── Definitions ────────────────────────────────────────────────────────────


@router.post("", tags=["Agentic Pipelines"])
def create_pipeline(data: PipelineDefinitionCreate) -> Dict[str, Any]:
    result = _service().create_definition(data)
    if result and "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return result or {}


@router.get("", tags=["Agentic Pipelines"])
def list_pipelines(
    category: str = "", enabled_only: bool = False
) -> List[Dict[str, Any]]:
    return _service().list_definitions(category=category, enabled_only=enabled_only)


@router.post("/sync", tags=["Agentic Pipelines"])
def sync_pipelines() -> Dict[str, Any]:
    """Load all definition YAMLs from the catalogue and upsert them."""
    from common_lib.modules.agentic_pipelines.loader import sync_definitions_to_db

    return sync_definitions_to_db()


# NOTE: parameterized definition routes (GET/PATCH/DELETE /{pipeline_id}) are
# declared at the END of this module on purpose — FastAPI matches routes in
# declaration order, so static paths like /runs, /requirements and /artifacts
# must be registered first or they get swallowed by /{pipeline_id}.

# ── Runs ───────────────────────────────────────────────────────────────────


@router.post("/runs", tags=["Agentic Pipelines"])
def run_pipeline(req: PipelineRunCreate) -> Dict[str, Any]:
    result = _service().run_pipeline(
        pipeline_id=req.pipeline_id,
        pipeline_slug=req.pipeline_slug,
        input_text=req.input,
        inputs=req.inputs,
        context_sources=req.context_sources,
        session_id=req.session_id,
        use_llm=req.use_llm,
        export_formats=req.export_formats,
    )
    # NOTE: a successful run dict always includes an empty ``error`` field
    # (from PipelineRun.to_dict), so use a TRUTHY check — ``"error" in result``
    # would 404 every successful run.
    if result and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result or {}


@router.get("/runs", tags=["Agentic Pipelines"])
def list_runs(pipeline_id: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    return _service().list_runs(pipeline_id=pipeline_id, limit=min(limit, 500))


@router.get("/runs/{run_id}", tags=["Agentic Pipelines"])
def get_run(run_id: str) -> Dict[str, Any]:
    result = _service().get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@router.delete("/runs/{run_id}", tags=["Agentic Pipelines"])
def delete_run(run_id: str) -> Dict[str, Any]:
    if not _service().delete_run(run_id):
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {"deleted": True, "id": run_id}


# ── Artifacts ──────────────────────────────────────────────────────────────


@router.post("/runs/{run_id}/export", tags=["Agentic Pipelines"])
def export_run(
    run_id: str, req: ArtifactExportRequest | None = None
) -> Dict[str, Any]:
    # Accept either the path run_id (matching the body, when provided) or the
    # body's run_id. ``formats`` defaults to None → exporter defaults.
    effective_id = run_id or (req.run_id if req else None)
    formats = req.formats if (req and req.formats) else None
    artifacts = _service().export_run(effective_id, formats=formats)
    return {"run_id": effective_id, "artifacts": artifacts}


@router.get("/runs/{run_id}/artifacts", tags=["Agentic Pipelines"])
def list_artifacts(run_id: str) -> List[Dict[str, Any]]:
    return _service().list_artifacts(run_id)


@router.get("/artifacts/{artifact_id}", tags=["Agentic Pipelines"])
def get_artifact(artifact_id: str) -> Dict[str, Any]:
    result = _service().get_artifact(artifact_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Artifact {artifact_id} not found"
        )
    return result


# ── Self-learning ──────────────────────────────────────────────────────────


@router.post("/runs/{run_id}/gaps", tags=["Agentic Pipelines"])
def detect_gaps(
    run_id: str,
    available_capabilities: Optional[List[str]] = None,
    file_tickets: bool = True,
) -> Dict[str, Any]:
    requirements = _service().detect_gaps_and_file(
        run_id,
        available_capabilities=available_capabilities,
        file_tickets=file_tickets,
    )
    return {"run_id": run_id, "requirements": requirements}


@router.get("/requirements", tags=["Agentic Pipelines"])
def list_requirements(
    pipeline_id: str = "", status: str = ""
) -> List[Dict[str, Any]]:
    return _service().list_requirements(pipeline_id=pipeline_id, status=status)


@router.post("/requirements/{requirement_id}/done", tags=["Agentic Pipelines"])
def mark_requirement_done(requirement_id: str) -> Dict[str, Any]:
    result = _service().mark_requirement_done(requirement_id)
    if result is None:
        raise HTTPException(
            status_code=404, detail=f"Requirement {requirement_id} not found"
        )
    return result


# ── Definitions (parameterized — MUST stay last) ───────────────────────────


@router.get("/{pipeline_id}", tags=["Agentic Pipelines"])
def get_pipeline(pipeline_id: str) -> Dict[str, Any]:
    result = _service().get_definition(pipeline_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")
    return result


@router.patch("/{pipeline_id}", tags=["Agentic Pipelines"])
def update_pipeline(
    pipeline_id: str, data: PipelineDefinitionUpdate
) -> Dict[str, Any]:
    result = _service().update_definition(pipeline_id, data)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")
    return result


@router.delete("/{pipeline_id}", tags=["Agentic Pipelines"])
def delete_pipeline(pipeline_id: str) -> Dict[str, Any]:
    if not _service().delete_definition(pipeline_id):
        raise HTTPException(status_code=404, detail=f"Pipeline {pipeline_id} not found")
    return {"deleted": True, "id": pipeline_id}
