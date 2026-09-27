"""Qwen-Image-2.1 REST endpoints — thin routers over the jobs module.

Modes: txt2img (JSON) / img2img / inpaint / outpaint (multipart uploads).
Generation is jobs-backed (``vision.qwen21.*`` executors, artifacts on disk,
refs only); pass ``sync=true`` to run inline and get the legacy synchronous
response. Business logic lives in
``common_lib.modules.image_processing.services.qwen21_service``.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.modules.jobs.actor import capture_job_actor, owned_job_service

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/qwen21",
    tags=["Qwen-Image 2.1"],
    dependencies=[Depends(capture_job_actor)],
)


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


def _ensure_jobs():
    from app.modules.vision.runtime.job_executors import (
        ensure_vision_executors_registered,
    )

    ensure_vision_executors_registered()
    return owned_job_service()


def _ok(meta: dict[str, Any]) -> dict[str, Any]:
    return {"status": "success", **meta}


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _job_payload(record: Any) -> dict[str, Any]:
    refs: list[str] = []
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


def _job_status(job_id: str) -> dict[str, Any]:
    """Jobs-backed status view with b64-free metadata (never inline blobs)."""
    svc = _ensure_jobs()
    record = svc.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: dict[str, Any] = _job_payload(record)
    meta: dict[str, Any] = {}
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    for ref in refs:
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


@router.get("/status")
async def qwen21_status() -> dict[str, Any]:
    """Native stack readiness (files on disk) + loaded state."""
    from common_lib.modules.image_processing.native_stacks import (
        get_native_stack_readiness,
    )

    readiness = get_native_stack_readiness("qwen21")
    readiness["loaded"] = _service().is_loaded
    return readiness


@router.get("/jobs/{job_id}")
async def qwen21_job_status(job_id: str) -> dict[str, Any]:
    """Poll a jobs-backed Qwen-Image-2.1 generation job."""
    return _job_status(job_id)


@router.post("/txt2img")
async def qwen21_txt2img(
    request: Qwen21Txt2ImgRequest, sync: bool = False
) -> dict[str, Any]:
    """Text → image (official t2i path). Jobs-backed; ``sync=true`` for inline."""
    if sync:
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
    from app.modules.vision.runtime.job_executors import QWEN21_TXT2IMG_KIND

    record = _ensure_jobs().submit(
        QWEN21_TXT2IMG_KIND,
        params={
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "steps": request.steps,
            "cfg": request.cfg,
            "seed": request.seed,
            "device": "cuda",
        },
    )
    return {"status": "queued", "model": "qwen21", **_job_payload(record)}


@router.post("/img2img")
async def qwen21_img2img(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    strength: float = Form(0.6),
    steps: int = Form(20),
    cfg: float = Form(1.0),
    seed: int = Form(0),
    sync: bool = False,
) -> dict[str, Any]:
    """Image + prompt → re-imagined image (official edit path). Jobs-backed."""
    raw: bytes = await image.read()
    if sync:
        try:
            meta = _service().img2img(
                prompt=prompt,
                image=raw,
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
    from app.modules.vision.runtime.job_executors import QWEN21_IMG2IMG_KIND

    record = _ensure_jobs().submit(
        QWEN21_IMG2IMG_KIND,
        params={
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image_b64": _b64(raw),
            "strength": strength,
            "steps": steps,
            "cfg": cfg,
            "seed": seed,
            "device": "cuda",
        },
    )
    return {"status": "queued", "model": "qwen21", **_job_payload(record)}


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
    sync: bool = False,
) -> dict[str, Any]:
    """Repaint the masked region (mask white = repaint). Jobs-backed."""
    raw: bytes = await image.read()
    mask_raw: bytes = await mask.read()
    if sync:
        try:
            meta = _service().inpaint(
                prompt=prompt,
                image=raw,
                mask=mask_raw,
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
    from app.modules.vision.runtime.job_executors import QWEN21_INPAINT_KIND

    record = _ensure_jobs().submit(
        QWEN21_INPAINT_KIND,
        params={
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image_b64": _b64(raw),
            "mask_b64": _b64(mask_raw),
            "strength": strength,
            "steps": steps,
            "cfg": cfg,
            "seed": seed,
            "feather_px": feather_px,
            "device": "cuda",
        },
    )
    return {"status": "queued", "model": "qwen21", **_job_payload(record)}


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
    sync: bool = False,
) -> dict[str, Any]:
    """Expand the canvas by ``pad`` px per side, repaint the border. Jobs-backed."""
    raw: bytes = await image.read()
    if sync:
        try:
            meta = _service().outpaint(
                prompt=prompt,
                image=raw,
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
    from app.modules.vision.runtime.job_executors import QWEN21_OUTPAINT_KIND

    record = _ensure_jobs().submit(
        QWEN21_OUTPAINT_KIND,
        params={
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image_b64": _b64(raw),
            "pad": pad,
            "steps": steps,
            "cfg": cfg,
            "seed": seed,
            "feather_px": feather_px,
            "device": "cuda",
        },
    )
    return {"status": "queued", "model": "qwen21", **_job_payload(record)}


__all__ = ["router"]
