from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from app.modules.tools.schemas.index import ToolCreate, ToolUpdate
from app.core.common_lib_integration import common_memory, sync_entity_to_fs

class ToolService:
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        tools = common_memory.list_tool_definitions()
        return tools[skip : skip + limit]

    def get_by_id(self, tool_id: str) -> Optional[Dict[str, Any]]:
        return common_memory.get_tool_definition(tool_id)

    def create(self, tool_in: ToolCreate) -> Dict[str, Any]:
        data = tool_in.model_dump()
        tool_id = data.get("id") or data.get("name")
        if not tool_id:
            raise HTTPException(status_code=400, detail="Tool ID or Name is required")
            
        common_memory.save_tool_definition(
            definition=data
        )
        sync_entity_to_fs("tool", tool_id)
        return self.get_by_id(tool_id)

    def update(self, tool_id: str, tool_in: ToolUpdate) -> Dict[str, Any]:
        existing = self.get_by_id(tool_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Tool not found")
            
        update_data = tool_in.model_dump(exclude_unset=True)
        # Assuming the tool schema is largely dynamic/embedded into definition
        merged = {**existing.get("definition", existing), **update_data}
        merged["id"] = tool_id
        
        common_memory.save_tool_definition(
            definition=merged
        )
        sync_entity_to_fs("tool", tool_id)
        return self.get_by_id(tool_id)

    def delete(self, tool_id: str) -> bool:
        if not self.get_by_id(tool_id):
            raise HTTPException(status_code=404, detail="Tool not found")
        # common_memory does not natively have delete_tool_definition easily exposed
        # I will emulate it for the unified interface here if not perfectly mirroring agent
        try:
            from common_lib.modules.core_infrastructure.tool.models import ToolDefinitionRecord
            from sqlalchemy import delete
            with common_memory._get_session() as session:
                stmt = delete(ToolDefinitionRecord).where(ToolDefinitionRecord.id == tool_id)
                session.execute(stmt)
                session.commit()
        except AttributeError:
            # Fallback if the underlying method exists
            if hasattr(common_memory, 'delete_tool_definition'):
                common_memory.delete_tool_definition(tool_id)
            else:
                pass
        return True

tool_service = ToolService()
