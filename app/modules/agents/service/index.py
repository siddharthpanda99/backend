from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from app.modules.agents.schemas.index import AgentCreate, AgentUpdate
from app.core.common_lib_integration import common_memory, sync_entity_to_fs

class AgentService:
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        agents = common_memory.list_agent_definitions()
        return agents[skip : skip + limit]

    def get_by_id(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return common_memory.get_agent_definition(agent_id)

    def create(self, agent_in: AgentCreate) -> Dict[str, Any]:
        data = agent_in.model_dump()
        agent_id = data.get("id") or data.get("name")
        if not agent_id:
            raise HTTPException(status_code=400, detail="Agent ID or Name is required")
            
        common_memory.save_agent_definition(
            name=agent_id,
            identity=data.get("identity", {}),
            definition=data.get("definition", {}),
            version=data.get("version", "1.0.0"),
            description=data.get("description"),
            agent_type=data.get("agent_type")
        )
        sync_entity_to_fs("agent", agent_id)
        return self.get_by_id(agent_id)

    def update(self, agent_id: str, agent_in: AgentUpdate) -> Dict[str, Any]:
        existing = self.get_by_id(agent_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Agent not found")
            
        update_data = agent_in.model_dump(exclude_unset=True)
        
        # Merge properties into existing
        identity = update_data.get("identity", existing.get("identity", {}))
        definition = update_data.get("definition", existing.get("definition", {}))
        version = update_data.get("version", existing.get("version", "1.0.0"))
        description = update_data.get("description", existing.get("description"))
        agent_type = update_data.get("agent_type", existing.get("agent_type"))
        
        common_memory.save_agent_definition(
            name=agent_id,
            identity=identity,
            definition=definition,
            version=version,
            description=description,
            agent_type=agent_type
        )
        sync_entity_to_fs("agent", agent_id)
        return self.get_by_id(agent_id)

    def delete(self, agent_id: str) -> bool:
        if not self.get_by_id(agent_id):
            raise HTTPException(status_code=404, detail="Agent not found")
        common_memory.delete_agent_definition(agent_id)
        return True

agent_service = AgentService()
