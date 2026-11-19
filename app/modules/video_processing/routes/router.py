"""VideoProcessing Routes — Thin API layer for Video Generation (Wan, LTX)."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from common_lib.modules.image_processing.video_processing.schemas import (
    VideoGenerateRequest,
    VideoGenerateResponse,
    VideoModelInfo,
    VideoDownloadRequest,
    VideoDownloadResponse,
    VideoListModelsResponse,
    VideoListRecordsResponse,
    VideoGenerationRecordResponse,
)
from common_lib.modules.image_processing.video_processing.service import (
    get_video_processing_service,
)
from common_lib.modules.image_processing.video_processing.exceptions import (
    VideoGenerationError,
    VideoModelDownloadError,
    VideoModelNotAvailableError,
    InvalidInputError,
    VideoGPUOutOfMemoryError,
)
from common_lib.modules.image_processing.video_processing.feature_flags import (
    VIDEO_PROCESSING_ENABLED,
    VIDEO_GENERATION,
    VIDEO_MODEL_DOWNLOAD,
    VIDEO_ASYNC_GENERATION,
    VIDEO_WAN_ENABLED,
    VIDEO_LTX_ENABLED,
)

from app.modules.jobs.actor import capture_job_actor, owned_job_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(capture_job_actor)])


# ── Feature Flag Checks ────────────────────────────────────────────────


def _check_video_enabled() -> VideoGenerateResponse | None:
    if not VIDEO_PROCESSING_ENABLED.is_enabled():
        return VideoGenerateResponse(
            status="error",
            error="Feature disabled",
            message="Video processing module is not enabled. Set VIDEO_PROCESSING_ENABLED=true.",
        )
    return None


def _check_generation_enabled() -> VideoGenerateResponse | None:
    if not VIDEO_GENERATION.is_enabled():
        return VideoGenerateResponse(
            status="error",
            error="Feature disabled",
            message="Video generation is not enabled. Set VIDEO_GENERATION=true.",
        )
    return None


def _check_download_enabled() -> VideoDownloadResponse | None:
    if not VIDEO_MODEL_DOWNLOAD.is_enabled():
        return VideoDownloadResponse(
            status="error",
            model_id="",
            error="Model download is not enabled. Set VIDEO_MODEL_DOWNLOAD=true.",
        )
    return None


def _check_wan_enabled() -> VideoGenerateResponse | None:
    if not VIDEO_WAN_ENABLED.is_enabled():
        return VideoGenerateResponse(
            status="error",
            error="Feature disabled",
            message="Wan models are not enabled. Set VIDEO_WAN_ENABLED=true.",
        )
    return None


def _check_ltx_enabled() -> VideoGenerateResponse | None:
    if not VIDEO_LTX_ENABLED.is_enabled():
        return VideoGenerateResponse(
            status="error",
            error="Feature disabled",
            message="LTX Video is not enabled. Set VIDEO_LTX_ENABLED=true.",
        )
    return None


def _handle_generation_error(e: Exception) -> VideoGenerateResponse:
    if isinstance(e, VideoGPUOutOfMemoryError):
        return VideoGenerateResponse(
            status="error",
            error="GPU out of memory",
            message="Try reducing resolution, frames, or enabling CPU offload",
        )
    elif isinstance(e, InvalidInputError):
        return VideoGenerateResponse(
            status="error",
            error="Invalid input",
            message=e.message,
        )
    elif isinstance(e, VideoGenerationError):
        return VideoGenerateResponse(
            status="error",
            error="Generation failed",
            message=e.message,
        )
    else:
        logger.exception(f"Unexpected video generation error: {e}")
        return VideoGenerateResponse(
            status="error",
            error="Internal error",
            message=str(e),
        )


# ── Generation Endpoints ──────────────────────────────────────────────


@router.post("/generate", response_model=VideoGenerateResponse)
async def generate_video(request: VideoGenerateRequest):
    """
    Generate a video from text prompt (t2v) or image prompt (i2v).

    Supports Wan 2.1 (t2v, i2v) and LTX Video models.
    Returns an MP4 video file with configurable resolution, fps, and duration.
    """
    # Check feature flags
    flag_error = _check_video_enabled() or _check_generation_enabled()
    if flag_error:
        return flag_error

    # Model-specific flags
    if request.model.startswith("wan"):
        flag_error = _check_wan_enabled()
        if flag_error:
            return flag_error
    elif request.model == "ltx-video":
        flag_error = _check_ltx_enabled()
        if flag_error:
            return flag_error

    service = get_video_processing_service()
    try:
        result = await service.generate_video(request)
        return result
    except (VideoGPUOutOfMemoryError, InvalidInputError, VideoGenerationError) as e:
        return _handle_generation_error(e)
    except Exception as e:
        return _handle_generation_error(e)


@router.post("/generate/async")
async def generate_video_async(request: VideoGenerateRequest):
    """Queue a video generation job asynchronously."""
    flag_error = _check_video_enabled() or _check_generation_enabled()
    if flag_error:
        return flag_error

    if not VIDEO_ASYNC_GENERATION.is_enabled():
        return VideoGenerateResponse(
            status="error",
            error="Feature disabled",
            message="Async video generation is not enabled. Set VIDEO_ASYNC_GENERATION=true.",
        )

    import uuid

    job_id = str(uuid.uuid4())
    return {
        "status": "queued",
        "job_id": job_id,
        "message": "Job queued. Use /jobs/{job_id} to poll status.",
    }


@router.post("/generate/upload", response_model=VideoGenerateResponse)
async def generate_video_upload(
    file: UploadFile = File(None),
    prompt: str = Form(...),
    model: str = Form("wan2.1-t2v"),
    seed: int = Form(42),
    steps: int = Form(50),
    cfg_scale: float = Form(7.0),
    fps: int = Form(16),
    width: int = Form(512),
    height: int = Form(512),
    num_frames: int = Form(81),
    save_video: bool = Form(True),
    save_preview: bool = Form(True),
):
    """Generate video from uploaded image file (for i2v)."""
    flag_error = _check_video_enabled() or _check_generation_enabled()
    if flag_error:
        return flag_error

    if model.startswith("wan"):
        flag_error = _check_wan_enabled()
        if flag_error:
            return flag_error
    elif model == "ltx-video":
        flag_error = _check_ltx_enabled()
        if flag_error:
            return flag_error

    image_input = None
    if file:
        content = await file.read()
        import base64
        import io
        from PIL import Image

        try:
            image = Image.open(io.BytesIO(content)).convert("RGB")
            buffered = io.BytesIO()
            image.save(buffered, format="PNG")
            image_input = (
                "data:image/png;base64,"
                + base64.b64encode(buffered.getvalue()).decode()
            )
        except Exception as e:
            logger.exception(f"Image processing failed: {e}")
            return VideoGenerateResponse(
                status="error", error="Image processing failed", message=str(e)
            )

    request = VideoGenerateRequest(
        prompt=prompt,
        model=model,
        image=image_input,
        seed=seed,
        steps=steps,
        cfg_scale=cfg_scale,
        fps=fps,
        width=width,
        height=height,
        num_frames=num_frames,
        save_video=save_video,
        save_preview=save_preview,
    )

    service = get_video_processing_service()
    try:
        result = await service.generate_video(request)
        return result
    except (VideoGPUOutOfMemoryError, InvalidInputError, VideoGenerationError) as e:
        return _handle_generation_error(e)
    except Exception as e:
        return _handle_generation_error(e)


# ── Model Management Endpoints ────────────────────────────────────────


@router.get("/models", response_model=VideoListModelsResponse)
async def list_models():
    """List available video models (Wan 2.1, LTX Video)."""
    service = get_video_processing_service()
    try:
        models = service.list_models()
        return VideoListModelsResponse(models=models)
    except Exception as e:
        logger.exception(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}", response_model=VideoModelInfo)
async def get_model(model_id: str):
    """Get information about a specific video model."""
    service = get_video_processing_service()
    try:
        info = service.get_model_info(model_id)
        return info
    except Exception as e:
        logger.exception(f"Error getting model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/download", response_model=VideoDownloadResponse)
async def download_model(model_id: str, request: VideoDownloadRequest):
    """Download a video model (Wan 2.1, LTX Video)."""
    flag_error = _check_video_enabled() or _check_download_enabled()
    if flag_error:
        return flag_error

    if model_id.startswith("wan") and not VIDEO_WAN_ENABLED.is_enabled():
        return VideoDownloadResponse(
            status="error",
            model_id=model_id,
            error="Wan models are not enabled. Set VIDEO_WAN_ENABLED=true.",
        )
    if model_id == "ltx-video" and not VIDEO_LTX_ENABLED.is_enabled():
        return VideoDownloadResponse(
            status="error",
            model_id=model_id,
            error="LTX Video is not enabled. Set VIDEO_LTX_ENABLED=true.",
        )

    service = get_video_processing_service()
    try:
        result = await service.download_model(model_id, request.force)
        return VideoDownloadResponse(
            status=result.status,
            model_id=result.model_name,
            local_path=result.local_path,
            progress=result.progress,
            error=result.error_message,
        )
    except VideoModelDownloadError as e:
        return VideoDownloadResponse(status="error", model_id=model_id, error=e.message)
    except VideoModelNotAvailableError as e:
        return VideoDownloadResponse(status="error", model_id=model_id, error=e.message)
    except Exception as e:
        logger.exception(f"Error downloading model: {e}")
        return VideoDownloadResponse(status="error", model_id=model_id, error=str(e))


# ── Generation Records Endpoints ──────────────────────────────────────


@router.get("/records", response_model=VideoListRecordsResponse)
async def list_records(limit: int = 50, offset: int = 0):
    """List video generation records with pagination."""
    service = get_video_processing_service()
    try:
        records = service.list_records(limit=limit, offset=offset)
        total = service.count_records()
        return VideoListRecordsResponse(
            records=[
                VideoGenerationRecordResponse(
                    record_id=r.record_id,
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    input_prompt=r.input_prompt,
                    model_name=r.model_name,
                    generation_mode=r.generation_mode,
                    seed=r.seed,
                    steps=r.steps,
                    cfg_scale=r.cfg_scale,
                    fps=r.fps,
                    width=r.width,
                    height=r.height,
                    num_frames=r.num_frames,
                    output_video_path=r.output_video_path,
                    output_preview_path=r.output_preview_path,
                    status=r.status,
                    processing_time_seconds=r.processing_time_seconds,
                    error_message=r.error_message,
                )
                for r in records
            ],
            total=total,
        )
    except Exception as e:
        logger.exception(f"Error listing records: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/records/{record_id}", response_model=VideoGenerationRecordResponse)
async def get_record(record_id: UUID):
    """Get a specific generation record by ID."""
    service = get_video_processing_service()
    try:
        record = service.get_record(record_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=f"Record '{record_id}' not found"
            )
        return VideoGenerationRecordResponse(
            record_id=record.record_id,
            created_at=record.created_at.isoformat() if record.created_at else "",
            input_prompt=record.input_prompt,
            model_name=record.model_name,
            generation_mode=record.generation_mode,
            seed=record.seed,
            steps=record.steps,
            cfg_scale=record.cfg_scale,
            fps=record.fps,
            width=record.width,
            height=record.height,
            num_frames=record.num_frames,
            output_video_path=record.output_video_path,
            output_preview_path=record.output_preview_path,
            status=record.status,
            processing_time_seconds=record.processing_time_seconds,
            error_message=record.error_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting record: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Health & Status ───────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    service = get_video_processing_service()
    models = service.list_models()
    return {
        "status": "healthy",
        "module": "video_processing",
        "models_available": sum(1 for m in models if m.is_local),
        "total_models": len(models),
        "gpu_available": torch.cuda.is_available() if "torch" in globals() else False,
    }


@router.get("/status")
async def status():
    """Detailed status including models and GPU info."""
    import torch

    service = get_video_processing_service()
    models = service.list_models()

    gpu_info = {}
    if torch.cuda.is_available():
        gpu_info = {
            "available": True,
            "device_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "device_name": torch.cuda.get_device_name(),
            "memory_allocated_gb": torch.cuda.memory_allocated() / (1024**3),
            "memory_reserved_gb": torch.cuda.memory_reserved() / (1024**3),
            "max_memory_gb": torch.cuda.get_device_properties(0).total_memory
            / (1024**3),
        }
    else:
        gpu_info = {"available": False}

    return {
        "module": "video_processing",
        "models": [m.model_dump() for m in models],
        "gpu": gpu_info,
        "output_dir": service.output_dir,
        "feature_flags": {
            "enabled": VIDEO_PROCESSING_ENABLED.is_enabled(),
            "generation": VIDEO_GENERATION.is_enabled(),
            "model_download": VIDEO_MODEL_DOWNLOAD.is_enabled(),
            "wan": VIDEO_WAN_ENABLED.is_enabled(),
            "ltx": VIDEO_LTX_ENABLED.is_enabled(),
        },
    }


__all__ = ["router"]
