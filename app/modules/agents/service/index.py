from typing import List, Optional
from sqlmodel import Session, select
from fastapi import HTTPException
from common_lib.modules.orchestration.agent.models import AgentDefinitionRecord
from app.modules.agents.schemas.index import AgentCreate, AgentUpdate

class AgentService:
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[AgentDefinitionRecord]:
        statement = select(AgentDefinitionRecord).offset(skip).limit(limit)
        return session.exec(statement).all()

    def get_by_id(self, session: Session, agent_id: str) -> Optional[AgentDefinitionRecord]:
        return session.get(AgentDefinitionRecord, agent_id)

    def create(self, session: Session, agent_in: AgentCreate) -> AgentDefinitionRecord:
        db_obj = AgentDefinitionRecord(**agent_in.model_dump())
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def update(self, session: Session, agent_id: str, agent_in: AgentUpdate) -> AgentDefinitionRecord:
        db_obj = self.get_by_id(session, agent_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        update_data = agent_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
            
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def delete(self, session: Session, agent_id: str) -> bool:
        db_obj = self.get_by_id(session, agent_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Agent not found")
        session.delete(db_obj)
        session.commit()
        return True

agent_service = AgentService()
