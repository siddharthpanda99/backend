"""Filters background-job executors.

Moves blocking filter operations OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_filters_executors_registered` and runs on a jobs
worker thread under a per-device semaphore (gpu: 1, cpu: 4).

Artifact policy: image bytes are persisted with
``common_lib.modules.jobs.artifacts.save_artifact`` and only the ref strings
land in ``result_refs``. Inline ``image_b64`` payloads are decoded to PNG
artifacts and stripped from stored metadata — raw base64 never touches
``JobRecord``. A ``result.json`` metadata artifact (b64-free) accompanies
every job.

Completion fan-out (SSE/inbox) is handled by ``JobService`` itself, which
calls ``notify_job_complete`` on every terminal transition.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

APPLY_KIND = "filters.apply"
APPLY_DEVICE = "cpu"
APPLY_TIMEOUT = 120.0

APPLY_OPERATIONS_KIND = "filters.apply_operations"
APPLY_OPERATIONS_DEVICE = "cpu"
APPLY_OPERATIONS_TIMEOUT = 300.0

PREVIEW_KIND = "filters.preview"
PREVIEW_DEVICE = "cpu"
PREVIEW_TIMEOUT = 120.0

PRESET_APPLY_KIND = "filters.preset.apply"
PRESET_APPLY_DEVICE = "cpu"
PRESET_APPLY_TIMEOUT = 120.0

PRESET_PREVIEWS_KIND = "filters.presets.generate_previews"
PRESET_PREVIEWS_DEVICE = "cpu"
PRESET_PREVIEWS_TIMEOUT = 600.0

# Keys that carry inline image payloads — always stripped before persisting.
_B64_KEYS: tuple[str, ...] = ("image_b64", "image", "images")


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


def _strip_b64(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload without inline image blobs."""
    return {k: v for k, v in payload.items() if k not in _B64_KEYS}


def _decode_image(b64_data: str) -> np.ndarray:
    """Decode base64 image to RGB numpy array."""
    raw = base64.b64decode(b64_data)
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(pil)


def _encode_image(arr: np.ndarray) -> str:
    """Encode RGB numpy array to base64 PNG."""
    pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _image_to_bytes(arr: np.ndarray) -> bytes:
    """Encode RGB numpy array to PNG bytes."""
    pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def _save_png(job_id: str, filename: str, image_bytes: bytes) -> str:
    """Persist PNG bytes as a job artifact. Returns the ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    return save_artifact(job_id, filename, image_bytes)


def _save_json(job_id: str, filename: str, payload: dict[str, Any]) -> str:
    """Persist a JSON-serializable metadata payload. Returns the ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    return save_artifact(
        job_id, filename, json.dumps(payload, default=str).encode("utf-8")
    )


def _cancelled_result() -> dict[str, Any]:
    return {"result_refs": [], "status": "cancelled"}


async def _run_async(coro_factory: Callable[[], Any]) -> Any:
    """Run an async coroutine to completion on this worker thread."""
    import asyncio

    return asyncio.run(coro_factory())


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
    clean: dict[str, Any] = _strip_b64(dict(payload))
    clean["artifact_images"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(_save_json(job_id, "result.json", clean))
    return {"result_refs": refs, "status": status}


# ---------------------------------------------------------------------------
# Filter operation executors
# ---------------------------------------------------------------------------


def apply_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``filters.apply`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("file") or params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "No image provided"}, status="error")
    image = _decode_image(image_b64)
    filter_id = params.get("filter_id")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.filter_service import (
        FilterService,
    )

    service = FilterService()
    result_image = service.apply_filter(image, filter_id)
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result_image)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "filtered.png"),))


def apply_operations_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``filters.apply_operations`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("file") or params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "No image provided"}, status="error")
    image = _decode_image(image_b64)

    operations_data = params.get("operations")
    if not operations_data:
        return _finish(job_id, {"error": "No operations provided"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.filter_service import (
        FilterService,
        FilterOperation,
    )

    service = FilterService()
    ops = [FilterOperation(**op) for op in operations_data]
    result_image = service.apply_operations(image, ops)
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result_image)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "filtered.png"),))


def preview_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``filters.preview`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("file") or params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "No image provided"}, status="error")
    image = _decode_image(image_b64)

    operations_data = params.get("operations")
    if not operations_data:
        return _finish(job_id, {"error": "No operations provided"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.filter_service import (
        FilterService,
        FilterOperation,
    )

    service = FilterService()
    ops = [FilterOperation(**op) for op in operations_data]
    result_image = service.apply_operations(image, ops)
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    import base64

    buf = io.BytesIO()
    result_image.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return _finish(
        job_id,
        {
            "status": "success",
            "preview": f"data:image/png;base64,{b64}",
            "width": result_image.width,
            "height": result_image.height,
            "operations_count": len(ops),
        },
    )


def preset_apply_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``filters.preset.apply`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("file") or params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "No image provided"}, status="error")
    image = _decode_image(image_b64)
    preset_id = params.get("preset_id")

    if not preset_id:
        return _finish(job_id, {"error": "No preset_id provided"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.filter_service import (
        FilterService,
    )

    service = FilterService()
    result_image = service.apply_preset(image, preset_id)
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result_image)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "preset_applied.png"),))


def preset_previews_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``filters.presets.generate_previews`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    regenerate = params.get("regenerate", False)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.filter_service import (
        FilterService,
    )

    service = FilterService()
    results = service.generate_preset_previews(regenerate=regenerate)
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    generated = sum(1 for r in results if r["status"] == "generated")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    errors = sum(1 for r in results if r["status"] == "error")

    return _finish(
        job_id,
        {
            "status": "success",
            "results": results,
            "summary": {
                "total": len(results),
                "generated": generated,
                "skipped": skipped,
                "errors": errors,
            },
        },
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (APPLY_KIND, apply_executor, APPLY_DEVICE, APPLY_TIMEOUT),
    (APPLY_OPERATIONS_KIND, apply_operations_executor, APPLY_OPERATIONS_DEVICE, APPLY_OPERATIONS_TIMEOUT),
    (PREVIEW_KIND, preview_executor, PREVIEW_DEVICE, PREVIEW_TIMEOUT),
    (PRESET_APPLY_KIND, preset_apply_executor, PRESET_APPLY_DEVICE, PRESET_APPLY_TIMEOUT),
    (PRESET_PREVIEWS_KIND, preset_previews_executor, PRESET_PREVIEWS_DEVICE, PRESET_PREVIEWS_TIMEOUT),
)


def ensure_filters_executors_registered() -> bool:
    """Register all filters executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_filters_executors_registered failed: %s", exc)
        return False


__all__ = [
    "APPLY_DEVICE",
    "APPLY_KIND",
    "APPLY_TIMEOUT",
    "APPLY_OPERATIONS_DEVICE",
    "APPLY_OPERATIONS_KIND",
    "APPLY_OPERATIONS_TIMEOUT",
    "PRESET_APPLY_DEVICE",
    "PRESET_APPLY_KIND",
    "PRESET_APPLY_TIMEOUT",
    "PRESET_PREVIEWS_DEVICE",
    "PRESET_PREVIEWS_KIND",
    "PRESET_PREVIEWS_TIMEOUT",
    "PREVIEW_DEVICE",
    "PREVIEW_KIND",
    "PREVIEW_TIMEOUT",
    "apply_executor",
    "apply_operations_executor",
    "ensure_filters_executors_registered",
    "preset_apply_executor",
    "preset_previews_executor",
    "preview_executor",
]