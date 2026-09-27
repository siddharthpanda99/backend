"""Workflow Failure Analysis background-job executors.

Moves blocking failure analysis operations OFF the FastAPI event loop onto the jobs module.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

FA_ANALYZE_KIND = "workflow.failure_analysis.analyze"
FA_ANALYZE_DEVICE = "cpu"
FA_ANALYZE_TIMEOUT = 300.0

FA_BATCH_KIND = "workflow.failure_analysis.batch"
FA_BATCH_DEVICE = "cpu"
FA_BATCH_TIMEOUT = 1800.0

FA_REPORT_KIND = "workflow.failure_analysis.report"
FA_REPORT_DEVICE = "cpu"
FA_REPORT_TIMEOUT = 600.0

FA_STATS_KIND = "workflow.failure_analysis.stats"
FA_STATS_DEVICE = "cpu"
FA_STATS_TIMEOUT = 300.0

FA_PATTERNS_KIND = "workflow.failure_analysis.patterns"
FA_PATTERNS_DEVICE = "cpu"
FA_PATTERNS_TIMEOUT = 120.0


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
    import asyncio
    return asyncio.run(coro_factory())


def _finish(
    job_id: str,
    payload: dict[str, Any],
    *,
    extra_files: tuple[bytes, str] | tuple = (),
    status: str = "success",
) -> dict[str, Any]:
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
# Failure Analysis operation executors
# ---------------------------------------------------------------------------


def _get_analyzer():
    from common_lib.modules.workflows.standard.history.recorder import get_recorder
    from common_lib.modules.workflows.standard.history.failure_analysis import (
        FailureAnalyzerTracker,
    )
    recorder = get_recorder()
    return FailureAnalyzerTracker.get_instance(recorder=recorder)


def fa_analyze_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``workflow.failure_analysis.analyze`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    execution_id = params.get("execution_id")
    node_id = params.get("node_id")
    if not execution_id:
        return _finish(job_id, {"error": "Missing execution_id"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    analyzer = _get_analyzer()
    result = _run_async(lambda: analyzer.analyze_failure(execution_id=execution_id, node_id=node_id))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    if result is None:
        return _finish(job_id, {"error": "Execution not found or no failure"}, status="error")

    return _finish(job_id, {
        "status": "success",
        "execution_id": result.execution_id,
        "failure_node_id": result.failure_node_id,
        "error_message": result.error_message,
        "error_type": result.error_type,
        "category": result.category,
        "severity": result.severity,
        "root_cause": result.root_cause,
        "suggestions": result.suggestions,
        "similar_failures": result.similar_failures,
        "analyzed_at": result.analyzed_at.isoformat(),
    })


def fa_batch_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``workflow.failure_analysis.batch`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    execution_ids = params.get("execution_ids", [])
    if not execution_ids:
        return _finish(job_id, {"error": "Missing execution_ids"}, status="error")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    analyzer = _get_analyzer()
    results = []
    total = len(execution_ids)
    for i, execution_id in enumerate(execution_ids):
        if check_cancel():
            return _cancelled_result()
        result = _run_async(lambda: analyzer.analyze_failure(execution_id=execution_id))
        if result:
            results.append({
                "execution_id": result.execution_id,
                "failure_node_id": result.failure_node_id,
                "category": result.category,
                "severity": result.severity,
                "root_cause": result.root_cause,
                "suggestions": result.suggestions[:2],
            })
        report_progress(15.0 + 75.0 * (i + 1) / total)

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {
        "status": "success",
        "analyzed": len(results),
        "total_requested": total,
        "results": results,
    })


def fa_report_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``workflow.failure_analysis.report`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    workflow_id = params.get("workflow_id")
    if not workflow_id:
        return _finish(job_id, {"error": "Missing workflow_id"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    analyzer = _get_analyzer()
    report = _run_async(lambda: analyzer.generate_report(workflow_id=workflow_id))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {
        "status": "success",
        "workflow_id": workflow_id,
        "statistics": report.get("statistics", {}),
        "recent_failures": report.get("recent_failures", []),
        "recommendations": report.get("recommendations", []),
        "report_generated_at": report.get("report_generated_at"),
    })


def fa_stats_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``workflow.failure_analysis.stats`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    workflow_id = params.get("workflow_id")
    if not workflow_id:
        return _finish(job_id, {"error": "Missing workflow_id"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    analyzer = _get_analyzer()
    stats = _run_async(lambda: analyzer.get_failure_statistics(workflow_id=workflow_id))

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {
        "status": "success",
        "workflow_id": workflow_id,
        "total_failures": stats.get("total_failures", 0),
        "by_category": stats.get("by_category", {}),
        "by_severity": stats.get("by_severity", {}),
        "by_pattern": stats.get("by_pattern", {}),
    })


def fa_patterns_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``workflow.failure_analysis.patterns`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    analyzer = _get_analyzer()
    patterns = [{
        "pattern_id": p.pattern_id,
        "category": p.category,
        "severity": p.severity,
        "description": p.description,
        "suggestions": p.suggestions,
    } for p in analyzer.patterns]

    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(job_id, {
        "status": "success",
        "patterns": patterns,
        "count": len(patterns),
    })


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    (FA_ANALYZE_KIND, fa_analyze_executor, FA_ANALYZE_DEVICE, FA_ANALYZE_TIMEOUT),
    (FA_BATCH_KIND, fa_batch_executor, FA_BATCH_DEVICE, FA_BATCH_TIMEOUT),
    (FA_REPORT_KIND, fa_report_executor, FA_REPORT_DEVICE, FA_REPORT_TIMEOUT),
    (FA_STATS_KIND, fa_stats_executor, FA_STATS_DEVICE, FA_STATS_TIMEOUT),
    (FA_PATTERNS_KIND, fa_patterns_executor, FA_PATTERNS_DEVICE, FA_PATTERNS_TIMEOUT),
)


def ensure_workflow_fa_executors_registered() -> bool:
    """Register all workflow failure analysis executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:
        logger.warning("ensure_workflow_fa_executors_registered failed: %s", exc)
        return False


__all__ = [
    "FA_ANALYZE_DEVICE",
    "FA_ANALYZE_KIND",
    "FA_ANALYZE_TIMEOUT",
    "FA_BATCH_DEVICE",
    "FA_BATCH_KIND",
    "FA_BATCH_TIMEOUT",
    "FA_PATTERNS_DEVICE",
    "FA_PATTERNS_KIND",
    "FA_PATTERNS_TIMEOUT",
    "FA_REPORT_DEVICE",
    "FA_REPORT_KIND",
    "FA_REPORT_TIMEOUT",
    "FA_STATS_DEVICE",
    "FA_STATS_KIND",
    "FA_STATS_TIMEOUT",
    "ensure_workflow_fa_executors_registered",
    "fa_analyze_executor",
    "fa_batch_executor",
    "fa_patterns_executor",
    "fa_report_executor",
    "fa_stats_executor",
]