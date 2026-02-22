from typing import List, Optional
from sqlmodel import Session, select
from fastapi import HTTPException
from common_lib.modules.orchestration.memory.models import MemoryDefinitionRecord
from app.modules.memories.schemas.index import MemoryCreate, MemoryUpdate

class MemoryService:
    def get_all(self, session: Session, skip: int = 0, limit: int = 100) -> List[MemoryDefinitionRecord]:
        statement = select(MemoryDefinitionRecord).offset(skip).limit(limit)
        return session.exec(statement).all()

    def get_by_id(self, session: Session, memory_id: str) -> Optional[MemoryDefinitionRecord]:
        return session.get(MemoryDefinitionRecord, memory_id)

    def create(self, session: Session, memory_in: MemoryCreate) -> MemoryDefinitionRecord:
        db_obj = MemoryDefinitionRecord(**memory_in.model_dump())
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def update(self, session: Session, memory_id: str, memory_in: MemoryUpdate) -> MemoryDefinitionRecord:
        db_obj = self.get_by_id(session, memory_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Memory not found")
            
        update_data = memory_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_obj, key, value)
            
        session.add(db_obj)
        session.commit()
        session.refresh(db_obj)
        return db_obj

    def delete(self, session: Session, memory_id: str) -> bool:
        db_obj = self.get_by_id(session, memory_id)
        if not db_obj:
            raise HTTPException(status_code=404, detail="Memory not found")
        session.delete(db_obj)
        session.commit()
        return True

memory_service = MemoryService()
