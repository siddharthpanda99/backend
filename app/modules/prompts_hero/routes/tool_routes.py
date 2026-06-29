"""Tool routes — micro-app tool registry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from common_lib.modules.data_storage.database.connection import get_session

router = APIRouter()


class ToolCreateRequest(BaseModel):
    name: str
    slug: str
    category: str
    description: str | None = None
    input_schema: list | None = None
    prompt_template: str | None = None
    negative_prompt: str | None = None
    default_model: str | None = None
    default_params: dict | None = None
    credits_cost: int = 3


class ToolUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    input_schema: list | None = None
    prompt_template: str | None = None
    credits_cost: int | None = None


def _svc():
    from common_lib.modules.prompts_hero.services.tool_registry_service import (
        ToolRegistryService,
    )

    return ToolRegistryService()


@router.get("/tools")
def list_tools(category: str | None = None, session: Session = Depends(get_session)):
    svc = _svc()
    tools = svc.list_tools(session, category=category)
    return {"success": True, "data": [t.model_dump() for t in tools]}


@router.get("/tools/categories")
def list_categories(session: Session = Depends(get_session)):
    svc = _svc()
    cats = svc.get_categories(session)
    return {"success": True, "data": cats}


@router.get("/tools/{tool_id}")
def get_tool(tool_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    tool = svc.get_tool(session, tool_id)
    if not tool:
        raise HTTPException(404, "Tool not found")
    return {"success": True, "data": tool.model_dump()}


@router.get("/tools/slug/{slug}")
def get_tool_by_slug(slug: str, session: Session = Depends(get_session)):
    svc = _svc()
    tool = svc.get_tool_by_slug(session, slug)
    if not tool:
        raise HTTPException(404, "Tool not found")
    return {"success": True, "data": tool.model_dump()}


@router.post("/tools")
def create_tool(body: ToolCreateRequest, session: Session = Depends(get_session)):
    svc = _svc()
    tool = svc.create_tool(session, **body.model_dump())
    return {"success": True, "data": tool.model_dump()}


@router.put("/tools/{tool_id}")
def update_tool(
    tool_id: str, body: ToolUpdateRequest, session: Session = Depends(get_session)
):
    svc = _svc()
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    tool = svc.update_tool(session, tool_id, **data)
    if not tool:
        raise HTTPException(404, "Tool not found or is builtin")
    return {"success": True, "data": tool.model_dump()}


@router.delete("/tools/{tool_id}")
def delete_tool(tool_id: str, session: Session = Depends(get_session)):
    svc = _svc()
    if not svc.delete_tool(session, tool_id):
        raise HTTPException(404, "Tool not found or is builtin")
    return {"success": True}


@router.post("/tools/seed")
def seed_tools(session: Session = Depends(get_session)):
    svc = _svc()
    count = svc.seed_builtin_tools(session)
    return {"success": True, "data": {"counted": count}}
