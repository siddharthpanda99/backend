from fastapi import APIRouter, Depends, HTTPException
from typing import List
from common_lib.modules.memories.schemas import MemoryRead, MemoryCreate, MemoryUpdate
from common_lib.modules.memories.service import memory_service, NotFoundError
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()


@router.get("/", response_model=APIResponse[List[MemoryRead]])
def list_memories(skip: int = 0, limit: int = 100):
    items = memory_service.get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of memories")


@router.post("/", response_model=APIResponse[MemoryRead])
def create_memory(
    memory_in: MemoryCreate, current_user=Depends(get_current_active_user)
):
    item = memory_service.create(memory_in)
    return APIResponse(data=item, message="Memory created successfully")


@router.get("/{id}", response_model=APIResponse[MemoryRead])
def get_memory(id: str, current_user=Depends(get_current_active_user)):
    item = memory_service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory not found")
    return APIResponse(data=item, message="Memory retrieved successfully")


@router.put("/{id}", response_model=APIResponse[MemoryRead])
def update_memory(
    id: str, memory_in: MemoryUpdate, current_user=Depends(get_current_active_user)
):
    try:
        item = memory_service.update(id, memory_in)
        return APIResponse(data=item, message="Memory updated successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Memory not found")


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_memory(id: str, current_user=Depends(get_current_active_user)):
    try:
        memory_service.delete(id)
        return APIResponse(
            data={"success": True}, message="Memory deleted successfully"
        )
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Memory not found")


__all__ = ["router"]
