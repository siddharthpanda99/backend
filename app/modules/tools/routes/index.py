from fastapi import APIRouter, Depends, HTTPException
from typing import List
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.tools.schemas import ToolRead, ToolCreate, ToolUpdate
from common_lib.modules.tools.service import tool_service, NotFoundError
from app.modules.common.types.index import APIResponse

router = APIRouter()


@router.get("/", response_model=APIResponse[List[ToolRead]])
def list_tools(skip: int = 0, limit: int = 100):
    items = tool_service.get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of tools")


@router.post("/", response_model=APIResponse[ToolRead])
def create_tool(tool_in: ToolCreate):
    item = tool_service.create(tool_in)
    return APIResponse(data=item, message="Tool created successfully")


@router.get("/{id}", response_model=APIResponse[ToolRead])
def get_tool(id: str):
    item = tool_service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Tool not found")
    return APIResponse(data=item, message="Tool retrieved successfully")


@router.put("/{id}", response_model=APIResponse[ToolRead])
def update_tool(id: str, tool_in: ToolUpdate):
    try:
        item = tool_service.update(id, tool_in)
        return APIResponse(data=item, message="Tool updated successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Tool not found")


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_tool(id: str):
    try:
        tool_service.delete(id)
        return APIResponse(data={"success": True}, message="Tool deleted successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Tool not found")
