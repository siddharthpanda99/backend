"""Failure Analysis API routes.

Exposes the FailureAnalyzer from common_lib as REST endpoints.
Integrates with the integration module for event routing and error handling.

Long-running batch analysis and report generation are jobs-backed by default; pass ``sync=true`` for inline.
"""

import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from common_lib.modules.integration import (
    get_event_router,
    get_error_handler,
    ErrorSeverity,
)
from common_lib.modules.integration.core.context_propagation import create_trace_context
from common_lib.modules.workflows.standard.history.failure_analysis import (
    FailureAnalyzer,
    FailureAnalyzerTracker,
)
from common_lib.modules.workflows.standard.history.recorder import (
    WorkflowRecorder,
    get_recorder,
)
from app.modules.common.types.index import APIResponse

from app.modules.workflows.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(capture_job_actor)])


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_fa_jobs():
    return owned_job_service()


def _fa_job_payload(record: Any) -> Dict[str, Any]:
    refs: List[str] = []
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


def _fa_job_status(job_id: str) -> Dict[str, Any]:
    from fastapi import HTTPException as _HTTPException
    import json

    svc = _ensure_fa_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _fa_job_payload(record)
    meta: Dict[str, Any] = {}
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


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------


@router.get("/failure-analysis/jobs")
async def list_fa_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    records = _ensure_fa_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="workflow.failure_analysis.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_fa_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/failure-analysis/jobs/{job_id}")
async def get_fa_job(job_id: str) -> Dict[str, Any]:
    return _fa_job_status(job_id)


@router.post("/failure-analysis/jobs/{job_id}/cancel")
async def cancel_fa_job(job_id: str) -> Dict[str, Any]:
    record = _ensure_fa_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_fa_job_payload(record)}


@router.get("/failure-analysis/jobs/{job_id}/events")
async def fa_job_events(job_id: str):
    from fastapi.responses import StreamingResponse
    import json
    import asyncio
    import time as _time

    async def event_generator():
        deadline: float = _time.time() + 3600.0
        last_progress: float = -1.0
        yield f"event: started\ndata: {json.dumps({'job_id': job_id, 'status': 'queued'})}\n\n"
        while True:
            record: JobRecord | None = get_job_service().get(job_id)
            if record is None:
                yield f"event: failed\ndata: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
                return
            if record.progress != last_progress:
                last_progress = record.progress
                yield f"event: progress\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'progress': record.progress})}\n\n"
            if record.status in ("completed", "failed", "cancelled"):
                if record.status == "completed":
                    meta: Dict[str, Any] = {}
                    for ref in _fa_job_payload(record)["result_refs"]:
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
                    yield f"event: completed\ndata: {json.dumps({'job_id': job_id, 'status': 'completed', 'meta': meta})}\n\n"
                else:
                    yield f"event: {record.status}\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'error': record.error or record.status})}\n\n"
                return
            if _time.time() > deadline:
                yield f"event: timeout\ndata: {json.dumps({'job_id': job_id, 'error': 'progress stream timed out'})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class AnalyzeRequest(BaseModel):
    execution_id: str
    node_id: Optional[str] = None


class AnalyzeBatchRequest(BaseModel):
    execution_ids: list[str]


def _get_analyzer() -> FailureAnalyzer:
    recorder = get_recorder()
    return FailureAnalyzerTracker.get_instance(recorder=recorder)


@router.post("/failure-analysis/analyze")
async def analyze_failure(request: AnalyzeRequest, sync: bool = False):
    """Analyze a workflow failure and return root cause + suggestions.

    Jobs-backed by default; pass ``sync=true`` for inline.
    """
    if sync:
        trace_ctx = create_trace_context(source="api", operation="failure_analysis.analyze")
        event_router = get_event_router()
        error_handler = get_error_handler()

        try:
            analyzer = _get_analyzer()
            result = analyzer.analyze_failure(
                execution_id=request.execution_id,
                node_id=request.node_id,
            )

            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Execution {request.execution_id} not found or no failure recorded",
                )

            await event_router.fire_event(
                event_type="failure_analysis.analyze",
                data={"execution_id": request.execution_id, "category": result.category},
                channel="workflow",
                source="api",
                trace_id=trace_ctx.trace_id,
            )

            return APIResponse(
                data={
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
                },
                message="Failure analysis completed",
            )
        except HTTPException:
            raise
        except Exception as e:
            error_handler.handle_error(
                error=e,
                module="failure_analysis",
                operation="analyze",
                trace_id=trace_ctx.trace_id,
                severity=ErrorSeverity.ERROR,
            )
            raise HTTPException(status_code=500, detail=f"Analysis failed: {e}")

    from app.modules.workflows.runtime.job_executors import FA_ANALYZE_KIND

    record = _ensure_fa_jobs().submit(
        FA_ANALYZE_KIND,
        params={"execution_id": request.execution_id, "node_id": request.node_id},
    )
    return {"status": "queued", **_fa_job_payload(record)}


