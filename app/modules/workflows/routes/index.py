from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.modules.common.types.index import APIResponse
from app.modules.database.service.connection import get_session
from app.modules.workflows.service.index import workflow_service
from app.modules.workflows.schemas.index import WorkflowRead, WorkflowCreate, WorkflowUpdate

router = APIRouter()

@router.get("/", response_model=APIResponse[List[WorkflowRead]])
def list_workflows(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    items = workflow_service.get_all(db, skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of workflows")

@router.post("/", response_model=APIResponse[WorkflowRead])
def create_workflow(workflow_in: WorkflowCreate, db: Session = Depends(get_session)):
    item = workflow_service.create(db, workflow_in)
    return APIResponse(data=item, message="Workflow created successfully")

@router.get("/{id}", response_model=APIResponse[WorkflowRead])
def get_workflow(id: str, db: Session = Depends(get_session)):
    item = workflow_service.get_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return APIResponse(data=item, message="Workflow retrieved successfully")

@router.put("/{id}", response_model=APIResponse[WorkflowRead])
def update_workflow(id: str, workflow_in: WorkflowUpdate, db: Session = Depends(get_session)):
    item = workflow_service.update(db, id, workflow_in)
    return APIResponse(data=item, message="Workflow updated successfully")

@router.delete("/{id}", response_model=APIResponse[dict])
def delete_workflow(id: str, db: Session = Depends(get_session)):
    workflow_service.delete(db, id)
    return APIResponse(data={"success": True}, message="Workflow deleted successfully")
