"""Image Processing Ops Routes — Expose all image operations as REST API endpoints.

Each operation accepts an image upload + JSON params and returns a processed image.
"""

from __future__ import annotations

import io
import logging
import json
import time
import asyncio
import base64
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
from fastapi.responses import Response, StreamingResponse

from common_lib.modules.image_processing.ops_service import (
    list_operations_flat,
    process_image,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ops", tags=["Image Ops"])


def _sse(event: str, data: Dict[str, Any]) -> str:
    """Build an SSE message string."""
    return "event: {}\ndata: {}\n\n".format(event, json.dumps(data))


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


@router.post("/batch/stream")
async def run_batch_stream(
    body: Dict[str, Any] = Body(...),
):
    """Batch-process images with SSE per-image progress.

    Body: {
        "method": str,
        "params": dict,
        "images": [str, ...],   # list of base64-encoded images
    }
    Yields per-image SSE events:
      event: progress  — { index, total, percent, phase }
      event: result    — { index, image, error }
      event: complete  — { count, ok, errors }
    """
    method = body.get("method")
    if not method:
        raise HTTPException(400, detail="Missing 'method'")
    images = body.get("images") or []
    if not isinstance(images, list) or not images:
        raise HTTPException(400, detail="'images' must be a non-empty list")
    if len(images) > 100:
        raise HTTPException(400, detail="Maximum 100 images per batch")

    params = dict(body.get("params") or {})
    total = len(images)

    async def event_generator():  # type: ignore[no-untyped-def]
        start_time = time.time()
        ok_count = 0
        error_list: List[str] = []

        for idx, img_b64 in enumerate(images):
            # Per-image progress
            progress_data = {
                "index": idx,
                "total": total,
                "percent": round((idx / total) * 100, 1),
                "phase": "processing",
                "message": "Processing image {}/{}".format(idx + 1, total),
            }
            yield _sse("progress", progress_data)

            try:
                loop = asyncio.get_event_loop()
                raw = await loop.run_in_executor(
                    None, lambda b=img_b64: base64.b64decode(b)
                )
                out = await loop.run_in_executor(
                    None, lambda r=raw: process_image(method, r, dict(params))
                )
                out_b64 = base64.b64encode(out).decode()
                ok_count += 1
                error_list.append("")

                result_data = {
                    "index": idx,
                    "total": total,
                    "image": out_b64,
                    "error": None,
                }
                yield _sse("result", result_data)

            except Exception as e:
                logger.warning("Batch stream op %s image #%d failed: %s", method, idx, e)
                error_list.append(str(e))

                error_result = {
                    "index": idx,
                    "total": total,
                    "image": None,
                    "error": str(e),
                }
                yield _sse("result", error_result)

        elapsed = time.time() - start_time
        complete_data = {
            "count": total,
            "ok": ok_count,
            "failed": total - ok_count,
            "errors": error_list,
            "elapsed_ms": round(elapsed * 1000),
        }
        yield _sse("complete", complete_data)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# Operations that benefit from progress streaming
SLOW_OPS = {
    "restore_face", "gfpgan_restore", "codeformer_restore",
    "swap_face", "reactor_swap", "instantid_generate",
    "pulid_generate", "photomaker_generate",
    "generate_creature", "generate_scene",
    "transform_race", "create_hybrid",
    "transfer_style", "style_transfer",
    "inpaint", "super_resolution", "realesrgan",
    "virtual_try_on", "try_on_outfit",
    "transfer_makeup", "full_beauty_enhance",
    "design_tattoo",
}

# Phases for slow operations
STREAM_PHASES = [
    (0.05, "Analyzing", "Detecting faces and analyzing image..."),
    (0.15, "Preparing", "Loading model and preparing..."),
    (0.30, "Processing", "Running neural network inference..."),
    (0.60, "Generating", "Generating output..."),
    (0.80, "Refining", "Post-processing and refining..."),
    (0.95, "Finalizing", "Encoding final image..."),
]


@router.post("/{method}/stream")
async def run_operation_stream(
    method: str,
    body: Dict[str, Any] = Body(...),
):
    """Execute an operation with SSE progress streaming.

    Yields progress events as the operation executes:
      - event: progress  — { percent, message, phase }
      - event: result    — { image, metadata }
      - event: error     — { message }

    Long-running operations (restoration, swap, generation) emit
    progress at key phases. Fast operations emit start+complete.
    """
    raw_str = body.get("image")
    if not raw_str:
        raise HTTPException(400, detail="Missing 'image' field (base64)")

    try:
        image_data = base64.b64decode(raw_str)
    except Exception:
        raise HTTPException(400, detail="Invalid base64 image data")

    params = {k: v for k, v in body.items() if k != "image"}

    async def event_generator():  # type: ignore[no-untyped-def]
        start_time = time.time()

        # Send initial progress
        yield _sse("progress", {"percent": 0, "message": "Starting...", "phase": "Init"})

        if method in SLOW_OPS:
            # Simulate progress phases while the actual op runs in background
            phase_idx = 0
            done = False
            result_data_raw = None
            error_msg = None

            async def run_op():  # type: ignore[no-untyped-def]
                nonlocal result_data_raw, error_msg, done
                try:
                    loop = asyncio.get_event_loop()
                    result_data_raw = await loop.run_in_executor(
                        None, lambda: process_image(method, image_data, params)
                    )
                except Exception as e:
                    error_msg = str(e)
                finally:
                    done = True

            # Start the operation
            op_task = asyncio.create_task(run_op())

            # Emit progress while operation runs
            while not done:
                if phase_idx < len(STREAM_PHASES):
                    pct, phase_name, phase_msg = STREAM_PHASES[phase_idx]
                    elapsed = time.time() - start_time
                    est_total = elapsed / max(pct, 0.01)
                    remaining = max(0, est_total - elapsed)
                    progress = {
                        "percent": round(pct * 100, 1),
                        "message": "{} (~{:.0f}s remaining)".format(phase_msg, remaining),
                        "phase": phase_name,
                        "elapsed": round(elapsed, 1),
                    }
                    yield _sse("progress", progress)
                    phase_idx += 1
                    await asyncio.sleep(0.3)
                else:
                    elapsed = time.time() - start_time
                    heartbeat = {
                        "percent": round(min(95, 60 + elapsed * 2), 1),
                        "message": "Processing... ({:.1f}s elapsed)".format(elapsed),
                        "phase": "Processing",
                        "elapsed": round(elapsed, 1),
                    }
                    yield _sse("progress", heartbeat)
                    await asyncio.sleep(0.5)

            # Wait for task to complete
            await op_task

            elapsed = time.time() - start_time

            if error_msg:
                yield _sse("error", {"message": error_msg})
                return

            # Send final result
            img_b64 = base64.b64encode(result_data_raw).decode()
            done_progress = {
                "percent": 100,
                "message": "Complete!",
                "phase": "Done",
                "elapsed": round(elapsed, 1),
            }
            yield _sse("progress", done_progress)
            yield _sse("result", {
                "image": img_b64,
                "metadata": {"method": method, "duration_ms": round(elapsed * 1000)},
            })

        else:
            # Fast operation — just run it
            try:
                loop = asyncio.get_event_loop()
                result_data_raw = await loop.run_in_executor(
                    None, lambda: process_image(method, image_data, params)
                )
                elapsed = time.time() - start_time
                img_b64 = base64.b64encode(result_data_raw).decode()
                yield _sse("progress", {
                    "percent": 100,
                    "message": "Complete!",
                    "phase": "Done",
                    "elapsed": round(elapsed, 1),
                })
                yield _sse("result", {
                    "image": img_b64,
                    "metadata": {"method": method, "duration_ms": round(elapsed * 1000)},
                })
            except Exception as e:
                yield _sse("error", {"message": str(e)})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