@router.post("/failure-analysis/batch")
async def analyze_failures_batch(request: AnalyzeBatchRequest, sync: bool = False):
    """Analyze multiple workflow failures in batch.

    Jobs-backed by default; pass ``sync=true`` for inline.
    """
    if sync:
        trace_ctx = create_trace_context(source="api", operation="failure_analysis.batch")
        event_router = get_event_router()

        try:
            analyzer = _get_analyzer()
            results = []
            for execution_id in request.execution_ids:
                result = analyzer.analyze_failure(execution_id=execution_id)
                if result:
                    results.append(
                        {
                            "execution_id": result.execution_id,
                            "failure_node_id": result.failure_node_id,
                            "category": result.category,
                            "severity": result.severity,
                            "root_cause": result.root_cause,
                            "suggestions": result.suggestions[:2],
                        }
                    )

            await event_router.fire_event(
                event_type="failure_analysis.batch",
                data={"count": len(results), "total": len(request.execution_ids)},
                channel="workflow",
                source="api",
                trace_id=trace_ctx.trace_id,
            )

            return APIResponse(
                data={
                    "analyzed": len(results),
                    "total_requested": len(request.execution_ids),
                    "results": results,
                },
                message="Batch analysis completed",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Batch analysis failed: {e}")

    from app.modules.workflows.runtime.job_executors import FA_BATCH_KIND

    record = _ensure_fa_jobs().submit(
        FA_BATCH_KIND,
        params={"execution_ids": request.execution_ids},
    )
    return {"status": "queued", **_fa_job_payload(record)}


@router.get("/failure-analysis/report/{workflow_id}")
async def get_failure_report(workflow_id: str, sync: bool = False):
    """Generate comprehensive failure analysis report for a workflow.

    Jobs-backed by default; pass ``sync=true`` for inline.
    """
    if sync:
        trace_ctx = create_trace_context(source="api", operation="failure_analysis.report")

        try:
            analyzer = _get_analyzer()
            report = analyzer.generate_report(workflow_id=workflow_id)

            return APIResponse(
                data={
                    "workflow_id": workflow_id,
                    "statistics": report.get("statistics", {}),
                    "recent_failures": report.get("recent_failures", []),
                    "recommendations": report.get("recommendations", []),
                    "report_generated_at": report.get(
                        "report_generated_at",
                        __import__("datetime").datetime.now().isoformat(),
                    ),
                },
                message="Failure report generated",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")

    from app.modules.workflows.runtime.job_executors import FA_REPORT_KIND

    record = _ensure_fa_jobs().submit(
        FA_REPORT_KIND,
        params={"workflow_id": workflow_id},
    )
    return {"status": "queued", **_fa_job_payload(record)}


@router.get("/failure-analysis/stats/{workflow_id}")
async def get_failure_statistics(workflow_id: str, sync: bool = False):
    """Get failure statistics for a workflow.

    Jobs-backed by default; pass ``sync=true`` for inline.
    """
    if sync:
        try:
            analyzer = _get_analyzer()
            stats = analyzer.get_failure_statistics(workflow_id=workflow_id)

            return APIResponse(
                data={
                    "workflow_id": workflow_id,
                    "total_failures": stats.get("total_failures", 0),
                    "by_category": stats.get("by_category", {}),
                    "by_severity": stats.get("by_severity", {}),
                    "by_pattern": stats.get("by_pattern", {}),
                },
                message="Failure statistics retrieved",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {e}")

    from app.modules.workflows.runtime.job_executors import FA_STATS_KIND

    record = _ensure_fa_jobs().submit(
        FA_STATS_KIND,
        params={"workflow_id": workflow_id},
    )
    return {"status": "queued", **_fa_job_payload(record)}


@router.get("/failure-analysis/patterns")
async def list_error_patterns():
    """List all known error patterns used for failure analysis."""
    try:
        analyzer = _get_analyzer()
        patterns = [
            {
                "pattern_id": p.pattern_id,
                "category": p.category,
                "severity": p.severity,
                "description": p.description,
                "suggestions": p.suggestions,
            }
            for p in analyzer.patterns
        ]
        return APIResponse(
            data={"patterns": patterns, "count": len(patterns)},
            message="Error patterns retrieved",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list patterns: {e}")


__all__ = ["router"]
