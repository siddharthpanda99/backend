"""SAM3 background-job executors.

Moves blocking SAM3 operations OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_sam3_executors_registered` and runs on a jobs
worker thread under a per-device semaphore (gpu: 1, cpu: 4).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

SESSION_ACTION_KIND = "sam3.session_action"
SESSION_ACTION_DEVICE = "gpu"
SESSION_ACTION_TIMEOUT = 300.0

SESSION_CREATE_KIND = "sam3.session_create"
SESSION_CREATE_DEVICE = "gpu"
SESSION_CREATE_TIMEOUT = 120.0


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
# SAM3 operation executors
# ---------------------------------------------------------------------------


def session_create_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``sam3.session_create`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_base64 = params.get("image_base64")
    if not image_base64:
        return _finish(job_id, {"error": "Missing image_base64"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.sam3.service import get_sam3_service

    svc = get_sam3_service()
    result = _run_async(lambda: svc.create_session(image_base64))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "message": "Session created", "data": result})


def session_action_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``sam3.session_action`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    session_id = params.get("session_id")
    action = params.get("action")
    action_params = params.get("params", {})

    if not session_id or not action:
        return _finish(job_id, {"error": "Missing session_id or action"}, status="error")

    report_progress(20.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.sam3.service import get_sam3_service

    svc = get_sam3_service()
    result = _run_async(
        lambda: svc.execute_action(
            session_id=session_id,
            action=action,
            params=action_params,
        )
    )

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "message": f"Action '{action}' completed", "data": {"result": result}})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (SESSION_CREATE_KIND, session_create_executor, SESSION_CREATE_DEVICE, SESSION_CREATE_TIMEOUT),
    (SESSION_ACTION_KIND, session_action_executor, SESSION_ACTION_DEVICE, SESSION_ACTION_TIMEOUT),
)


def ensure_sam3_executors_registered() -> bool:
    """Register all SAM3 executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_sam3_executors_registered failed: %s", exc)
        return False


__all__ = [
    "SESSION_ACTION_DEVICE",
    "SESSION_ACTION_KIND",
    "SESSION_ACTION_TIMEOUT",
    "SESSION_CREATE_DEVICE",
    "SESSION_CREATE_KIND",
    "SESSION_CREATE_TIMEOUT",
    "ensure_sam3_executors_registered",
    "session_action_executor",
    "session_create_executor",
]