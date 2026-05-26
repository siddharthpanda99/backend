from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from typing import List, Dict, Any
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.workflows.standard.models.observability import (
    WorkflowExecution,
    WorkflowEvent,
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
        .offset(skip)
        .limit(limit)
    )
    results = session.exec(statement).all()
    data: List[Dict[str, Any]] = [r.model_dump() for r in results]

    # Merge combinatorial executions from in-memory store (non-DB)
    try:
        from app.modules.workflows.routes.combinatorial import _execution_store

        for eid, record in _execution_store.items():
            combo_entry: Dict[str, Any] = {
                "trace_id": f"combo_{eid}",
                "workflow_id": f"combinatorial/{eid}",
                "workflow_name": f"Combinatorial ({record['total']} images)",
                "agent_id": None,
                "status": record["status"],
                "started_at": record["timestamp"],
                "completed_at": record["timestamp"],
                "duration_ms": None,
                "error": None,
                "inputs": record.get("config", {}),
                "outputs": {
                    "summary": record.get("summary", {}),
                    "artifactCount": len(record.get("artifacts", [])),
                },
                "trigger_type": "combinatorial",
                "worker_id": None,
                "system_metadata": {"execution_id": eid, "source": "combinatorial"},
                "state_snapshot": None,
                "usage_metadata": None,
                "total_cost": None,
            }
            data.append(combo_entry)
        data.sort(key=lambda e: e.get("started_at", ""), reverse=True)
    except ImportError:
        pass

    return APIResponse(data=data, message="Retrieved workflow executions")


@router.get(
    "/executions/{trace_id}/waterfall", response_model=APIResponse[List[Dict[str, Any]]]
)
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


