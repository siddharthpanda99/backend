from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.modules.common.types.index import APIResponse
from app.modules.database.service.connection import get_session
from app.modules.tools.service.index import tool_service
from app.modules.tools.schemas.index import ToolRead, ToolCreate, ToolUpdate

router = APIRouter()

@router.get("/", response_model=APIResponse[List[ToolRead]])
def list_tools(skip: int = 0, limit: int = 100, db: Session = Depends(get_session)):
    items = tool_service.get_all(db, skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of tools")

@router.post("/", response_model=APIResponse[ToolRead])
def create_tool(tool_in: ToolCreate, db: Session = Depends(get_session)):
    item = tool_service.create(db, tool_in)
    return APIResponse(data=item, message="Tool created successfully")

@router.get("/{id}", response_model=APIResponse[ToolRead])
def get_tool(id: str, db: Session = Depends(get_session)):
    item = tool_service.get_by_id(db, id)
    if not item:
        raise HTTPException(status_code=404, detail="Tool not found")
    return APIResponse(data=item, message="Tool retrieved successfully")

@router.put("/{id}", response_model=APIResponse[ToolRead])
def update_tool(id: str, tool_in: ToolUpdate, db: Session = Depends(get_session)):
    item = tool_service.update(db, id, tool_in)
    return APIResponse(data=item, message="Tool updated successfully")

@router.delete("/{id}", response_model=APIResponse[dict])
def delete_tool(id: str, db: Session = Depends(get_session)):
    tool_service.delete(db, id)
    return APIResponse(data={"success": True}, message="Tool deleted successfully")
