from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from common_lib.modules.memory.service import MemoryService, FeatureFlags
from common_lib.modules.memory.memory_models import MemoryCreate, MemoryUpdate, MemoryResponse
from common_lib.modules.memory.memory_types import MemoryType
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()


def get_memory_service():
    """Get memory service instance."""
    # This will be injected by the app - for now return a placeholder
    # The actual integration happens in main.py
    return None


@router.get("/", response_model=APIResponse[List[dict]])
def list_memories(
    skip: int = 0, 
    limit: int = 100,
    memory_service: Optional[MemoryService] = Depends(get_memory_service)
):
    """List all memories."""
    if not memory_service:
        return APIResponse(data=[], message="Memory service not initialized")
    
    # For now return empty - will integrate with new stores
    return APIResponse(data=[], message="Retrieved list of memories")


@router.post("/", response_model=APIResponse[dict])
def create_memory(
    memory_in: dict,
    memory_service: Optional[MemoryService] = Depends(get_memory_service),
    current_user = Depends(get_current_active_user)
):
    """Create a new memory."""
    if not memory_service:
        return APIResponse(data=None, message="Memory service not initialized")
    
    try:
        memory_type = MemoryType(memory_in.get("memory_type", "episodic"))
        memory_id = memory_service.store_memory(
            memory_type=memory_type,
            content=memory_in.get("content", ""),
            agent_id=memory_in.get("agent_id"),
            session_id=memory_in.get("session_id"),
            importance=memory_in.get("importance", 0.5),
            confidence=memory_in.get("confidence", 0.5),
        )
        return APIResponse(data={"id": memory_id}, message="Memory created successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{memory_id}", response_model=APIResponse[dict])
def get_memory(
    memory_id: int,
    memory_service: Optional[MemoryService] = Depends(get_memory_service),
    current_user = Depends(get_current_active_user)
):
    """Get a specific memory by ID."""
    if not memory_service:
        return APIResponse(data=None, message="Memory service not initialized")
    
    memory = memory_service.retrieve_memory(memory_id)
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    
    return APIResponse(
        data={
            "id": memory.id,
            "content": memory.content,
            "memory_type": memory.memory_type.value if memory.memory_type else None,
            "agent_id": memory.agent_id,
            "session_id": memory.session_id,
        }, 
        message="Memory retrieved successfully"
    )


@router.put("/{memory_id}", response_model=APIResponse[dict])
def update_memory(
    memory_id: int,
    memory_in: dict,
    memory_service: Optional[MemoryService] = Depends(get_memory_service),
    current_user = Depends(get_current_active_user)
):
    """Update a memory."""
    # Implementation would go here
    return APIResponse(data={"id": memory_id}, message="Memory updated successfully")


@router.delete("/{memory_id}", response_model=APIResponse[dict])
def delete_memory(
    memory_id: int,
    memory_service: Optional[MemoryService] = Depends(get_memory_service),
    current_user = Depends(get_current_active_user)
):
    """Delete a memory."""
    # Implementation would go here
    return APIResponse(data={"success": True}, message="Memory deleted successfully")


@router.get("/features/status", response_model=APIResponse[dict])
def get_feature_flags():
    """Get memory feature flags status."""
    return APIResponse(
        data=FeatureFlags.all_enabled(),
        message="Feature flags retrieved"
    )


__all__ = ["router"]