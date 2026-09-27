"""DAW background-job executors.

Moves blocking DAW operations OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_daw_executors_registered` and runs on a jobs
worker thread under a per-device semaphore (gpu: 1, cpu: 4).

Artifact policy: audio bytes are persisted with
``common_lib.modules.jobs.artifacts.save_artifact`` and only the ref strings
land in ``result_refs``. A ``result.json`` metadata artifact accompanies
every job.

Completion fan-out (SSE/inbox) is handled by ``JobService`` itself, which
calls ``notify_job_complete`` on every terminal transition.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

EXPORT_PROJECT_KIND = "daw.export_project"
EXPORT_PROJECT_DEVICE = "cpu"
EXPORT_PROJECT_TIMEOUT = 600.0

RENDER_PROJECT_KIND = "daw.render_project"
RENDER_PROJECT_DEVICE = "cpu"
RENDER_PROJECT_TIMEOUT = 1200.0


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
# DAW operation executors
# ---------------------------------------------------------------------------


def export_project_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``daw.export_project`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    project_id = params.get("project_id")
    if not project_id:
        return _finish(job_id, {"error": "Missing project_id"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.audio_processing.daw.service import daw_service
    from common_lib.modules.data_storage.database.connection import get_session

    try:
        with next(get_session()) as session:
            result = daw_service.export_project(session, project_id)
    except Exception as e:
        return _finish(job_id, {"error": str(e)}, status="error")

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "export": result})


def render_project_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``daw.render_project`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    project_id = params.get("project_id")
    output_format = params.get("format", "wav")
    sample_rate = params.get("sample_rate", 44100)
    bit_depth = params.get("bit_depth", 24)

    if not project_id:
        return _finish(job_id, {"error": "Missing project_id"}, status="error")

    report_progress(20.0)
    if check_cancel():
        return _cancelled_result()

    # This would need a render implementation in the DAW service
    # For now, we'll use the export as a fallback
    from common_lib.modules.audio_processing.daw.service import daw_service
    from common_lib.modules.data_storage.database.connection import get_session

    try:
        with next(get_session()) as session:
            result = daw_service.export_project(session, project_id)
    except Exception as e:
        return _finish(job_id, {"error": str(e)}, status="error")

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "render": result, "format": output_format})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (EXPORT_PROJECT_KIND, export_project_executor, EXPORT_PROJECT_DEVICE, EXPORT_PROJECT_TIMEOUT),
    (RENDER_PROJECT_KIND, render_project_executor, RENDER_PROJECT_DEVICE, RENDER_PROJECT_TIMEOUT),
)


def ensure_daw_executors_registered() -> bool:
    """Register all DAW executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_daw_executors_registered failed: %s", exc)
        return False


__all__ = [
    "EXPORT_PROJECT_DEVICE",
    "EXPORT_PROJECT_KIND",
    "EXPORT_PROJECT_TIMEOUT",
    "RENDER_PROJECT_DEVICE",
    "RENDER_PROJECT_KIND",
    "RENDER_PROJECT_TIMEOUT",
    "ensure_daw_executors_registered",
    "export_project_executor",
    "render_project_executor",
]