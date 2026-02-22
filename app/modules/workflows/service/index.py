from typing import List, Optional
from sqlmodel import Session, select
from fastapi import HTTPException
from common_lib.modules.orchestration.workflow.models import WorkflowDefinitionRecord
from app.modules.workflows.schemas.index import WorkflowCreate, WorkflowUpdate

class WorkflowService:
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[WorkflowDefinitionRecord]:
        statement = select(WorkflowDefinitionRecord).offset(skip).limit(limit)
        return session.exec(statement).all()

    def get_by_id(self, session: Session, workflow_id: str) -> Optional[WorkflowDefinitionRecord]:
        return session.get(WorkflowDefinitionRecord, workflow_id)

    def create(self, session: Session, workflow_in: WorkflowCreate) -> WorkflowDefinitionRecord:
        db_obj = WorkflowDefinitionRecord(**workflow_in.model_dump())
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def update(self, session: Session, workflow_id: str, workflow_in: WorkflowUpdate) -> WorkflowDefinitionRecord:
        db_obj = self.get_by_id(session, workflow_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
        update_data = workflow_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
            
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def delete(self, session: Session, workflow_id: str) -> bool:
        db_obj = self.get_by_id(session, workflow_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Workflow not found")
        session.delete(db_obj)
        session.commit()
        return True

workflow_service = WorkflowService()
