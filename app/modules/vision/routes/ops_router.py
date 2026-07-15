"""Image Processing Ops Routes — Expose all image operations as REST API endpoints.

Each operation accepts an image upload + JSON params and returns a processed image.
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response

from common_lib.modules.image_processing.ops_service import (
    list_operations_flat,
    process_image,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ops", tags=["Image Ops"])


@router.get("/list")
def get_operations() -> List[Dict[str, Any]]:
    return list_operations_flat()


@router.post("/{method}")
async def run_operation(
    method: str,
    file: UploadFile = File(...),
    params: Optional[str] = Form(None),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(400, detail="File must be an image")
    raw = await file.read()
    parsed_params: Dict[str, Any] = {}
    if params:
        import json

        try:
            parsed_params = json.loads(params)
        except json.JSONDecodeError:
            raise HTTPException(400, detail="Invalid JSON in params")
    try:
        out = process_image(method, raw, parsed_params)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        logger.exception("Image op %s failed", method)
        raise HTTPException(500, detail=str(e))
    content_type = file.content_type or "image/png"
    return Response(content=out, media_type=content_type)


@router.post("/{method}/json")
async def run_operation_json(
    method: str,
    body: Dict[str, Any] = Body(...),
):
    raw_str = body.get("image")
    if not raw_str:
        raise HTTPException(400, detail="Missing 'image' field (base64)")
    import base64

    try:
        image_data = base64.b64decode(raw_str)
    except Exception:
        raise HTTPException(400, detail="Invalid base64 image data")
    params = {k: v for k, v in body.items() if k != "image"}
    try:
        out = process_image(method, image_data, params)
    except ValueError as e:
        raise HTTPException(404, detail=str(e))
    except Exception as e:
        logger.exception("Image op %s failed", method)
        raise HTTPException(500, detail=str(e))
    return Response(content=out, media_type="image/png")


@router.post("/batch")
async def run_batch(body: Dict[str, Any] = Body(...)):
    """Batch-process a list of images with a single operation.

    Body: {
        "method": str,                 # operation name
        "params": dict,                # shared params for every image
        "images": [str, ...],          # list of base64-encoded images
        "output_format": str           # optional PNG/JPEG/WEBP (default PNG)
    }
    Returns: {
        "results": [str, ...],         # base64-encoded processed images
        "errors": [str, ...],          # per-index error messages (empty on success)
        "count": int, "ok": int
    }
    """
    import base64

    method = body.get("method")
    if not method:
        raise HTTPException(400, detail="Missing 'method'")
    images = body.get("images") or []
    if not isinstance(images, list) or not images:
        raise HTTPException(400, detail="'images' must be a non-empty list")
    if len(images) > 100:
        raise HTTPException(400, detail="Maximum 100 images per batch")
    params = dict(body.get("params") or {})
    out_fmt = params.pop("output_format", body.get("output_format", "PNG"))

    results: List[str] = []
    errors: List[str] = []
    for idx, img_b64 in enumerate(images):
        try:
            raw = base64.b64decode(img_b64)
            out = process_image(method, raw, {**params, "output_format": out_fmt})
            results.append(base64.b64encode(out).decode())
            errors.append("")
        except Exception as e:  # noqa: BLE001 - report per-image, continue
            logger.warning("Batch op %s image #%d failed: %s", method, idx, e)
            results.append("")
            errors.append(str(e))

    ok = sum(1 for e in errors if not e)
    return {
        "results": results,
        "errors": errors,
        "count": len(images),
        "ok": ok,
    }
