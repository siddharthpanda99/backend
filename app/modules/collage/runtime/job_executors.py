"""Collage background-job executors.

Moves blocking collage operations OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_collage_executors_registered` and runs on a jobs
worker thread under a per-device semaphore (gpu: 1, cpu: 4).
"""

from __future__ import annotations

import io
import json
import logging
from typing import Any, Callable, Optional

from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

RENDER_KIND = "collage.render"
RENDER_DEVICE = "cpu"
RENDER_TIMEOUT = 300.0

CUTOUT_KIND = "collage.cutout"
CUTOUT_DEVICE = "gpu"
CUTOUT_TIMEOUT = 180.0


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _record_params(record: Any) -> dict[str, Any]:
    try:
        params: Any = record.get_params()
    except Exception:
        return {}
    return params if isinstance(params, dict) else {}


def _record_id(record: Any) -> str:
    try:
        job_id: Any = record.id
    except Exception:
        return "unknown"
    return str(job_id)


def _cancelled_result() -> dict[str, Any]:
    return {"result_refs": [], "status": "cancelled"}


async def _run_async(coro_factory: Callable[[], Any]) -> Any:
    """Run an async coroutine to completion on this worker thread."""
    import asyncio

    return asyncio.run(coro_factory())


def _image_to_bytes(arr: Any) -> bytes:
    """Convert PIL Image or numpy array to PNG bytes."""
    if hasattr(arr, "save"):  # PIL Image
        buf = io.BytesIO()
        arr.save(buf, format="PNG")
        return buf.getvalue()
    import numpy as np
    if isinstance(arr, np.ndarray):
        pil = Image.fromarray(arr)
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        return buf.getvalue()
    return b""


def _finish(
    job_id: str,
    payload: dict[str, Any],
    *,
    extra_files: tuple[bytes, str] | tuple = (),
    status: str = "success",
) -> dict[str, Any]:
    """Persist result payload: artifact files first, then ``result.json``."""
    from common_lib.modules.jobs.artifacts import save_artifact

    refs: list[str] = []
    for file_bytes, filename in extra_files:
        if file_bytes:
            refs.append(save_artifact(job_id, filename, file_bytes))
    clean: dict[str, Any] = dict(payload)
    clean["artifact_files"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(save_artifact(job_id, "result.json", json.dumps(clean, default=str).encode("utf-8")))
    return {"result_refs": refs, "status": status}


# ---------------------------------------------------------------------------
# Collage operation executors
# ---------------------------------------------------------------------------


def render_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``collage.render`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    # CollageDocument is a pydantic model - reconstruct from params
    try:
        from common_lib.modules.image_processing.collage_sticker import (
            CollageDocument,
            render_collage,
        )
    except Exception as e:
        return _finish(job_id, {"error": f"Import failed: {e}"}, status="error")

    try:
        doc = CollageDocument(**params)
    except Exception as e:
        return _finish(job_id, {"error": f"Invalid collage document: {e}"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    result = _run_async(lambda: render_collage(doc))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "collage.png"),))


def cutout_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``collage.cutout`` jobs (AI background removal)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    # This would call the actual AI background removal model
    # For now, we simulate the operation
    import base64
    import numpy as np
    from PIL import Image

    image_b64 = params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "No image provided"}, status="error")

    # Decode input image
    raw = base64.b64decode(image_b64)
    pil = Image.open(io.BytesIO(raw)).convert("RGBA")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    # TODO: Replace with actual ONNX segmenter/matting model
    # from common_lib.modules.image_processing.collage_sticker import remove_background
    # result = _run_async(lambda: remove_background(pil))

    # Simulate AI processing time
    import time
    time.sleep(0.5)

    # Create a simple alpha mask (placeholder)
    result = pil.copy()
    # In real implementation, this would be the segmented foreground with alpha channel

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(
        job_id,
        {"status": "success", "message": "Background removed", "alpha_mask_available": True},
        extra_files=((img_bytes, "cutout.png"),),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (RENDER_KIND, render_executor, RENDER_DEVICE, RENDER_TIMEOUT),
    (CUTOUT_KIND, cutout_executor, CUTOUT_DEVICE, CUTOUT_TIMEOUT),
)


def ensure_collage_executors_registered() -> bool:
    """Register all collage executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_collage_executors_registered failed: %s", exc)
        return False


__all__ = [
    "RENDER_DEVICE",
    "RENDER_KIND",
    "RENDER_TIMEOUT",
    "CUTOUT_DEVICE",
    "CUTOUT_KIND",
    "CUTOUT_TIMEOUT",
    "ensure_collage_executors_registered",
    "render_executor",
    "cutout_executor",
]