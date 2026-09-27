"""Doc Processing background-job executors.

Moves blocking PDF/document operations OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_doc_processing_executors_registered` and runs on a jobs
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

EXTRACT_FULL_KIND = "doc_processing.extract.full"
EXTRACT_FULL_DEVICE = "cpu"
EXTRACT_FULL_TIMEOUT = 600.0

EXTRACT_TEXT_KIND = "doc_processing.extract.text"
EXTRACT_TEXT_DEVICE = "cpu"
EXTRACT_TEXT_TIMEOUT = 300.0

EXTRACT_TABLES_KIND = "doc_processing.extract.tables"
EXTRACT_TABLES_DEVICE = "cpu"
EXTRACT_TABLES_TIMEOUT = 300.0

EXTRACT_METADATA_KIND = "doc_processing.extract.metadata"
EXTRACT_METADATA_DEVICE = "cpu"
EXTRACT_METADATA_TIMEOUT = 120.0


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
# Doc Processing operation executors
# ---------------------------------------------------------------------------


def _get_pipeline():
    from common_lib.modules.doc_processing.pdf_extractor.pipeline.extraction_pipeline import PDFExtractionPipeline
    return PDFExtractionPipeline()


def extract_full_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``doc_processing.extract.full`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    file_path = params.get("file_path")
    if not file_path:
        return _finish(job_id, {"error": "Missing file_path"}, status="error")

    options = params.get("options", {})

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    pipeline = _get_pipeline()
    result = _run_async(lambda: pipeline.extract(file_path, **options) if hasattr(pipeline, "extract") else {"file": file_path})

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def extract_text_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``doc_processing.extract.text`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    file_path = params.get("file_path")
    if not file_path:
        return _finish(job_id, {"error": "Missing file_path"}, status="error")

    pages = params.get("pages")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    pipeline = _get_pipeline()
    result = _run_async(lambda: pipeline.extract_text(file_path, pages=pages) if hasattr(pipeline, "extract_text") else {"text": ""})

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def extract_tables_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``doc_processing.extract.tables`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    file_path = params.get("file_path")
    if not file_path:
        return _finish(job_id, {"error": "Missing file_path"}, status="error")

    pages = params.get("pages")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    pipeline = _get_pipeline()
    result = _run_async(lambda: pipeline.extract_tables(file_path, pages=pages) if hasattr(pipeline, "extract_tables") else {"tables": []})

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


def extract_metadata_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``doc_processing.extract.metadata`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    file_path = params.get("file_path")
    if not file_path:
        return _finish(job_id, {"error": "Missing file_path"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    pipeline = _get_pipeline()
    result = _run_async(lambda: pipeline.extract_metadata(file_path) if hasattr(pipeline, "extract_metadata") else {"metadata": {}})

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", "result": result})


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (EXTRACT_FULL_KIND, extract_full_executor, EXTRACT_FULL_DEVICE, EXTRACT_FULL_TIMEOUT),
    (EXTRACT_TEXT_KIND, extract_text_executor, EXTRACT_TEXT_DEVICE, EXTRACT_TEXT_TIMEOUT),
    (EXTRACT_TABLES_KIND, extract_tables_executor, EXTRACT_TABLES_DEVICE, EXTRACT_TABLES_TIMEOUT),
    (EXTRACT_METADATA_KIND, extract_metadata_executor, EXTRACT_METADATA_DEVICE, EXTRACT_METADATA_TIMEOUT),
)


def ensure_doc_processing_executors_registered() -> bool:
    """Register all doc_processing executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_doc_processing_executors_registered failed: %s", exc)
        return False


__all__ = [
    "EXTRACT_FULL_DEVICE",
    "EXTRACT_FULL_KIND",
    "EXTRACT_FULL_TIMEOUT",
    "EXTRACT_METADATA_DEVICE",
    "EXTRACT_METADATA_KIND",
    "EXTRACT_METADATA_TIMEOUT",
    "EXTRACT_TABLES_DEVICE",
    "EXTRACT_TABLES_KIND",
    "EXTRACT_TABLES_TIMEOUT",
    "EXTRACT_TEXT_DEVICE",
    "EXTRACT_TEXT_KIND",
    "EXTRACT_TEXT_TIMEOUT",
    "ensure_doc_processing_executors_registered",
    "extract_full_executor",
    "extract_metadata_executor",
    "extract_tables_executor",
    "extract_text_executor",
]