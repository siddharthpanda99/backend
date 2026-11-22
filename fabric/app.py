"""Nexus Runtime Execution Fabric - FastAPI app factory.

Thin control plane: routes, health, registry, job dispatch. NO torch here.
Workers run in isolated venvs and communicate over loopback HTTP.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from fabric import admin as admin_module
from common_lib.modules.image_processing.native_stacks import get_all_native_stacks
from fabric.jobs import JobQueueFull, JobStatus, job_store
from fabric.models_registry import ModelRegistry
from fabric.profiles import ProfileRegistry
from fabric.schemas import (
    GenerationRequest,
    GenerationResponse,
    HealthResponse,
    ModelInfoResponse,
    Modality,
    TaskType,
)
from fabric.supervisor import supervisor
from fabric.worker_client import (
    WorkerUnavailableError,
    execute_on_worker,
)

logger = logging.getLogger(__name__)

_MODEL_BY_TASK_ORDER = [
    ("music_gen", "ace-step"),
    ("tts", "cosyvoice"),
    ("stt", "whisper"),
    ("voice_conversion", "seed-vc"),
]


def _resolve_model_id(request: GenerationRequest) -> Optional[str]:
    if request.model_id:
        return request.model_id
    # Deterministic pick: first registered model for the task type
    for task_value, model_id in _MODEL_BY_TASK_ORDER:
        if task_value == request.task_type.value and ModelRegistry.get(model_id):
            return model_id
    candidates = ModelRegistry.get_by_task(request.task_type)
    return candidates[0].model_id if candidates else None


def _worker_payload(
    job_id: Optional[str], request: GenerationRequest, model_id: str
) -> Dict[str, Any]:
    return {
        "protocol_version": "1.0",
        "request_id": uuid.uuid4().hex,
        "job_id": job_id,
        "model_id": model_id,
        "task": request.task_type.value,
        "input": {
            "prompt": request.prompt,
            "text": request.prompt,
            "audio_path": request.audio_path,
            "image_path": request.image_path,
            "voice": request.voice,
            "language": request.language,
            "messages": request.messages,
            "system_prompt": request.system_prompt,
            **request.extra.get("input", {}),
        },
        "parameters": {
            "duration": request.duration,
            "sample_rate": request.sample_rate,
            "speed": request.speed,
            "seed": request.seed,
            "temperature": request.temperature,
            "top_p": request.top_p,
            "max_tokens": request.max_tokens,
            "width": request.width,
            "height": request.height,
            "num_inference_steps": request.num_inference_steps,
            "guidance_scale": request.guidance_scale,
            "cpu_offload": request.cpu_offload,
            "sampler": request.sampler,
            "scheduler": request.scheduler,
            **request.extra.get("parameters", {}),
        },
    }


def _response_from_worker(
    request: GenerationRequest,
    model_id: str,
    body: Dict[str, Any],
    start: float,
) -> GenerationResponse:
    if body.get("status") == "completed":
        result = body.get("result") or {}
        return GenerationResponse(
            status="completed",
            model_id=model_id,
            modality=request.modality,
            task_type=request.task_type,
            audio_path=result.get("audio_path"),
            image_path=result.get("image_path"),
            video_path=result.get("video_path"),
            images=result.get("images"),
            text=result.get("text"),
            metadata={**result.get("metadata", {}), "worker_response": result},
            execution_time_ms=int((time.time() - start) * 1000),
        )
    return GenerationResponse(
        status="failed",
        model_id=model_id,
        modality=request.modality,
        task_type=request.task_type,
        error=body.get("error", "worker returned an unsuccessful status"),
        metadata={"worker_response": body},
        execution_time_ms=int((time.time() - start) * 1000),
    )


def _gpu_probe() -> Dict[str, Any]:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=memory.total,memory.used,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                total, used, util = [x.strip() for x in out.stdout.strip().split(",")]
                return {
                    "gpu_available": True,
                    "gpu_memory": f"{int(total) / 1024:.1f}GB",
                    "gpu_utilization": float(util) / 100.0,
                }
        except Exception:
            pass
    return {"gpu_available": False, "gpu_memory": None, "gpu_utilization": None}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Nexus Runtime Execution Fabric - control plane starting")
    models = ModelRegistry.get_all()
    for m in models:
        logger.info(
            "  registered: %s (%s/%s)", m.model_id, m.modality.value, m.task_type.value
        )
    await job_store.start_dispatcher()
    logger.info("Job dispatcher running; workers launch on demand")
    try:
        yield
    finally:
        logger.info("Shutting down; stopping workers and dispatcher...")
        await job_store.stop_dispatcher()
        await supervisor.stop_all_workers()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nexus Runtime Execution Fabric",
        description="Control plane - workers launched on-demand in isolated venvs",
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        models = ModelRegistry.get_all()
        local_models = [m for m in models if m.is_local]
        gpu = _gpu_probe()
        return HealthResponse(
            status="healthy",
            models_loaded=len(models),
            local_models=len(local_models),
            gpu_available=gpu["gpu_available"],
            gpu_memory=gpu["gpu_memory"],
            gpu_utilization=gpu["gpu_utilization"],
        )

    @app.get("/admin/workers")
    async def list_workers():
        """List all workers with their status, GPU usage, and potential stuck detection."""
        workers = supervisor.get_all_worker_info()
        gpu = _gpu_probe()
        now = datetime.utcnow()
        results = []
        for w in workers:
            started = w.get("started_at")
            uptime = None
            if started:
                started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                uptime = (now - started_dt).total_seconds()
            # Detect potentially stuck workers
            is_stuck = False
            stuck_reason = None
            if w["state"] == "busy" and uptime and uptime > 300:  # BUSY > 5 min
                is_stuck = True
                stuck_reason = "BUSY for >5min"
            elif w["state"] == "idle" and uptime and uptime > 600:  # IDLE > 10 min
                is_stuck = True
                stuck_reason = "IDLE for >10min"
            elif (
                w["state"] == "starting" and uptime and uptime > 120
            ):  # STARTING > 2 min
                is_stuck = True
                stuck_reason = "STARTING for >2min"
            elif w["state"] == "failed":
                is_stuck = True
                stuck_reason = "FAILED state"
            results.append(
                {
                    "profile_id": w["profile_id"],
                    "pid": w.get("pid"),
                    "state": w["state"],
                    "uptime_seconds": uptime,
                    "active_jobs": w.get("active_jobs", 0),
                    "total_jobs": w.get("total_jobs", 0),
                    "port": w.get("port"),
                    "is_stuck": is_stuck,
                    "stuck_reason": stuck_reason,
                }
            )
        return {
            "workers": results,
            "gpu_available": gpu.get("gpu_available", False),
            "gpu_memory": gpu.get("gpu_memory"),
            "gpu_utilization": gpu.get("gpu_utilization"),
        }

    @app.post("/admin/workers/cleanup")
    async def cleanup_stuck_workers(
        max_busy_seconds: int = Query(
            default=300, description="Max seconds in BUSY before stuck"
        ),
        max_idle_seconds: int = Query(
            default=600, description="Max seconds in IDLE before cleanup"
        ),
        max_starting_seconds: int = Query(
            default=120, description="Max seconds in STARTING before stuck"
        ),
        force: bool = Query(
            default=False, description="Also kill BUSY workers if true"
        ),
    ):
        """Stop stuck/idle workers. Use force=true to also kill BUSY workers exceeding threshold."""
        now = datetime.utcnow()
        cleaned = []
        errors = []
        for profile_id, worker in list(supervisor._workers.items()):
            started = worker.started_at
            if not started:
                continue
            uptime = (datetime.utcnow() - started).total_seconds()
            should_stop = False
            reason = None

            if worker.state == WorkerState.FAILED:
                should_stop = True
                reason = "FAILED state"
            elif worker.state == WorkerState.STARTING and uptime > 120:
                should_stop = True
                reason = f"STARTING for {uptime:.0f}s"
            elif worker.state == WorkerState.BUSY and uptime > max_busy_seconds:
                if force:
                    should_stop = True
                    reason = f"BUSY for {uptime:.0f}s (force=true)"
                else:
                    logger.warning(
                        f"Worker {profile_id} BUSY for {uptime:.0f}s - use force=true to kill"
                    )
            elif worker.state == WorkerState.IDLE and uptime > max_idle_seconds:
                should_stop = True
                reason = f"IDLE for {uptime:.0f}s"
            elif worker.state == WorkerState.FAILED:
                should_stop = True
                reason = "FAILED state"

            if should_stop:
                try:
                    await supervisor.stop_worker(worker.profile.profile_id)
                    cleaned.append(
                        {"profile_id": worker.profile.profile_id, "reason": reason}
                    )
                    logger.info("Cleaned up stuck worker %s: %s", profile_id, reason)
                except Exception as e:
                    errors.append(
                        {"profile_id": worker.profile.profile_id, "error": str(e)}
                    )
                    logger.error("Failed to stop worker %s: %s", profile_id, e)

        return {"cleaned": cleaned, "errors": errors}

    @app.post("/admin/workers/{profile_id}/kill")
    async def kill_worker(profile_id: str):
        """Force kill a specific worker by profile ID."""
        worker = supervisor._workers.get(profile_id)
        if not worker:
            raise HTTPException(
                status_code=404, detail=f"worker not found: {profile_id}"
            )
        await supervisor.stop_worker(profile_id)
        return {"killed": profile_id}

    @app.get("/models", response_model=List[ModelInfoResponse])
    async def list_models(
        modality: Optional[Modality] = None,
        task_type: Optional[TaskType] = None,
        local_only: bool = False,
    ):
        models = ModelRegistry.get_all()
        if modality:
            models = [m for m in models if m.modality == modality]
        if task_type:
            models = [m for m in models if m.task_type == task_type]
        if local_only:
            models = [m for m in models if m.is_local]
        return [
            ModelInfoResponse(
                model_id=m.model_id,
                name=m.name,
                modality=m.modality,
                task_type=m.task_type,
                model_type=m.model_type,
                size_gb=m.size_gb,
                min_vram_gb=m.min_vram_gb,
                quantization=m.quantization,
                is_local=m.is_local,
                supported_features=m.supported_features,
            )
            for m in models
        ]

    @app.get("/families")
    async def list_families() -> Dict[str, Any]:
        """List image family folders with the models available inside them."""
        from fabric.discovery import list_families as _list

        families = _list()
        return {"count": len(families), "families": families}

    @app.get("/native-stacks")
    async def native_stacks():
        """Report file readiness for all native image stacks (zimage, ernie, qwen21, moss).

        Returns per-stack readiness based on the native loaders' exact path constants
        (checkpoints/<stack>/...), which differ from the registry's file_path layout.
        """
        return get_all_native_stacks()

    @app.get("/families/{family}/models")
    async def list_family_models(family: str) -> Dict[str, Any]:
        """List model files inside one image family folder."""
        from fabric.discovery import (
            list_family_models as _list_family,
        )

        safe = family.strip("/").lower().replace("..", "")
        files = _list_family(safe)
        if files is None:
            raise HTTPException(
                status_code=404,
                detail=f"family not found or not an image checkpoint folder: {family}",
            )
        return {"family": safe, "count": len(files), "models": files}

    @app.get("/images/{filename}")
    async def get_image(filename: str):
        """Stream a generated image from the outputs directory.

        Path traversal is rejected: only files directly inside the outputs
        directory are served, and only image extensions.
        """
        from fastapi.responses import FileResponse
        import re

        allowed_ext = (".png", ".jpg", ".jpeg", ".webp", ".gif")
        name = filename.strip()
        if "/" in name or ".." in name or not re.match(r"^[\w\-. ]+$", name):
            raise HTTPException(status_code=400, detail="invalid filename")
        if not any(name.lower().endswith(e) for e in allowed_ext):
            raise HTTPException(status_code=400, detail="unsupported file type")
        out_dir = Path(os.environ.get("NEXUS_IMAGE_OUTPUT_DIR", "/data/outputs/images"))
        path = (out_dir / name).resolve()
        if not str(path).startswith(str(out_dir.resolve())):
            raise HTTPException(status_code=400, detail="path traversal rejected")
        if not path.is_file():
            raise HTTPException(status_code=404, detail=f"image not found: {name}")
        return FileResponse(path)

    @app.get("/models/{model_id}", response_model=ModelInfoResponse)
    async def get_model(model_id: str):
        m = ModelRegistry.get(model_id)
        if not m:
            raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
        return ModelInfoResponse(
            model_id=m.model_id,
            name=m.name,
            modality=m.modality,
            task_type=m.task_type,
            model_type=m.model_type,
            size_gb=m.size_gb,
            min_vram_gb=m.min_vram_gb,
            quantization=m.quantization,
            is_local=m.is_local,
            supported_features=m.supported_features,
        )

    @app.post("/generate", response_model=GenerationResponse)
    async def generate(request: GenerationRequest):
        start = time.time()
        model_id = _resolve_model_id(request)
        if not model_id:
            raise HTTPException(
                status_code=400,
                detail=f"no model registered for task '{request.task_type.value}'",
            )

        profile = ProfileRegistry.get_profile_for_model(model_id)
        if profile is None or not profile.enabled:
            return GenerationResponse(
                status="not_implemented",
                model_id=model_id,
                modality=request.modality,
                task_type=request.task_type,
                error=f"no runtime profile configured for model '{model_id}'",
                execution_time_ms=int((time.time() - start) * 1000),
            )

        payload = _worker_payload(None, request, model_id)
        try:
            body = await execute_on_worker(profile.profile_id, payload)
        except WorkerUnavailableError as e:
            return GenerationResponse(
                status="failed",
                model_id=model_id,
                modality=request.modality,
                task_type=request.task_type,
                error=str(e),
                execution_time_ms=int((time.time() - start) * 1000),
            )
        return _response_from_worker(request, model_id, body, start)

    @app.post("/audio/generate", response_model=GenerationResponse)
    async def generate_audio(request: GenerationRequest):
        request.modality = Modality.AUDIO
        return await generate(request)

    @app.post("/vision/generate", response_model=GenerationResponse)
    async def generate_vision(request: GenerationRequest):
        request.modality = Modality.VISION
        return await generate(request)

    @app.post("/text/generate", response_model=GenerationResponse)
    async def generate_text(request: GenerationRequest):
        request.modality = Modality.TEXT
        return await generate(request)

    @app.post("/video/generate", response_model=GenerationResponse)
    async def generate_video(request: GenerationRequest):
        request.modality = Modality.VIDEO
        return await generate(request)

    @app.post("/multimodal/generate", response_model=GenerationResponse)
    async def generate_multimodal(request: GenerationRequest):
        request.modality = Modality.MULTIMODAL
        return await generate(request)

    # ---------------- async job system ----------------

    class JobSubmitResponse(BaseModel):
        job_id: str
        status: str
        profile_id: Optional[str] = None

    @app.post("/jobs", response_model=JobSubmitResponse, status_code=202)
    async def submit_job(request: GenerationRequest):
        model_id = _resolve_model_id(request)
        if not model_id:
            raise HTTPException(
                status_code=400,
                detail=f"no model registered for task '{request.task_type.value}'",
            )
        profile = ProfileRegistry.get_profile_for_model(model_id)
        try:
            job = await job_store.create(
                model_id=model_id,
                modality=request.modality.value,
                task_type=request.task_type.value,
                input={
                    "prompt": request.prompt,
                    "text": request.prompt,
                    "audio_path": request.audio_path,
                    "voice": request.voice,
                    "language": request.language,
                    "messages": request.messages,
                    **request.extra.get("input", {}),
                },
                parameters={
                    "duration": request.duration,
                    "speed": request.speed,
                    "seed": request.seed,
                    "sample_rate": request.sample_rate,
                    **request.extra.get("parameters", {}),
                },
                profile_id=profile.profile_id if profile else None,
            )
        except JobQueueFull as e:
            raise HTTPException(status_code=503, detail=str(e))
        return JobSubmitResponse(
            job_id=job.job_id,
            status=job.status.value,
            profile_id=job.profile_id,
        )

    @app.get("/jobs")
    async def list_jobs(
        status: Optional[str] = Query(default=None), limit: int = Query(default=100)
    ):
        jobs = job_store.list(status=status, limit=limit)
        return {"count": len(jobs), "jobs": [j.to_dict() for j in jobs]}

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str):
        job = job_store.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
        return job.to_dict()

    @app.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str):
        ok = await job_store.cancel(job_id)
        if not ok:
            raise HTTPException(
                status_code=409,
                detail=f"job {job_id} not cancellable (missing or already finished)",
            )
        return {"job_id": job_id, "status": JobStatus.CANCELLED.value}

    app.include_router(admin_module.router, prefix="/admin/runtime")

    # ── AI-model-serving routers (ported from Backend/app/modules) ──────────
    # Phase 1 of the two-server port (copy + verify): the AI-specific
    # Backend routes are also served by the fabric control plane. Removal
    # from the Backend is a later step.
    #
    # Mount paths mirror the Backend ROUTER_DEFINITIONS:
    #   models          → /api/v1/models/          (models + external_routes + resolve + frontier)
    #   sd_models       → /api/v1/sd-models/       (router self-prefixes /sd-models)
    #   sam3            → /api/v1/sam3/
    #   agents          → /api/v1/agents/          (registry/runtime/sessions/pipelines/traces)
    from fabric.ai_routes import (
        models_external_router,
        models_router,
        sam3_router,
        sd_models_router,
    )

    app.include_router(models_router, prefix="/api/v1/models")
    app.include_router(models_external_router, prefix="/api/v1/models/external")
    app.include_router(sd_models_router, prefix="/api/v1")
    app.include_router(sam3_router, prefix="/api/v1/sam3")
    try:
        # The agents package pulls the integration stack (observability →
        # secrets → cryptography); the fabric venv intentionally stays
        # lean. When the stack is available (e.g. the Backend venv or a
        # deps-complete venv), the agents routes mount at /api/v1/agents/.
        from fabric.ai_routes.agents.index import (
            router as agents_router,
        )

        app.include_router(agents_router, prefix="/api/v1/agents")
    except Exception as exc:  # noqa: BLE001 - optional on the fabric venv
        logger.warning("agents routes unavailable on the fabric: %s", exc)

    @app.get("/")
    async def root():
        return {
            "name": "Nexus Runtime Execution Fabric",
            "version": "1.0.0",
            "description": "Control plane - workers launched on-demand in isolated venvs",
            "modalities": [m.value for m in Modality],
            "endpoints": {
                "health": "/health",
                "models": "/models",
                "generate": "/generate",
                "jobs": "/jobs",
                "admin_profiles": "/admin/runtime/profiles",
                "admin_workers": "/admin/runtime/workers",
                "admin_gpu": "/admin/runtime/resources/gpu",
            },
            "docs": "/docs",
        }

    return app
