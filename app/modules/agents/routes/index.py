from typing import List
from fastapi import APIRouter, HTTPException, Depends
from app.modules.common.types.index import APIResponse
from app.modules.agents.schemas.index import AgentRead, AgentCreate, AgentUpdate
from app.modules.agents.service.index import agent_service
from app.modules.agents.routes.registry import router as registry_router
from app.modules.agents.runtime.routes import router as runtime_router
from app.modules.agents.runtime.session_routes import router as session_router
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()
router.include_router(registry_router, prefix="/registry", tags=["Registry"])
router.include_router(runtime_router, prefix="/runtime", tags=["Agent Runtime"])
router.include_router(session_router, prefix="/runtime", tags=["Sessions"])


@router.get("/", response_model=APIResponse[List[AgentRead]])
def list_agents(
    skip: int = 0, limit: int = 100, current_user=Depends(get_current_active_user)
):
    items = agent_service.get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of agents")


@router.post("/", response_model=APIResponse[AgentRead])
def create_agent(agent_in: AgentCreate, current_user=Depends(get_current_active_user)):
    item = agent_service.create(agent_in)
    return APIResponse(data=item, message="Agent created successfully")


@router.get("/{id}", response_model=APIResponse[AgentRead])
def get_agent(id: str, current_user=Depends(get_current_active_user)):
    item = agent_service.get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Agent not found")
    return APIResponse(data=item, message="Agent retrieved successfully")


@router.put("/{id}", response_model=APIResponse[AgentRead])
def update_agent(
    id: str, agent_in: AgentUpdate, current_user=Depends(get_current_active_user)
):
    item = agent_service.update(id, agent_in)
    return APIResponse(data=item, message="Agent updated successfully")


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_agent(id: str, current_user=Depends(get_current_active_user)):
    agent_service.delete(id)
    return APIResponse(data={"success": True}, message="Agent deleted successfully")
