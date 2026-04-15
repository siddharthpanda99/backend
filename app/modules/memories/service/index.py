from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from app.modules.memories.schemas.index import MemoryCreate, MemoryUpdate
from app.core.common_lib_integration import common_memory, sync_entity_to_fs

class MemoryService:
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        # common_memory.list_memory_definitions() if available, else emulate via fallback
        try:
            memories = common_memory.list_memory_definitions()
            return memories[skip : skip + limit]
        except AttributeError:
            from common_lib.modules.orchestration.context.memory.models import MemoryDefinitionRecord
            from sqlmodel import select
            with common_memory._get_session() as session:
                statement = select(MemoryDefinitionRecord).offset(skip).limit(limit)
                records = session.exec(statement).all()
                return [r.dict() if hasattr(r, 'dict') else {c.name: getattr(r, c.name) for c in r.__table__.columns} for r in records]

    def get_by_id(self, memory_id: str) -> Optional[Dict[str, Any]]:
        try:
            return common_memory.get_memory_definition(memory_id)
        except AttributeError:
            from common_lib.modules.orchestration.context.memory.models import MemoryDefinitionRecord
            with common_memory._get_session() as session:
                record = session.get(MemoryDefinitionRecord, memory_id)
                return record.dict() if record and hasattr(record, 'dict') else ({c.name: getattr(record, c.name) for c in record.__table__.columns} if record else None)

    def create(self, memory_in: MemoryCreate) -> Dict[str, Any]:
        data = memory_in.model_dump()
        memory_id = data.get("id") or data.get("name")
        if not memory_id:
            raise HTTPException(status_code=400, detail="Memory ID or Name is required")
            
        try:
            common_memory.save_memory_definition(
                name=memory_id,
                definition=data.get("definition", {}),
                version=data.get("version", "1.0.0")
            )
        except AttributeError:
            from common_lib.modules.orchestration.context.memory.models import MemoryDefinitionRecord
            with common_memory._get_session() as session:
                record = MemoryDefinitionRecord(**data)
                session.add(record)
                session.commit()
                
        sync_entity_to_fs("memory", memory_id)
        return self.get_by_id(memory_id)

    def update(self, memory_id: str, memory_in: MemoryUpdate) -> Dict[str, Any]:
        existing = self.get_by_id(memory_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Memory not found")
            
        update_data = memory_in.model_dump(exclude_unset=True)
        definition = update_data.get("definition", existing.get("definition", {}))
        version = update_data.get("version", existing.get("version", "1.0.0"))
        
        try:
            common_memory.save_memory_definition(
                name=memory_id,
                definition=definition,
                version=version
            )
        except AttributeError:
            from common_lib.modules.orchestration.context.memory.models import MemoryDefinitionRecord
            with common_memory._get_session() as session:
                record = session.get(MemoryDefinitionRecord, memory_id)
                if record:
                    for k, v in update_data.items():
                        setattr(record, k, v)
                    session.commit()
                
        sync_entity_to_fs("memory", memory_id)
        return self.get_by_id(memory_id)

    def delete(self, memory_id: str) -> bool:
        if not self.get_by_id(memory_id):
            raise HTTPException(status_code=404, detail="Memory not found")
            
        try:
            common_memory.delete_memory_definition(memory_id)
        except AttributeError:
            from common_lib.modules.orchestration.context.memory.models import MemoryDefinitionRecord
            from sqlalchemy import delete
            with common_memory._get_session() as session:
                stmt = delete(MemoryDefinitionRecord).where(MemoryDefinitionRecord.id == memory_id)
                session.execute(stmt)
                session.commit()
                
        return True

memory_service = MemoryService()
