"""Image Processing module API routes — Loaders, Encoding, Sampling, Segmentation.

Thin routing layer that delegates to common_lib.modules.image_processing services.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# Loader endpoints
# ---------------------------------------------------------------------------

@router.post("/load")
async def load_image(request: LoadImageRequest) -> Dict[str, Any]:
    """Load an image from path."""
    try:
        svc = _get_image_service()
        result = svc.load_image(request.image_path) if hasattr(svc, "load_image") else {"path": request.image_path}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoints")
async def list_checkpoints() -> Dict[str, Any]:
    """List available model checkpoints."""
    try:
        svc = _get_image_service()
        result = svc.list_checkpoints() if hasattr(svc, "list_checkpoints") else []
        return {"checkpoints": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/loras")
async def list_loras() -> Dict[str, Any]:
    """List available LoRA models."""
    try:
        svc = _get_image_service()
        result = svc.list_loras() if hasattr(svc, "list_loras") else []
        return {"loras": result, "count": len(result) if isinstance(result, list) else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Captioning endpoints
# ---------------------------------------------------------------------------

@router.post("/caption")
async def caption_image(request: CaptionRequest) -> Dict[str, Any]:
    """Generate a caption for an image."""
    try:
        svc = _get_image_service()
        result = svc.caption(request.image_path, model=request.model) if hasattr(svc, "caption") else {"caption": ""}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Segmentation endpoints
# ---------------------------------------------------------------------------

@router.post("/segment")
async def segment_image(request: SegmentRequest) -> Dict[str, Any]:
    """Segment an image using SAM3."""
    try:
        svc = _get_image_service()
        result = svc.segment(request.image_path, prompt=request.prompt) if hasattr(svc, "segment") else {"segments": []}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Face swap (ReActor) endpoints
# ---------------------------------------------------------------------------

@router.post("/face-swap")
async def face_swap(request: FaceSwapRequest) -> Dict[str, Any]:
    """Perform face swap using ReActor."""
    try:
        svc = _get_image_service()
        result = svc.face_swap(request.source_image, request.target_image) if hasattr(svc, "face_swap") else {"swapped": False}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# CLIP encoding endpoints
# ---------------------------------------------------------------------------

@router.post("/encode")
async def encode_image(image_path: str, text: Optional[str] = None) -> Dict[str, Any]:
    """Encode image using CLIP."""
    try:
        svc = _get_image_service()
        result = svc.encode(image_path, text) if hasattr(svc, "encode") else {"encoding": None}
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
