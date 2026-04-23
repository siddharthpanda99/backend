from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from typing import List, Dict, Any
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.workflows.standard.models.observability import WorkflowExecution
from common_lib.modules.workflows.standard.observability.events import WorkflowEvent
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
    data = [r.model_dump() for r in results]
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
    return APIResponse(
        data=execution.model_dump(), message="Retrieved execution summary"
    )


__all__ = ["router"]
