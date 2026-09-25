"""Qwen-Image-2.1 REST endpoints — thin routers over the common_lib service.

Modes: txt2img (JSON) / img2img / inpaint / outpaint (multipart uploads).
All business logic lives in
``common_lib.modules.image_processing.services.qwen21_service``.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/qwen21", tags=["Qwen-Image 2.1"])


class Qwen21Txt2ImgRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt")
    negative_prompt: str = Field("", description="Negative prompt (cfg > 1 only)")
    width: int = Field(1024, description="Width px (multiple of 16)")
    height: int = Field(1024, description="Height px (multiple of 16)")
    steps: int = Field(20, description="Euler steps (official range 20-50)")
    cfg: float = Field(1.0, description="Guidance scale (1.0 = distilled)")
    seed: int = Field(0, description="Seed (0 = deterministic default)")


def _service():
    from common_lib.modules.image_processing.services.qwen21_service import (
        get_qwen21_service,
    )

    return get_qwen21_service()


def _ok(meta: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", **meta}


@router.get("/status")
async def qwen21_status() -> dict[str, Any]:
    """Native stack readiness (files on disk) + loaded state."""
    from common_lib.modules.image_processing.native_stacks import (
        get_native_stack_readiness,
    )

    readiness = get_native_stack_readiness("qwen21")
    readiness["loaded"] = _service().is_loaded
    return readiness


@router.post("/txt2img")
async def qwen21_txt2img(request: Qwen21Txt2ImgRequest) -> dict[str, Any]:
    """Text → image (official t2i path). Returns base64 PNG + metadata."""
    try:
        meta = _service().txt2img(
            prompt=request.prompt,
            width=request.width,
            height=request.height,
            steps=request.steps,
            cfg=request.cfg,
            seed=request.seed,
            negative_prompt=request.negative_prompt,
        )
        return _ok(meta)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception(f"qwen21 txt2img failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/img2img")
async def qwen21_img2img(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    strength: float = Form(0.6),
    steps: int = Form(20),
    cfg: float = Form(1.0),
    seed: int = Form(0),
) -> dict[str, Any]:
    """Image + prompt → re-imagined image (official edit path)."""
    try:
        meta = _service().img2img(
            prompt=prompt,
            image=await image.read(),
            strength=strength,
            steps=steps,
            cfg=cfg,
            seed=seed,
            negative_prompt=negative_prompt,
        )
        return _ok(meta)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception(f"qwen21 img2img failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inpaint")
async def qwen21_inpaint(
    image: UploadFile = File(...),
    mask: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    strength: float = Form(1.0),
    steps: int = Form(20),
    cfg: float = Form(1.0),
    seed: int = Form(0),
    feather_px: int = Form(16),
) -> dict[str, Any]:
    """Repaint the masked region (mask white = repaint)."""
    try:
        meta = _service().inpaint(
            prompt=prompt,
            image=await image.read(),
            mask=await mask.read(),
            strength=strength,
            steps=steps,
            cfg=cfg,
            seed=seed,
            negative_prompt=negative_prompt,
            feather_px=feather_px,
        )
        return _ok(meta)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception(f"qwen21 inpaint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outpaint")
async def qwen21_outpaint(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    pad: int = Form(256),
    steps: int = Form(20),
    cfg: float = Form(1.0),
    seed: int = Form(0),
    feather_px: int = Form(32),
) -> dict[str, Any]:
    """Expand the canvas by ``pad`` px per side, repaint the border."""
    try:
        meta = _service().outpaint(
            prompt=prompt,
            image=await image.read(),
            pad=pad,
            steps=steps,
            cfg=cfg,
            seed=seed,
            negative_prompt=negative_prompt,
            feather_px=feather_px,
        )
        return _ok(meta)
    except FileNotFoundError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.exception(f"qwen21 outpaint failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
