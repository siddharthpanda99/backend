from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.modules.common.types.index import APIResponse
from app.modules.database.service.connection import get_session
from app.modules.memories.service.index import memory_service
from app.modules.memories.schemas.index import MemoryRead, MemoryCreate, MemoryUpdate

router = APIRouter()

@router.get("/", response_model=APIResponse[List[MemoryRead]])
def list_memories(skip: int = 0, limit: int = 100):
    items = memory_service.get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of memories")

@router.post("/", response_model=APIResponse[MemoryRead])
def create_memory(memory_in: MemoryCreate):
    item = memory_service.create(memory_in)
    return APIResponse(data=item, message="Memory created successfully")

@router.get("/{id}", response_model=APIResponse[MemoryRead])
def get_memory(id: str):
    item = memory_service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Memory not found")
    return APIResponse(data=item, message="Memory retrieved successfully")

@router.put("/{id}", response_model=APIResponse[MemoryRead])
def update_memory(id: str, memory_in: MemoryUpdate):
    item = memory_service.update(id, memory_in)
    return APIResponse(data=item, message="Memory updated successfully")

@router.delete("/{id}", response_model=APIResponse[dict])
def delete_memory(id: str):
    memory_service.delete(id)
    return APIResponse(data={"success": True}, message="Memory deleted successfully")
