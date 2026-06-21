from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from typing import List, Dict, Any

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.workflows.standard.observability.analytics import (
    build_execution_summary,
    get_stats,
    get_waterfall,
    get_summary,
    get_node_metrics,
)
from common_lib.modules.data_storage.database.repository import NotFoundError
from app.modules.common.types.index import APIResponse

router = APIRouter()


@router.get("/executions", response_model=APIResponse[List[Dict[str, Any]]])
def list_executions(
    skip: int = 0, limit: int = 50, session: Session = Depends(get_session)
):
    from common_lib.modules.workflows.standard.models.observability import (
        WorkflowExecution,
    )

    statement = (
        select(WorkflowExecution)
        .order_by(desc(WorkflowExecution.started_at))
        .offset(skip)
        .limit(limit)
    )
    results = session.exec(statement).all()
    data: List[Dict[str, Any]] = [r.model_dump() for r in results]

    try:
        from common_lib.modules.workflows.combinatorial_service import _execution_store

        for eid, record in _execution_store.items():
            data.append(
                {
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
            )
        data.sort(key=lambda e: e.get("started_at", ""), reverse=True)
    except ImportError:
        pass

    return APIResponse(data=data, message="Retrieved workflow executions")


@router.get(
    "/executions/{trace_id}/waterfall", response_model=APIResponse[List[Dict[str, Any]]]
)
def get_execution_waterfall(trace_id: str, session: Session = Depends(get_session)):
    try:
        events = get_waterfall(session, trace_id)
        return APIResponse(data=events, message="Retrieved execution waterfall data")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/executions/{trace_id}/summary", response_model=APIResponse[Dict[str, Any]]
)
def get_execution_summary(trace_id: str, session: Session = Depends(get_session)):
    try:
        data = get_summary(session, trace_id)
        return APIResponse(
            data=data, message="Retrieved execution summary with intelligence"
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/executions/{trace_id}/node-metrics",
    response_model=APIResponse[List[Dict[str, Any]]],
)
def get_trace_node_metrics(trace_id: str, session: Session = Depends(get_session)):
    try:
        metrics = get_node_metrics(session, trace_id)
        return APIResponse(data=metrics, message="Retrieved node performance metrics")
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
def get_observability_stats(session: Session = Depends(get_session)):
    data = get_stats(session)
    return APIResponse(data=data, message="Retrieved observability statistics")


__all__ = ["router"]
