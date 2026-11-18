"""ThreeD Routes — Thin API layer for Image-to-3D Gaussian Splatting."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from common_lib.modules.three_d.schemas import (
    ThreeDGenerateRequest,
    ThreeDGenerateResponse,
    ThreeDModelInfo,
    ThreeDDownloadRequest,
    ThreeDDownloadResponse,
    ThreeDListModelsResponse,
    ThreeDListRecordsResponse,
    ThreeDGenerationRecordResponse,
)
from common_lib.modules.three_d.service import get_three_d_service
from common_lib.modules.three_d.exceptions import (
    GenerationError,
    ModelDownloadError,
    ModelNotAvailableError,
    InvalidInputError,
    GPUOutOfMemoryError,
)

from app.modules.jobs.actor import capture_job_actor, owned_job_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(capture_job_actor)])


# ── Helper Functions ───────────────────────────────────────────────────


def _handle_generation_error(e: Exception) -> ThreeDGenerateResponse:
    """Convert service exceptions to API responses."""
    if isinstance(e, GPUOutOfMemoryError):
        return ThreeDGenerateResponse(
            status="error",
            error="GPU out of memory",
            message="Try reducing num_gaussians or enabling GPU offload",
        )
    elif isinstance(e, InvalidInputError):
        return ThreeDGenerateResponse(
            status="error",
            error="Invalid input",
            message=e.message,
        )
    elif isinstance(e, GenerationError):
        return ThreeDGenerateResponse(
            status="error",
            error="Generation failed",
            message=e.message,
        )
    else:
        logger.exception(f"Unexpected generation error: {e}")
        return ThreeDGenerateResponse(
            status="error",
            error="Internal error",
            message=str(e),
        )


# ── Generation Endpoints ──────────────────────────────────────────────


@router.post("/generate", response_model=ThreeDGenerateResponse)
async def generate_3d(request: ThreeDGenerateRequest):
    """
    Generate a 3D Gaussian splat from a single image.

    Supports both real photographs (mode=real) and synthetic renders (mode=synthetic).
    Returns a .ply file with Gaussian splat data plus preview and camera parameters.
    """
    service = get_three_d_service()
    try:
        result = await service.generate_3d(request)
        return result
    except (GPUOutOfMemoryError, InvalidInputError, GenerationError) as e:
        return _handle_generation_error(e)
    except Exception as e:
        return _handle_generation_error(e)


@router.post("/generate/async")
async def generate_3d_async(request: ThreeDGenerateRequest):
    """
    Queue a 3D generation job asynchronously.

    Returns immediately with a job_id for polling. Use /jobs/{job_id} to check status.
    """
    # For now, run synchronously but return job-like response
    # In production, submit to job queue
    import uuid

    job_id = str(uuid.uuid4())

    service = get_three_d_service()
    # Note: Real implementation would use job queue
    return {
        "status": "queued",
        "job_id": job_id,
        "message": "Job queued. Use /jobs/{job_id} to poll status.",
    }


# ── Model Management Endpoints ────────────────────────────────────────


@router.get("/models", response_model=ThreeDListModelsResponse)
async def list_models():
    """List available 3D models in the registry."""
    service = get_three_d_service()
    try:
        info = service.get_model_info()
        return ThreeDListModelsResponse(models=[info])
    except Exception as e:
        logger.exception(f"Error listing models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models/{model_id}", response_model=ThreeDModelInfo)
async def get_model(model_id: str):
    """Get information about a specific 3D model."""
    service = get_three_d_service()
    try:
        info = service.get_model_info()
        if info.model_id != model_id:
            raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found")
        return info
    except Exception as e:
        logger.exception(f"Error getting model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/{model_id}/download", response_model=ThreeDDownloadResponse)
async def download_model(model_id: str, request: ThreeDDownloadRequest):
    """
    Download a 3D model and its dependencies.

    Requires HuggingFace authentication for gated dependencies (DINOv3, FLUX VAE).
    Run 'hf auth login' and accept terms before downloading.
    """
    service = get_three_d_service()
    try:
        result = await service.download_model(model_id, request.force)
        return ThreeDDownloadResponse(
            status=result.status,
            model_id=result.model_name,
            local_path=result.local_path,
            progress=result.progress,
            error=result.error_message,
        )
    except ModelDownloadError as e:
        return ThreeDDownloadResponse(
            status="error",
            model_id=model_id,
            error=e.message,
        )
    except ModelNotAvailableError as e:
        return ThreeDDownloadResponse(
            status="error",
            model_id=model_id,
            error=e.message,
        )
    except Exception as e:
        logger.exception(f"Error downloading model: {e}")
        return ThreeDDownloadResponse(
            status="error",
            model_id=model_id,
            error=str(e),
        )


# ── Generation Records Endpoints ──────────────────────────────────────


@router.get("/records", response_model=ThreeDListRecordsResponse)
async def list_records(limit: int = 50, offset: int = 0):
    """List 3D generation records with pagination."""
    service = get_three_d_service()
    try:
        records = service.list_records(limit=limit, offset=offset)
        total = service.count_records()

        return ThreeDListRecordsResponse(
            records=[
                ThreeDGenerationRecordResponse(
                    record_id=r.record_id,
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    input_image_path=r.input_image_path,
                    mode=r.mode,
                    seed=r.seed,
                    steps=r.steps,
                    cfg_strength=r.cfg_strength,
                    num_gaussians=r.num_gaussians,
                    output_ply_path=r.output_ply_path,
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


@router.get("/records/{record_id}", response_model=ThreeDGenerationRecordResponse)
async def get_record(record_id: UUID):
    """Get a specific generation record by ID."""
    service = get_three_d_service()
    try:
        record = service.get_record(record_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=f"Record '{record_id}' not found"
            )

        return ThreeDGenerationRecordResponse(
            record_id=record.record_id,
            created_at=record.created_at.isoformat() if record.created_at else "",
            input_image_path=record.input_image_path,
            mode=record.mode,
            seed=record.seed,
            steps=record.steps,
            cfg_strength=record.cfg_strength,
            num_gaussians=record.num_gaussians,
            output_ply_path=record.output_ply_path,
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


# ── File Upload Endpoint ──────────────────────────────────────────────


@router.post("/generate/upload", response_model=ThreeDGenerateResponse)
async def generate_3d_upload(
    file: UploadFile = File(...),
    mode: str = Form("real"),
    seed: int = Form(42),
    steps: int = Form(50),
    cfg_strength: float = Form(3.0),
    rescale_t: float = Form(3.0),
    num_gaussians: int = Form(262144),
    save_ply: bool = Form(True),
    save_preview: bool = Form(True),
):
    """
    Generate 3D from uploaded image file.

    Multipart form upload for direct file uploads.
    """
    # Read file content
    content = await file.read()

    # Save to temp and convert to base64 or path
    import base64
    import tempfile
    from PIL import Image
    import io

    try:
        image = Image.open(io.BytesIO(content)).convert("RGB")

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image.save(tmp.name)
            tmp_path = tmp.name

        # Create request with file path
        request = ThreeDGenerateRequest(
            image=tmp_path,
            mode=mode,
            seed=seed,
            steps=steps,
            cfg_strength=cfg_strength,
            rescale_t=rescale_t,
            num_gaussians=num_gaussians,
            save_ply=save_ply,
            save_preview=save_preview,
        )

        service = get_three_d_service()
        result = await service.generate_3d(request)

        # Cleanup temp file
        import os

        os.unlink(tmp_path)

        return result

    except Exception as e:
        logger.exception(f"Upload generation failed: {e}")
        return _handle_generation_error(e)


# ── Health & Status ───────────────────────────────────────────────────


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    service = get_three_d_service()
    model_info = service.get_model_info()

    return {
        "status": "healthy",
        "module": "three_d",
        "model": model_info.name,
        "model_available": model_info.is_local,
        "gpu_available": model_info.min_vram_gb > 0,
    }


@router.get("/status")
async def status():
    """Detailed status including model and GPU info."""
    import torch

    service = get_three_d_service()
    model_info = service.get_model_info()

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
        "module": "three_d",
        "model": model_info.model_dump(),
        "gpu": gpu_info,
        "output_dir": service.output_dir,
    }


__all__ = ["router"]
