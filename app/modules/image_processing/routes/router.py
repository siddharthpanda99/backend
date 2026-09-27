"""Image Processing module API routes — Loaders, Encoding, Sampling, Segmentation.

Thin routing layer that delegates to common_lib.modules.image_processing services.
Heavy ops run jobs-backed (``vision.caption`` / ``vision.segment`` /
``vision.face_swap`` / ``vision.encode`` executors, artifacts on disk, refs
only); pass ``sync=true`` to run inline and get the legacy synchronous
response.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class LoadImageRequest(BaseModel):
    image_path: str
    load_type: Optional[str] = "image"


class CaptionRequest(BaseModel):
    image_path: str
    model: Optional[str] = None


class SegmentRequest(BaseModel):
    image_path: str
    prompt: Optional[str] = None


class FaceSwapRequest(BaseModel):
    source_image: str
    target_image: str
    model: Optional[str] = None


# ---------------------------------------------------------------------------
# Lazy service loader
# ---------------------------------------------------------------------------


def _get_image_service():
    from common_lib.modules.image_processing.pipeline import ImageProcessingPipeline

    return ImageProcessingPipeline()


def _ensure_vision_jobs():
    """Register vision executors and return the JobService singleton."""
    from app.modules.vision.runtime.job_executors import (
        ensure_vision_executors_registered,
    )
    from common_lib.modules.jobs.service import get_job_service

    ensure_vision_executors_registered()
    return get_job_service()


def _job_envelope(record: Any) -> Dict[str, Any]:
    refs: List[str] = []
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    return {
        "job_id": str(record.id),
        "status": str(record.status),
        "kind": str(record.kind),
        "progress": float(record.progress or 0.0),
        "result_refs": refs,
        "error": record.error,
    }


@router.get("/jobs/{job_id}")
async def get_pipeline_job(job_id: str) -> Dict[str, Any]:
    """Poll a jobs-backed pipeline job (caption/segment/face-swap/encode)."""
    svc = _ensure_vision_jobs()
    record = svc.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload = _job_envelope(record)
    meta: Dict[str, Any] = {}
    for ref in payload["result_refs"]:
        if not ref.endswith("result.json"):
            continue
        try:
            with open(ref, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                meta = loaded
                break
        except (OSError, ValueError):
            continue
    payload["meta"] = meta
    return payload


# ---------------------------------------------------------------------------
# Loader endpoints
# ---------------------------------------------------------------------------


@router.post("/load")
async def load_image(request: LoadImageRequest) -> Dict[str, Any]:
    """Load an image from path."""
    try:
        svc = _get_image_service()
        result = (
            svc.load_image(request.image_path)
            if hasattr(svc, "load_image")
            else {"path": request.image_path}
        )
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints")
async def list_checkpoints() -> Dict[str, Any]:
    """List available model checkpoints."""
    try:
        svc = _get_image_service()
        result = svc.list_checkpoints() if hasattr(svc, "list_checkpoints") else []
        return {
            "checkpoints": result,
            "count": len(result) if isinstance(result, list) else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/loras")
async def list_loras() -> Dict[str, Any]:
    """List available LoRA models."""
    try:
        svc = _get_image_service()
        result = svc.list_loras() if hasattr(svc, "list_loras") else []
        return {
            "loras": result,
            "count": len(result) if isinstance(result, list) else 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Captioning endpoints (jobs-backed)
# ---------------------------------------------------------------------------


@router.post("/caption")
async def caption_image(request: CaptionRequest, sync: bool = False) -> Dict[str, Any]:
    """Generate a caption for an image (jobs-backed by default)."""
    if sync:
        try:
            svc = _get_image_service()
            result = (
                svc.caption(request.image_path, model=request.model)
                if hasattr(svc, "caption")
                else {"caption": ""}
            )
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    from app.modules.vision.runtime.job_executors import CAPTION_KIND

    try:
        record = _ensure_vision_jobs().submit(
            CAPTION_KIND,
            params={"image_path": request.image_path, "model": request.model},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "queued", **_job_envelope(record)}


# ---------------------------------------------------------------------------
# Segmentation endpoints (jobs-backed)
# ---------------------------------------------------------------------------


@router.post("/segment")
async def segment_image(request: SegmentRequest, sync: bool = False) -> Dict[str, Any]:
    """Segment an image using SAM3 (jobs-backed by default)."""
    if sync:
        try:
            svc = _get_image_service()
            result = (
                svc.segment(request.image_path, prompt=request.prompt)
                if hasattr(svc, "segment")
                else {"segments": []}
            )
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    from app.modules.vision.runtime.job_executors import SEGMENT_KIND

    try:
        record = _ensure_vision_jobs().submit(
            SEGMENT_KIND,
            params={"image_path": request.image_path, "prompt": request.prompt},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "queued", **_job_envelope(record)}


# ---------------------------------------------------------------------------
# Face swap (ReActor) endpoints (jobs-backed)
# ---------------------------------------------------------------------------


@router.post("/face-swap")
async def face_swap(request: FaceSwapRequest, sync: bool = False) -> Dict[str, Any]:
    """Perform face swap using ReActor (jobs-backed by default)."""
    if sync:
        try:
            svc = _get_image_service()
            result = (
                svc.face_swap(request.source_image, request.target_image)
                if hasattr(svc, "face_swap")
                else {"swapped": False}
            )
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    from app.modules.vision.runtime.job_executors import FACE_SWAP_KIND

    try:
        record = _ensure_vision_jobs().submit(
            FACE_SWAP_KIND,
            params={
                "source_image": request.source_image,
                "target_image": request.target_image,
                "model": request.model,
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "queued", **_job_envelope(record)}


# ---------------------------------------------------------------------------
# CLIP encoding endpoints (jobs-backed)
# ---------------------------------------------------------------------------


@router.post("/encode")
async def encode_image(
    image_path: str, text: Optional[str] = None, sync: bool = False
) -> Dict[str, Any]:
    """Encode image using CLIP (jobs-backed by default)."""
    if sync:
        try:
            svc = _get_image_service()
            result = (
                svc.encode(image_path, text)
                if hasattr(svc, "encode")
                else {"encoding": None}
            )
            return {"result": result}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    from app.modules.vision.runtime.job_executors import ENCODE_KIND

    try:
        record = _ensure_vision_jobs().submit(
            ENCODE_KIND, params={"image_path": image_path, "text": text}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"status": "queued", **_job_envelope(record)}
