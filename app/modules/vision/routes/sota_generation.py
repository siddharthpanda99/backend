"""SOTA Image Generation REST endpoints — thin routers over common_lib services.

Models: Krea 2, Qwen-Image-2.1, Ming-Image-0.1-Design
All endpoints run as background tasks to avoid blocking other API endpoints.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from common_lib.modules.vision.sota_generation_service import (
    MODE_CAPABILITIES,
    SAMPLE_BATCH_JSON,
    SUPPORTED_MODELS,
    cancel_task,
    get_task_status,
    list_tasks,
    run_batch_generation_task,
    run_single_generation_task,
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
    status: str = "started"
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
    status: str = "started"
    message: str
    model: str
    total_items: int


class SOTATaskStatus(BaseModel):
    """Task status response."""

    task_id: str
    status: str  # started, running, completed, failed
    model: str
    progress: Optional[Dict[str, Any]] = None
    results: Optional[List[Dict[str, Any]]] = None
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


def _create_task_id() -> str:
    """Create a short task ID."""
    return str(uuid.uuid4())[:8]


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
# Router Endpoints
# ---------------------------------------------------------------------------


@router.post("/generate/single", response_model=SOTASingleResponse)
async def generate_single(
    background_tasks: BackgroundTasks,
    request: SOTASingleRequest,
):
    """Generate a single image using a SOTA model (background task).

    Supported models:
    - krea-2-turbo: Krea 2 Turbo (txt2img, img2img)
    - qwen21: Qwen-Image-2.1 (txt2img, img2img, inpaint, outpaint)
    - ming: Ming-Image-0.1-Design (txt2img only)
    """
    _validate_model(request.model)

    task_id = _create_task_id()
    background_tasks.add_task(
        run_single_generation_task,
        task_id=task_id,
        model=request.model,
        prompt=request.prompt,
        negative_prompt=request.negative_prompt,
        width=request.width,
        height=request.height,
        steps=request.steps,
        cfg=request.cfg,
        seed=request.seed,
        device=request.device,
    )

    return SOTASingleResponse(
        task_id=task_id,
        status="started",
        message=f"Generation started for {request.model}",
        model=request.model,
    )


@router.post("/generate/batch", response_model=SOTABatchResponse)
async def generate_batch(
    background_tasks: BackgroundTasks,
    request: SOTABatchRequest,
):
    """Generate a batch of images from JSON using a SOTA model (background task).

    The JSON format matches the sample returned by GET /sota/sample-batch-json.

    Supported models:
    - krea-2-turbo: Krea 2 Turbo (txt2img, img2img)
    - qwen21: Qwen-Image-2.1 (txt2img, img2img, inpaint, outpaint)
    - ming: Ming-Image-0.1-Design (txt2img only)
    """
    _validate_model(request.model)

    if not request.items:
        raise HTTPException(status_code=400, detail="items list cannot be empty")

    task_id = _create_task_id()
    background_tasks.add_task(
        run_batch_generation_task,
        task_id=task_id,
        model=request.model,
        items=request.items,
        device=request.device,
        output_dir=request.output_dir,
    )

    return SOTABatchResponse(
        task_id=task_id,
        status="started",
        message=f"Batch generation started for {request.model}",
        model=request.model,
        total_items=len(request.items),
    )


@router.post("/generate/batch/upload", response_model=SOTABatchResponse)
async def generate_batch_upload(
    background_tasks: BackgroundTasks,
    model: str = Form(...),
    file: UploadFile = File(...),
    device: str = Form("cuda"),
    output_dir: Optional[str] = Form(None),
):
    """Upload a JSON file for batch generation (background task).

    The JSON file should contain an array of generation items.
    """
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

    task_id = _create_task_id()
    background_tasks.add_task(
        run_batch_generation_task,
        task_id=task_id,
        model=model,
        items=items,
        device=device,
        output_dir=output_dir,
    )

    return SOTABatchResponse(
        task_id=task_id,
        status="started",
        message=f"Batch generation started for {model}",
        model=model,
        total_items=len(items),
    )


@router.get("/tasks/{task_id}", response_model=SOTATaskStatus)
async def get_task_status_endpoint(task_id: str):
    """Get the status of a generation task."""
    task = get_task_status(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return SOTATaskStatus(**task)


@router.get("/tasks", response_model=List[SOTATaskStatus])
async def list_tasks_endpoint(
    status: Optional[str] = None,
    model: Optional[str] = None,
    limit: int = 50,
):
    """List all generation tasks with optional filters."""
    tasks = list_tasks(status=status, model=model, limit=limit)
    return [SOTATaskStatus(**t) for t in tasks]


@router.delete("/tasks/{task_id}")
async def cancel_task_endpoint(task_id: str):
    """Cancel a running task (marks as cancelled, actual cancellation depends on implementation)."""
    if not cancel_task(task_id):
        task = get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        if task["status"] in ("completed", "failed"):
            raise HTTPException(
                status_code=400, detail=f"Cannot cancel task in {task['status']} state"
            )

    return {"status": "cancelled", "task_id": task_id}


__all__ = ["router"]
