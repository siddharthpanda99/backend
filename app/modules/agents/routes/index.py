from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session
from typing import List
from app.modules.common.types.index import APIResponse
from app.modules.database.service.connection import get_session
from app.modules.agents.service.index import agent_service
from app.modules.agents.schemas.index import AgentRead, AgentCreate, AgentUpdate

router = APIRouter()

@router.get("/", response_model=APIResponse[List[AgentRead]])
def list_agents(skip: int = 0, limit: int = 100):
    items = agent_service.get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of agents")

@router.post("/", response_model=APIResponse[AgentRead])
def create_agent(agent_in: AgentCreate):
    item = agent_service.create(agent_in)
    return APIResponse(data=item, message="Agent created successfully")

@router.get("/{id}", response_model=APIResponse[AgentRead])
def get_agent(id: str):
    item = agent_service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Agent not found")
    return APIResponse(data=item, message="Agent retrieved successfully")

@router.put("/{id}", response_model=APIResponse[AgentRead])
def update_agent(id: str, agent_in: AgentUpdate):
    item = agent_service.update(id, agent_in)
    return APIResponse(data=item, message="Agent updated successfully")

@router.delete("/{id}", response_model=APIResponse[dict])
def delete_agent(id: str):
    agent_service.delete(id)
    return APIResponse(data={"success": True}, message="Agent deleted successfully")
