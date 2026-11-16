"""
Comparator routes for universal image generation module.

Thin transport layer — delegates to common_lib image_processing.generation service.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
import asyncio
import json
import os
import time
from pathlib import Path

router = APIRouter(prefix="/compare", tags=["Image Generation Comparator"])


# Request/Response Schemas (mirror common_lib generation schemas)
class EngineParams(BaseModel):
    engine: str
    steps: Optional[int] = None
    cfg: Optional[float] = None
    seed: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    negative_prompt: Optional[str] = None
    checkpoint: Optional[str] = None


class CommonParams(BaseModel):
    steps: int = 20
    cfg: float = 7.0
    seed: int = -1
    width: int = 1024
    height: int = 1024
    negative_prompt: str = ""


class CompareRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    engines: List[str] = Field(..., min_length=1)
    common_params: Optional[CommonParams] = None
    per_engine_params: Optional[List[EngineParams]] = None
    output_dir: Optional[str] = None


class CompareRunCreate(CompareRequest):
    pass


class CompareRunResponse(BaseModel):
    run_id: UUID
    prompt: str
    engines: List[str]
    status: str  # "pending" | "running" | "completed" | "failed"
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: List[Dict[str, Any]] = []


class CompareHistoryResponse(BaseModel):
    runs: List[CompareRunResponse]
    total: int


# In-memory store (replace with DB persistence in production)
_COMPARE_RUNS: Dict[UUID, CompareRunResponse] = {}

# Output base directory
DEFAULT_OUTPUT_BASE = Path(
    os.getenv(
        "IMAGE_GENERATION_OUTPUT_DIR",
        "/home/siddharth/Documents/Dev/agentic-platform/resources/generated_content/unified_generation_module_tests/compare_runs",
    )
)
DEFAULT_OUTPUT_BASE.mkdir(parents=True, exist_ok=True)


async def _run_single_generation(
    engine: str,
    prompt: str,
    params: EngineParams,
    common: CommonParams,
    output_dir: Path,
) -> Dict[str, Any]:
    """Run a single engine generation via the generation engine directly."""
    import time
    from common_lib.modules.image_processing.generation.engine import (
        generate as generate_engine,
    )
    from common_lib.modules.image_processing.generation.request import GenerationRequest

    # Merge params: common first, then per-engine overrides
    final_steps = params.steps if params.steps is not None else common.steps
    final_cfg = params.cfg if params.cfg is not None else common.cfg
    final_seed = params.seed if params.seed is not None else common.seed
    final_width = params.width if params.width is not None else common.width
    final_height = params.height if params.height is not None else common.height
    final_neg = (
        params.negative_prompt
        if params.negative_prompt is not None
        else common.negative_prompt
    )
    final_checkpoint = params.checkpoint

    # Build request for the generation engine
    req = GenerationRequest(
        engine=engine,
        prompt=prompt,
        mode="t2i",
        negative_prompt=final_neg if final_neg else None,
        width=final_width,
        height=final_height,
        steps=final_steps,
        cfg=final_cfg,
        seed=final_seed,
        strength=0.65,
        outpaint_margin=64,
        save_to=str(output_dir),
        recipe=f"compare_{engine}_{uuid4().hex[:8]}",
        model=params.checkpoint,
        extra={"checkpoint": params.checkpoint} if params.checkpoint else None,
    )

    started = time.time()
    try:
        result = await generate_engine(req)
        duration = time.time() - started

        if result.get("ok") and result.get("output"):
            return {
                "engine": engine,
                "params": {
                    "steps": final_steps,
                    "cfg": final_cfg,
                    "seed": final_seed,
                    "width": final_width,
                    "height": final_height,
                    "negative_prompt": final_neg,
                    "checkpoint": final_checkpoint,
                },
                "status": "completed",
                "output_path": result["output"],
                "duration_s": round(duration, 2),
            }
        else:
            return {
                "engine": engine,
                "params": {
                    "steps": final_steps,
                    "cfg": final_cfg,
                    "seed": final_seed,
                    "width": final_width,
                    "height": final_height,
                    "negative_prompt": final_neg,
                    "checkpoint": final_checkpoint,
                },
                "status": "failed",
                "error": result.get("error", "Unknown error"),
                "duration_s": round(time.time() - started, 2),
            }
    except Exception as e:
        return {
            "engine": engine,
            "params": {
                "steps": final_steps,
                "cfg": final_cfg,
                "seed": final_seed,
                "width": final_width,
                "height": final_height,
                "negative_prompt": final_neg,
                "checkpoint": final_checkpoint,
            },
            "status": "failed",
            "error": str(e),
            "duration_s": round(time.time() - started, 2),
        }


@router.post("", response_model=CompareRunResponse)
async def create_comparison(request: CompareRunCreate):
    """Start a multi-engine comparison run."""
    run_id = uuid4()
    timestamp = datetime.utcnow()

    # Create output directory for this run
    run_dir = DEFAULT_OUTPUT_BASE / run_id.hex
    run_dir.mkdir(parents=True, exist_ok=True)

    # Prepare common params
    common = request.common_params or CommonParams()

    # Prepare per-engine params
    per_engine_map = {}
    if request.per_engine_params:
        for ep in request.per_engine_params:
            per_engine_map[ep.engine] = ep

    # Create initial run record
    run = CompareRunResponse(
        run_id=run_id,
        prompt=request.prompt,
        engines=request.engines,
        status="running",
        created_at=timestamp,
    )
    _COMPARE_RUNS[run_id] = run

    # Run generations sequentially (for GPU memory)
    results = []
    for engine in request.engines:
        engine_params = per_engine_map.get(engine, EngineParams(engine=engine))
        result = await _run_single_generation(
            engine, request.prompt, engine_params, common, run_dir
        )
        results.append(result)

    # Update run with results
    run.status = (
        "completed" if all(r["status"] == "completed" for r in results) else "partial"
    )
    run.completed_at = datetime.utcnow()
    run.results = results
    _COMPARE_RUNS[run_id] = run

    return run


@router.get("/history", response_model=CompareHistoryResponse)
async def list_comparison_history(limit: int = 50, offset: int = 0):
    """List past comparison runs."""
    runs = list(_COMPARE_RUNS.values())
    runs.sort(key=lambda r: r.created_at, reverse=True)
    total = len(runs)
    return CompareHistoryResponse(runs=runs[offset : offset + limit], total=total)


@router.get("/history/{run_id}", response_model=CompareRunResponse)
async def get_comparison_run(run_id: UUID):
    """Get a specific comparison run with results."""
    if run_id not in _COMPARE_RUNS:
        raise HTTPException(status_code=404, detail="Comparison run not found")
    return _COMPARE_RUNS[run_id]


@router.delete("/history/{run_id}")
async def delete_comparison_run(run_id: UUID):
    """Delete a comparison run."""
    if run_id not in _COMPARE_RUNS:
        raise HTTPException(status_code=404, detail="Comparison run not found")
    del _COMPARE_RUNS[run_id]
    return {"status": "deleted", "run_id": str(run_id)}


@router.get("/engines")
async def list_available_engines():
    """List available generation engines with their default params."""
    # These match the proven engines in configs/backends.yaml
    return {
        "engines": [
            {
                "id": "zimage",
                "name": "ZImage (Z.ai)",
                "native_resolution": [1024, 1024],
                "default_params": {"steps": 9, "cfg": 0.0, "seed": 42},
                "proven": True,
                "notes": "Fast, good detail, cfg=0 native",
            },
            {
                "id": "sd15_dreamshaper",
                "name": "SD 1.5 DreamShaper",
                "native_resolution": [768, 768],
                "default_params": {"steps": 30, "cfg": 7.0, "seed": 42},
                "proven": True,
                "notes": "768px native, strong photorealism",
            },
            {
                "id": "sdxl_realvis",
                "name": "SDXL RealVisXL v5.0",
                "native_resolution": [1024, 1024],
                "default_params": {"steps": 30, "cfg": 5.0, "seed": 42},
                "proven": True,
                "notes": "Best photorealistic detail at 1024",
            },
            {
                "id": "qwen21_uc",
                "name": "Qwen-Image 2.1 UC",
                "native_resolution": [1024, 1024],
                "default_params": {"steps": 30, "cfg": 3.0, "seed": 42},
                "proven": True,
                "notes": "Best architectural/texture detail, true CFG support",
            },
            {
                "id": "krea2",
                "name": "Krea 2 (Flux)",
                "native_resolution": [1024, 1024],
                "default_params": {"steps": 8, "cfg": 1.0, "seed": 42},
                "proven": True,
                "notes": "ComfyUI path, unet weight warning",
            },
            {
                "id": "moss",
                "name": "Moss (Vulkan)",
                "native_resolution": [1024, 1024],
                "default_params": {"steps": 20, "cfg": 7.0, "seed": 42},
                "proven": True,
                "notes": "Vulkan backend, slower (~130s)",
            },
            {
                "id": "flux",
                "name": "FLUX.2 (blocked)",
                "native_resolution": [1024, 1024],
                "default_params": {"steps": 20, "cfg": 3.5, "seed": 42},
                "proven": False,
                "notes": "Missing FLUX.2 VAE + Qwen3-4B text encoder",
            },
        ]
    }
