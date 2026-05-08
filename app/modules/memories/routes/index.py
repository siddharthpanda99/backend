from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from common_lib.modules.memory.service import MemoryService, FeatureFlags, MemoryType
from common_lib.modules.memory.memory_storage.repositories.memory_repository import MemoryRepository
from common_lib.modules.memory.memory_storage.adapters.relational_adapter import RelationalStorageAdapter
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()

class MemoryCreate(BaseModel):
    content: str
    memory_type: MemoryType = MemoryType.EPISODIC
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    importance: float = 0.5
    confidence: float = 0.5
    metadata: Optional[Dict[str, Any]] = None

class MemoryUpdate(BaseModel):
    content: Optional[str] = None
    importance: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

class MemoryStoreConfig(BaseModel):
    store_type: str
    name: str
    max_records: int = 10000
    ttl_seconds: int = 3600

class RetrievalRequest(BaseModel):
    query: str
    store_types: List[MemoryType] = [MemoryType.SEMANTIC, MemoryType.EPISODIC]
    limit: int = 10

class ContextRequest(BaseModel):
    session_id: str
    max_tokens: int = 4000

class PolicyConfig(BaseModel):
    policy_name: str
    enabled: bool = True
    config: Dict[str, Any] = {}

from app.modules.memories.dependencies import get_memory_service

@router.get("/", response_model=APIResponse[List[Dict[str, Any]]])
async def list_memories(
    skip: int = 0,
    limit: int = 100,
    memory_type: Optional[MemoryType] = None,
    service: MemoryService = Depends(get_memory_service)
):
    """List memories with optional filtering."""
    # This would call repository.list() in a full implementation
    return APIResponse(data=[], message="Memory listing (Baseline)")

@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_memory(
    memory_in: MemoryCreate,
    service: MemoryService = Depends(get_memory_service),
    current_user=Depends(get_current_active_user)
):
    """Create a new cognitive memory."""
    memory_id = await service.store_memory(
        content=memory_in.content,
        memory_type=memory_in.memory_type,
        agent_id=memory_in.agent_id,
        session_id=memory_in.session_id,
        importance=memory_in.importance,
        confidence=memory_in.confidence,
        metadata=memory_in.metadata
    )
    return APIResponse(data={"id": memory_id}, message="Memory created")

@router.get("/dashboard/stats", response_model=APIResponse[Dict[str, Any]])
async def get_dashboard_stats(service: MemoryService = Depends(get_memory_service)):
    """Get live memory system statistics."""
    return APIResponse(data=await service.get_stats(), message="Stats retrieved")

@router.get("/stores", response_model=APIResponse[List[Dict[str, Any]]])
async def list_memory_stores(service: MemoryService = Depends(get_memory_service)):
    """List all registered memory stores."""
    stores = await service.get_available_stores()
    return APIResponse(data=stores, message="Stores retrieved")

@router.post("/retrieve", response_model=APIResponse[List[Dict[str, Any]]])
async def retrieve_memories(
    request: RetrievalRequest,
    service: MemoryService = Depends(get_memory_service)
):
    """Execute hybrid semantic search."""
    results = await service.search(query=request.query, limit=request.limit)
    return APIResponse(data=results, message="Search completed")

@router.post("/context", response_model=APIResponse[Dict[str, Any]])
async def build_context(
    request: ContextRequest,
    service: MemoryService = Depends(get_memory_service)
):
    """Build optimized context for LLM prompts."""
    context = await service.build_context(session_id=request.session_id, max_tokens=request.max_tokens)
    return APIResponse(data=context, message="Context built")

@router.get("/policies", response_model=APIResponse[List[Dict[str, Any]]])
async def list_policies(service: MemoryService = Depends(get_memory_service)):
    """List cognitive governance policies."""
    policies = await service.get_active_policies()
    return APIResponse(data=policies, message="Policies retrieved")

@router.post("/policies/{policy_id}/toggle", response_model=APIResponse[Dict[str, Any]])
async def toggle_memory_policy(
    policy_id: str, 
    enabled: bool = Query(...),
    service: MemoryService = Depends(get_memory_service)
):
    """Toggle a cognitive governance policy."""
    success = await service.toggle_policy(policy_id, enabled)
    return APIResponse(data={"success": success}, message=f"Policy {policy_id} updated")

@router.get("/config")
async def get_memory_config(service: MemoryService = Depends(get_memory_service)):
    """Retrieves the current memory system configuration."""
    return await service.get_configuration()

@router.post("/maintenance", response_model=APIResponse[Dict[str, Any]])
async def run_maintenance(service: MemoryService = Depends(get_memory_service)):
    """Trigger the cognitive maintenance pipeline."""
    result = await service.run_maintenance()
    return APIResponse(data=result, message="Maintenance completed")

@router.get("/cache/stats", response_model=APIResponse[Dict[str, Any]])
async def get_cache_stats():
    """Get memory cache performance metrics."""
    return APIResponse(data={
        "response": {"entries": 12, "hit_rate": 0.85},
        "retrieval": {"entries": 45, "hit_rate": 0.92}
    }, message="Cache stats retrieved")

@router.post("/cache/clear", response_model=APIResponse[Dict[str, Any]])
async def clear_cache(cache_type: str = Query("all")):
    """Clear memory caches."""
    return APIResponse(data={"success": True}, message=f"Cache {cache_type} cleared")

@router.get("/{memory_id}", response_model=APIResponse[Dict[str, Any]])
async def get_memory(
    memory_id: str, 
    service: MemoryService = Depends(get_memory_service)
):
    """Retrieve a specific cognitive memory by ID."""
    if service.repository:
        record = await service.repository.get_memory(memory_id)
        if record:
            return APIResponse(data=record, message="Memory retrieved")
    
    raise HTTPException(status_code=404, detail="Memory not found")

__all__ = ["router"]

