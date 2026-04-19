from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select, desc
from typing import List, Dict, Any
from app.modules.database.service.connection import get_session
from app.modules.workflows.models.observability import WorkflowExecution, WorkflowEvent
from app.modules.common.types.index import APIResponse

router = APIRouter()

@router.get("/executions", response_model=APIResponse[List[Dict[str, Any]]])
def list_executions(
    skip: int = 0, 
    limit: int = 50, 
    session: Session = Depends(get_session)
):
    """List recent workflow executions from the observability schema."""
    statement = select(WorkflowExecution).order_by(desc(WorkflowExecution.started_at)).offset(skip).limit(limit)
    results = session.exec(statement).all()
    
    # model_dump is standard for SQLModel/Pydantic v2
    data = [r.model_dump() for r in results]
    return APIResponse(data=data, message="Retrieved workflow executions")

@router.get("/executions/{trace_id}/waterfall", response_model=APIResponse[List[Dict[str, Any]]])
def get_execution_waterfall(
    trace_id: str, 
    session: Session = Depends(get_session)
):
    """
    Retrieve granular events for a specific trace.
    Returns events ordered by timestamp to facilitate Jaeger-style waterfall rendering.
    """
    statement = select(WorkflowEvent).where(WorkflowEvent.trace_id == trace_id).order_by(WorkflowEvent.timestamp)
    results = session.exec(statement).all()
    
    if not results and not session.get(WorkflowExecution, trace_id):
        raise HTTPException(status_code=404, detail="Execution trace not found")
        
    data = [r.model_dump() for r in results]
    return APIResponse(data=data, message="Retrieved execution waterfall data")

@router.get("/executions/{trace_id}/summary", response_model=APIResponse[Dict[str, Any]])
def get_execution_summary(
    trace_id: str, 
    session: Session = Depends(get_session)
):
    """Get high-level summary and status of a specific execution."""
    execution = session.get(WorkflowExecution, trace_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
        
    return APIResponse(data=execution.model_dump(), message="Retrieved execution summary")
