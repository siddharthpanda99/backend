from typing import List, Optional
from sqlmodel import Session, select
from fastapi import HTTPException
from common_lib.modules.core_infrastructure.tool.models import ToolDefinitionRecord
from app.modules.tools.schemas.index import ToolCreate, ToolUpdate

class ToolService:
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[ToolDefinitionRecord]:
        statement = select(ToolDefinitionRecord).offset(skip).limit(limit)
        return session.exec(statement).all()

    def get_by_id(self, session: Session, tool_id: str) -> Optional[ToolDefinitionRecord]:
        return session.get(ToolDefinitionRecord, tool_id)

    def create(self, session: Session, tool_in: ToolCreate) -> ToolDefinitionRecord:
        db_obj = ToolDefinitionRecord(**tool_in.model_dump())
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def update(self, session: Session, tool_id: str, tool_in: ToolUpdate) -> ToolDefinitionRecord:
        db_obj = self.get_by_id(session, tool_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Tool not found")
            
        update_data = tool_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
            
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def delete(self, session: Session, tool_id: str) -> bool:
        db_obj = self.get_by_id(session, tool_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Tool not found")
        session.delete(db_obj)
        session.commit()
        return True

tool_service = ToolService()
