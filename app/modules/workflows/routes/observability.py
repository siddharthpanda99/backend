from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime, timedelta

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.workflows.standard.models.observability import (
    WorkflowExecution,
    WorkflowEvent,
)
from common_lib.modules.workflows.standard.observability.analytics import (
    build_execution_summary,
)
from app.modules.common.types.index import APIResponse

router = APIRouter()


@router.get("/executions", response_model=APIResponse[List[Dict[str, Any]]])
def list_executions(
    skip: int = 0, limit: int = 50, session: Session = Depends(get_session)
):
    statement = (
        select(WorkflowExecution)
        .order_by(desc(WorkflowExecution.started_at))
        .offset(skip).limit(limit)
    )
    results = session.exec(statement).all()
    data: List[Dict[str, Any]] = [r.model_dump() for r in results]

    # Merge combinatorial executions from in-memory store
    try:
        from app.modules.workflows.routes.combinatorial import _execution_store
        for eid, record in _execution_store.items():
            data.append({
                "trace_id": f"combo_{eid}",
                "workflow_id": f"combinatorial/{eid}",
                "workflow_name": f"Combinatorial ({record['total']} images)",
                "agent_id": None,
                "status": record["status"],
                "started_at": record["timestamp"],
                "completed_at": record["timestamp"],
                "duration_ms": None, "error": None,
                "inputs": record.get("config", {}),
                "outputs": {"summary": record.get("summary", {}),
                            "artifactCount": len(record.get("artifacts", []))},
                "trigger_type": "combinatorial", "worker_id": None,
                "system_metadata": {"execution_id": eid, "source": "combinatorial"},
                "state_snapshot": None, "usage_metadata": None, "total_cost": None,
            })
        data.sort(key=lambda e: e.get("started_at", ""), reverse=True)
    except ImportError:
        pass

    return APIResponse(data=data, message="Retrieved workflow executions")


@router.get("/executions/{trace_id}/waterfall", response_model=APIResponse[List[Dict[str, Any]]])
def get_execution_waterfall(trace_id: str, session: Session = Depends(get_session)):
    statement = (
        select(WorkflowEvent)
        .where(WorkflowEvent.trace_id == trace_id)
        .order_by(WorkflowEvent.timestamp)
    )
    results = session.exec(statement).all()
    if not results and not session.get(WorkflowExecution, trace_id):
        raise HTTPException(status_code=404, detail="Execution trace not found")
    data = [r.model_dump() for r in results]
    return APIResponse(data=data, message="Retrieved execution waterfall data")


@router.get("/executions/{trace_id}/summary", response_model=APIResponse[Dict[str, Any]])
def get_execution_summary(trace_id: str, session: Session = Depends(get_session)):
    execution = session.get(WorkflowExecution, trace_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    events_stmt = (
        select(WorkflowEvent)
        .where(WorkflowEvent.trace_id == trace_id)
        .order_by(WorkflowEvent.timestamp)
    )
    events = session.exec(events_stmt).all()

    # Calculate avg duration for benchmarking
    avg_duration_stmt = select(func.avg(WorkflowExecution.duration_ms)).where(
        WorkflowExecution.workflow_id == execution.workflow_id,
        WorkflowExecution.status == "completed",
    )
    avg_duration = session.exec(avg_duration_stmt).one_or_none()

    data = build_execution_summary(
        execution=execution.model_dump(),
        events=[e.model_dump() for e in events],
        avg_duration=avg_duration,
    )

    return APIResponse(data=data, message="Retrieved execution summary with intelligence")


@router.get("/executions/{trace_id}/node-metrics", response_model=APIResponse[List[Dict[str, Any]]])
def get_trace_node_metrics(trace_id: str, session: Session = Depends(get_session)):
    execution = session.get(WorkflowExecution, trace_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    from common_lib.modules.workflows.standard.history.analytics import (
        ExecutionAnalyticsTracker,
    )
    from common_lib.modules.workflows.standard.history.recorder import get_recorder

    recorder = get_recorder()
    analytics = ExecutionAnalyticsTracker.get_instance(recorder=recorder)
    metrics = analytics.get_node_metrics(workflow_id=execution.workflow_id)

    data = [
        {"node_id": m.node_id, "node_name": m.node_name, "execution_count": m.execution_count,
         "success_count": m.success_count, "failure_count": m.failure_count,
         "avg_duration_ms": m.avg_duration_ms, "common_errors": m.common_errors, "history": m.history}
        for m in metrics
    ]
    return APIResponse(data=data, message="Retrieved node performance metrics")


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
def get_observability_stats(session: Session = Depends(get_session)):
    now = datetime.utcnow()
    one_day_ago = now - timedelta(days=1)

    # Overall status counts
    status_stmt = select(WorkflowExecution.status, func.count(WorkflowExecution.trace_id)).group_by(WorkflowExecution.status)
    status_results = session.exec(status_stmt).all()
    status_counts = {status: count for status, count in status_results}

    # Recent execution history (last 24 hours in hourly buckets)
    history_stmt = select(WorkflowExecution.started_at, WorkflowExecution.status).where(
        WorkflowExecution.started_at >= one_day_ago
    )
    recent_runs = session.exec(history_stmt).all()

    buckets = []
    for i in range(24):
        bucket_time = now - timedelta(hours=23 - i)
        buckets.append({"hour": bucket_time.strftime("%H:00"), "success": 0, "failed": 0, "total": 0})

    for started_at, status in recent_runs:
        hour_diff = int((now - started_at).total_seconds() / 3600)
        if 0 <= hour_diff < 24:
            idx = 23 - hour_diff
            buckets[idx]["total"] += 1
            if status == "completed":
                buckets[idx]["success"] += 1
            elif status == "failed":
                buckets[idx]["failed"] += 1

    return APIResponse(
        data={
            "summary": {"total": sum(status_counts.values()),
                        "success": status_counts.get("completed", 0),
                        "failed": status_counts.get("failed", 0),
                        "running": status_counts.get("running", 0)},
            "chart_data": buckets,
        },
        message="Retrieved observability statistics",
    )


__all__ = ["router"]
