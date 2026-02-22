from typing import List, Optional, Dict, Any
from fastapi import HTTPException
from app.modules.workflows.schemas.index import WorkflowCreate, WorkflowUpdate
from app.core.common_lib_integration import common_memory, sync_entity_to_fs

class WorkflowService:
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        workflows = common_memory.list_workflow_definitions()
        return workflows[skip : skip + limit]

    def get_by_id(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        return common_memory.get_workflow_definition(workflow_id)

    def create(self, workflow_in: WorkflowCreate) -> Dict[str, Any]:
        data = workflow_in.model_dump()
        workflow_id = data.get("id") or data.get("name")
        if not workflow_id:
            raise HTTPException(status_code=400, detail="Workflow ID or Name is required")
            
        common_memory.save_workflow_definition(
            name=workflow_id,
            definition=data.get("definition", {}),
            version=data.get("version", "1.0.0")
        )
        sync_entity_to_fs("workflow", workflow_id)
        return self.get_by_id(workflow_id)

    def update(self, workflow_id: str, workflow_in: WorkflowUpdate) -> Dict[str, Any]:
        existing = self.get_by_id(workflow_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Workflow not found")
            
        update_data = workflow_in.model_dump(exclude_unset=True)
        definition = update_data.get("definition", existing.get("definition", {}))
        version = update_data.get("version", existing.get("version", "1.0.0"))
        
        common_memory.save_workflow_definition(
            name=workflow_id,
            definition=definition,
            version=version
        )
        sync_entity_to_fs("workflow", workflow_id)
        return self.get_by_id(workflow_id)

    def delete(self, workflow_id: str) -> bool:
        if not self.get_by_id(workflow_id):
            raise HTTPException(status_code=404, detail="Workflow not found")
        common_memory.delete_workflow_definition(workflow_id)
        return True

workflow_service = WorkflowService()
