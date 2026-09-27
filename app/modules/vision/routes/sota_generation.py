"""SOTA Image Generation REST endpoints — thin routers over the jobs module.

Models: Krea 2, Qwen-Image-2.1, Ming-Image-0.1-Design
All generation runs as jobs (DB-shaped ``JobRecord`` via the jobs module);
artifacts live on disk and only ref strings land in ``result_refs``.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common_lib.modules.vision.sota_generation_service import (
    MODE_CAPABILITIES,
    SAMPLE_BATCH_JSON,
    SUPPORTED_MODELS,
    validate_model,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sota", tags=["SOTA Image Generation"])


# ---------------------------------------------------------------------------
# Request/Response Models
# ---------------------------------------------------------------------------


class SOTASingleRequest(BaseModel):
    """Single prompt generation request."""

    prompt: str = Field(..., description="Text prompt for generation")
    negative_prompt: str = Field("", description="Negative prompt")
    model: str = Field(..., description="Model identifier: krea-2-turbo, qwen21, ming")
    width: int = Field(1024, description="Width in pixels (multiple of 16/32)")
    height: int = Field(1024, description="Height in pixels (multiple of 16/32)")
    steps: int = Field(20, description="Number of inference steps")
    cfg: float = Field(1.0, description="Guidance scale (CFG)")
    seed: int = Field(0, description="Random seed (0 = random)")
    device: str = Field("cuda", description="Device: cuda or cpu")


class SOTASingleResponse(BaseModel):
    """Single prompt generation response."""

    task_id: str
    job_id: str
    status: str = "queued"
    message: str
    model: str


class SOTABatchRequest(BaseModel):
    """Batch generation request from JSON."""

    model: str = Field(..., description="Model identifier: krea-2-turbo, qwen21, ming")
    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of generation items. Each item: "
        '{"prompt": str, "mode": "txt2img|img2img|inpaint|outpaint", '
        '"params": {"width": int, "height": int, "steps": int, "cfg": float, "seed": int, '
        '"strength": float, "pad": int, "source": int, "mask": str}}',
    )
    device: str = Field("cuda", description="Device: cuda or cpu")
    output_dir: Optional[str] = Field(None, description="Custom output directory")


class SOTABatchResponse(BaseModel):
    """Batch generation response."""

    task_id: str
    job_id: str
    status: str = "queued"
    message: str
    model: str
    total_items: int


class SOTATaskStatus(BaseModel):
    """Task status response."""

    task_id: str
    job_id: Optional[str] = None
    status: str  # queued/started, running, completed, failed, cancelled
    model: str
    progress: Optional[Dict[str, Any]] = None
    results: Optional[List[Dict[str, Any]]] = None
    result_refs: Optional[List[str]] = None
    error: Optional[str] = None
    created_at: float
    completed_at: Optional[float] = None


# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------

# Use shared constants from service module
MODE_CAPABILITIES = MODE_CAPABILITIES
SUPPORTED_MODELS = SUPPORTED_MODELS


def _validate_model(model: str) -> None:
    """Validate model identifier."""
    if not validate_model(model):
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model: {model}. Supported: {list(SUPPORTED_MODELS)}",
        )


def _ensure_jobs() -> Any:
    """Register vision executors and return the JobService singleton."""
    from app.modules.vision.runtime.job_executors import (
        ensure_vision_executors_registered,
    )
    from common_lib.modules.jobs.service import get_job_service

    ensure_vision_executors_registered()
    return get_job_service()


# ---------------------------------------------------------------------------
# JobRecord -> legacy task-shape mapping
# ---------------------------------------------------------------------------

_JOB_TO_LEGACY: Dict[str, str] = {
    "queued": "started",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}

_LEGACY_TO_JOB: Dict[str, str] = {
    "started": "queued",
    "queued": "queued",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}

_SOTA_KINDS: tuple[str, ...] = ("vision.sota.single", "vision.sota.batch")


def _to_timestamp(value: Any) -> float:
    if isinstance(value, datetime):
        return value.timestamp()
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _load_result_meta(result_refs: List[str]) -> List[Dict[str, Any]]:
    """Load b64-free ``result.json`` metadata for completed jobs."""
    results: List[Dict[str, Any]] = []
    for ref in result_refs:
        if not ref.endswith("result.json"):
            continue
        try:
            with open(ref, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if isinstance(payload, dict):
                results.append(payload)
        except (OSError, ValueError):
            continue
    return results


def _job_to_task(record: Any) -> Dict[str, Any]:
    """Map a JobRecord snapshot onto the legacy SOTA task shape."""
    params: Dict[str, Any] = {}
    try:
        params = record.get_params() or {}
    except Exception:
        params = {}
    if not isinstance(params, dict):
        params = {}
    status: str = _JOB_TO_LEGACY.get(str(record.status), str(record.status))
    refs: List[str] = []
    try:
        refs = record.get_result_refs() or []
    except Exception:
        refs = []
    progress: Dict[str, Any] = {
        "current": float(record.progress or 0.0),
        "total": 100,
        "percent": float(record.progress or 0.0),
    }
    created_at: float = _to_timestamp(record.created_at)
    completed_at: Optional[float] = None
    if status in ("completed", "failed", "cancelled"):
        completed_at = _to_timestamp(record.updated_at)
    results: Optional[List[Dict[str, Any]]] = None
    if status == "completed":
        results = _load_result_meta([str(r) for r in refs])
    return {
        "task_id": str(record.id),
        "job_id": str(record.id),
        "status": status,
        "model": str(params.get("model", "")),
        "progress": progress,
        "results": results,
        "result_refs": [str(r) for r in refs],
        "error": record.error,
        "created_at": created_at,
        "completed_at": completed_at,
    }


def _lookup_task(task_id: str) -> Optional[Dict[str, Any]]:
    """Find a task in the jobs module, falling back to the legacy store."""
    svc = _ensure_jobs()
    record = svc.get(task_id)
    if record is not None:
        return _job_to_task(record)
    try:
        from common_lib.modules.vision.sota_generation_service import (
            get_task_status as _legacy_get,
        )

        legacy = _legacy_get(task_id)
        if legacy is not None:
            task = dict(legacy)
            task.setdefault("job_id", task.get("task_id"))
            task.setdefault("result_refs", [])
            return task
    except Exception:  # noqa: BLE001
        logger.debug("sota: legacy task lookup failed for %s", task_id, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# Sample JSON for batch generation
# ---------------------------------------------------------------------------


@router.get("/sample-batch-json")
async def get_sample_batch_json() -> Dict[str, Any]:
    """Get sample JSON format for batch generation."""
    return SAMPLE_BATCH_JSON


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """List all supported SOTA models with their capabilities."""
    return {
        "models": [
            {"id": model_id, **caps} for model_id, caps in MODE_CAPABILITIES.items()
        ]
    }


# ---------------------------------------------------------------------------
# Router Endpoints (job-backed)
# ---------------------------------------------------------------------------


@router.post("/generate/single", response_model=SOTASingleResponse)
async def generate_single(
    request: SOTASingleRequest,
):
    """Generate a single image using a SOTA model (jobs-backed).

    Supported models:
    - krea-2-turbo: Krea 2 Turbo (txt2img, img2img)
    - qwen21: Qwen-Image-2.1 (txt2img, img2img, inpaint, outpaint)
    - ming: Ming-Image-0.1-Design (txt2img only)
    """
    from app.modules.vision.runtime.job_executors import SOTA_SINGLE_KIND

    _validate_model(request.model)

    svc = _ensure_jobs()
    record = svc.submit(
        SOTA_SINGLE_KIND,
        params={
            "model": request.model,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "cfg": request.cfg,
            "seed": request.seed,
            "device": request.device,
        },
    )

    return SOTASingleResponse(
        task_id=record.id,
        job_id=record.id,
        status="queued",
        message=f"Generation queued for {request.model}",
        model=request.model,
    )


@router.post("/generate/batch", response_model=SOTABatchResponse)
async def generate_batch(
    request: SOTABatchRequest,
):
    """Generate a batch of images from JSON using a SOTA model (jobs-backed).

    The JSON format matches the sample returned by GET /sota/sample-batch-json.

    Supported models:
    - krea-2-turbo: Krea 2 Turbo (txt2img, img2img)
    - qwen21: Qwen-Image-2.1 (txt2img, img2img, inpaint, outpaint)
    - ming: Ming-Image-0.1-Design (txt2img only)
    """
    from app.modules.vision.runtime.job_executors import SOTA_BATCH_KIND

    _validate_model(request.model)

    if not request.items:
        raise HTTPException(status_code=400, detail="items list cannot be empty")

    svc = _ensure_jobs()
    record = svc.submit(
        SOTA_BATCH_KIND,
        params={
            "model": request.model,
            "items": request.items,
            "device": request.device,
        },
    )

    return SOTABatchResponse(
        task_id=record.id,
        job_id=record.id,
        status="queued",
        message=f"Batch generation queued for {request.model}",
        model=request.model,
        total_items=len(request.items),
    )


@router.post("/generate/batch/upload", response_model=SOTABatchResponse)
async def generate_batch_upload(
    model: str = Form(...),
    file: UploadFile = File(...),
    device: str = Form("cuda"),
    output_dir: Optional[str] = Form(None),
):
    """Upload a JSON file for batch generation (jobs-backed).

    The JSON file should contain an array of generation items.
    """
    from app.modules.vision.runtime.job_executors import SOTA_BATCH_KIND

    _validate_model(model)

    try:
        content = await file.read()
        items = json.loads(content.decode("utf-8"))

        if not isinstance(items, list):
            raise HTTPException(
                status_code=400, detail="JSON must be an array of generation items"
            )

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    svc = _ensure_jobs()
    record = svc.submit(
        SOTA_BATCH_KIND,
        params={"model": model, "items": items, "device": device},
    )

    return SOTABatchResponse(
        task_id=record.id,
        job_id=record.id,
        status="queued",
        message=f"Batch generation queued for {model}",
        model=model,
        total_items=len(items),
    )


@router.get("/tasks/{task_id}", response_model=SOTATaskStatus)
async def get_task_status_endpoint(task_id: str):
    """Get the status of a generation task (jobs-backed)."""
    task = _lookup_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return SOTATaskStatus(**task)


@router.get("/tasks", response_model=List[SOTATaskStatus])
async def list_tasks_endpoint(
    status: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 50,
):
    """List all generation tasks with optional filters (jobs-backed)."""
    svc = _ensure_jobs()
    job_status: Optional[str] = None
    if status:
        job_status = _LEGACY_TO_JOB.get(status, status)
    tasks: List[Dict[str, Any]] = []
    for kind in _SOTA_KINDS:
        for record in svc.list(status=job_status, kind=kind, limit=limit):
            task = _job_to_task(record)
            if model and task.get("model") != model:
                continue
            tasks.append(task)
    tasks.sort(key=lambda t: t.get("created_at", 0.0), reverse=True)
    try:
        from common_lib.modules.vision.sota_generation_service import (
            list_tasks as _legacy_list,
        )

        for legacy in _legacy_list(status=status, model=model, limit=limit):
            if any(t["task_id"] == legacy.get("task_id") for t in tasks):
                continue
            entry = dict(legacy)
            entry.setdefault("job_id", entry.get("task_id"))
            entry.setdefault("result_refs", [])
            tasks.append(entry)
    except Exception:  # noqa: BLE001
        logger.debug("sota: legacy task list failed", exc_info=True)
    return [SOTATaskStatus(**t) for t in tasks[:limit]]


@router.delete("/tasks/{task_id}")
async def cancel_task_endpoint(task_id: str):
    """Cancel a queued/running task (jobs-backed, cooperative)."""
    svc = _ensure_jobs()
    record = svc.get(task_id)
    if record is not None:
        if str(record.status) in ("completed", "failed"):
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel task in {record.status} state"
            )
        svc.cancel(task_id)
        return {"status": "cancelled", "task_id": task_id, "job_id": task_id}
    try:
        from common_lib.modules.vision.sota_generation_service import (
            cancel_task as _legacy_cancel,
            get_task_status as _legacy_get,
        )

        if _legacy_cancel(task_id):
            return {"status": "cancelled", "task_id": task_id, "job_id": task_id}
        task = _legacy_get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        if task.get("status") in ("completed", "failed"):
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel task in {task['status']} state"
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=404, detail=f"Task {task_id} not found"
        ) from exc
    return {"status": "cancelled", "task_id": task_id, "job_id": task_id}


__all__ = ["router"]