@router.get(
    "/executions/{trace_id}/summary", response_model=APIResponse[Dict[str, Any]]
)
def get_execution_summary(trace_id: str, session: Session = Depends(get_session)):
    execution = session.get(WorkflowExecution, trace_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    # Also fetch events for this execution
    events_statement = (
        select(WorkflowEvent)
        .where(WorkflowEvent.trace_id == trace_id)
        .order_by(WorkflowEvent.timestamp)
    )
    events = session.exec(events_statement).all()

    # Calculate Execution Intelligence
    node_stats = {"started": 0, "completed": 0, "failed": 0, "total_nodes": set()}
    node_durations = {}

    for event in events:
        if "state" in event.event_type:
            node_id = event.node_id
            if not node_id:
                continue

            node_stats["total_nodes"].add(node_id)
            if "entered" in event.event_type:
                node_stats["started"] += 1
                node_durations[node_id] = {"start": event.timestamp}
            elif "exited" in event.event_type:
                node_stats["completed"] += 1
                if node_id in node_durations:
                    node_durations[node_id]["end"] = event.timestamp
                    node_durations[node_id]["duration"] = (
                        event.timestamp - node_durations[node_id]["start"]
                    ).total_seconds()
            elif (
                "failed" in event.event_type
            ):  # Note: we don't have state.failed yet, but tool.failed
                node_stats["failed"] += 1

    # Format slow nodes
    slow_nodes = []
    for nid, data in node_durations.items():
        if "duration" in data:
            slow_nodes.append({"id": nid, "duration": data["duration"]})
    slow_nodes.sort(key=lambda x: x["duration"], reverse=True)

    # Calculate Benchmarks
    avg_duration_stmt = select(func.avg(WorkflowExecution.duration_ms)).where(
        WorkflowExecution.workflow_id == execution.workflow_id,
        WorkflowExecution.status == "completed",
    )
    avg_duration = session.exec(avg_duration_stmt).one_or_none()

    # Calculate Token Usage & Cost Intelligence
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    compute = {"steps": 0, "resolution": None, "model_loads": 0}

    for event in events:
        if event.node_output and isinstance(event.node_output, dict):
            # 1. Standard LLM Tokens
            u = event.node_output.get("usage") or {}
            if not u and "metadata" in event.node_output:
                u = event.node_output["metadata"].get("usage") or {}

            usage["prompt_tokens"] += u.get("prompt_tokens", 0)
            usage["completion_tokens"] += u.get("completion_tokens", 0)
            usage["total_tokens"] += u.get("total_tokens", 0)

            # 2. Local Model Compute (Diffusers/SD)
            if "steps" in u:
                compute["steps"] += u["steps"]
            elif "steps" in event.node_output:  # Fallback
                compute["steps"] += event.node_output["steps"]

            if "resolution" in u:
                compute["resolution"] = u["resolution"]
            elif (
                "width" in event.node_output and "height" in event.node_output
            ):  # Fallback
                compute["resolution"] = (
                    f"{event.node_output['width']}x{event.node_output['height']}"
                )

            if "load_time" in event.node_output or "load_time" in u:
                compute["model_loads"] += 1

    # Cost Intelligence
    if usage["total_tokens"] > 0:
        # LLM Pricing: $0.01/1k prompt, $0.03/1k completion
        est_cost = (usage["prompt_tokens"] / 1000 * 0.01) + (
            usage["completion_tokens"] / 1000 * 0.03
        )
    else:
        # Local Compute Proxy: $0.0005 per step or $0.0001 per second of duration
        # Using duration as a more reliable proxy for "electricity/hardware wear" cost
        est_cost = (execution.duration_ms / 1000) * 0.0002

    # Calculate Throughput & Reliability
    duration_sec = execution.duration_ms / 1000 if execution.duration_ms else 1
    throughput = {
        "tokens_per_sec": round(usage["total_tokens"] / duration_sec, 2)
        if usage["total_tokens"] > 0
        else 0,
        "nodes_per_sec": round(len(events) / duration_sec, 2),
        "avg_node_latency_ms": round(execution.duration_ms / len(events), 2)
        if events
        else 0,
    }

    # Historical Reliability (Workflow Success Rate)
    # In a real app, we'd query historical executions for this flow_id
    # Mocking for now as we don't have the full history query yet, but calculating current success
    reliability = {
        "success_rate": 100.0 if execution.status == "completed" else 0.0,
        "retry_count": sum(
            1
            for e in events
            if e.event_metadata and e.event_metadata.get("retry_count")
        ),
        "stability_score": 98.5,  # Mock historical avg
    }

    data = execution.model_dump()
    data["events"] = [e.model_dump() for e in events]
    data["intelligence"] = {
        "node_summary": {
            "total": len(node_stats["total_nodes"]),
            "started": node_stats["started"],
            "completed": node_stats["completed"],
            "failed": node_stats["failed"],
        },
        "top_slow_nodes": slow_nodes[:5],
        "event_count": len(events),
        "benchmarks": {
            "avg_duration_ms": avg_duration,
            "diff_percent": (
                (execution.duration_ms - avg_duration) / avg_duration * 100
            )
            if avg_duration and execution.duration_ms
            else 0,
        },
        "usage": {
            **usage,
            "estimated_cost_usd": round(est_cost, 4),
            "throughput": throughput,
        },
        "compute": compute,
        "reliability": reliability,
    }

    return APIResponse(
        data=data, message="Retrieved execution summary with intelligence"
    )


@router.get(
    "/executions/{trace_id}/node-metrics",
    response_model=APIResponse[List[Dict[str, Any]]],
)
def get_trace_node_metrics(trace_id: str, session: Session = Depends(get_session)):
    """
    Returns historic execution metrics for all nodes associated with this workflow execution.
    """
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
        {
            "node_id": m.node_id,
            "node_name": m.node_name,
            "execution_count": m.execution_count,
            "success_count": m.success_count,
            "failure_count": m.failure_count,
            "avg_duration_ms": m.avg_duration_ms,
            "common_errors": m.common_errors,
            "history": m.history,
        }
        for m in metrics
    ]
    return APIResponse(data=data, message="Retrieved node performance metrics")


from sqlalchemy import func
from datetime import datetime, timedelta


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
def get_observability_stats(session: Session = Depends(get_session)):
    """
    Returns aggregated statistics for the observability dashboard.
    """
    # 1. Overall status counts
    status_statement = select(
        WorkflowExecution.status, func.count(WorkflowExecution.trace_id)
    ).group_by(WorkflowExecution.status)
    status_results = session.exec(status_statement).all()
    status_counts = {status: count for status, count in status_results}

    # 2. Recent execution history (last 24 hours in hourly buckets)
    now = datetime.utcnow()
    one_day_ago = now - timedelta(days=1)

    history_statement = select(
        WorkflowExecution.started_at, WorkflowExecution.status
    ).where(WorkflowExecution.started_at >= one_day_ago)
    recent_runs = session.exec(history_statement).all()

    # Initialize buckets for the last 24 hours
    # Each bucket: { hour: string, success: int, failed: int, total: int }
    buckets = []
    for i in range(24):
        bucket_time = now - timedelta(hours=23 - i)
        buckets.append(
            {
                "hour": bucket_time.strftime("%H:00"),
                "success": 0,
                "failed": 0,
                "total": 0,
            }
        )

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
            "summary": {
                "total": sum(status_counts.values()),
                "success": status_counts.get("completed", 0),
                "failed": status_counts.get("failed", 0),
                "running": status_counts.get("running", 0),
            },
            "chart_data": buckets,
        },
        message="Retrieved observability statistics",
    )


__all__ = ["router"]
