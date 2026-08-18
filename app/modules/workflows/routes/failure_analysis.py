"""Failure Analysis API routes.

Exposes the FailureAnalyzer from common_lib as REST endpoints.
Integrates with the integration module for event routing and error handling.
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

logger = logging.getLogger(__name__)

router = APIRouter()


class AnalyzeRequest(BaseModel):
    execution_id: str
    node_id: Optional[str] = None


class AnalyzeBatchRequest(BaseModel):
    execution_ids: list[str]


def _get_analyzer() -> FailureAnalyzer:
    recorder = get_recorder()
    return FailureAnalyzerTracker.get_instance(recorder=recorder)


@router.post("/failure-analysis/analyze")
async def analyze_failure(request: AnalyzeRequest):
    """Analyze a workflow failure and return root cause + suggestions."""
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


@router.post("/failure-analysis/batch")
async def analyze_failures_batch(request: AnalyzeBatchRequest):
    """Analyze multiple workflow failures in batch."""
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


@router.get("/failure-analysis/report/{workflow_id}")
async def get_failure_report(workflow_id: str):
    """Generate comprehensive failure analysis report for a workflow."""
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


@router.get("/failure-analysis/stats/{workflow_id}")
async def get_failure_statistics(workflow_id: str):
    """Get failure statistics for a workflow."""
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
