from typing import List
from fastapi import APIRouter, HTTPException, Depends
from common_lib.modules.agents.schemas import AgentRead, AgentCreate, AgentUpdate
from common_lib.modules.agents.service import agent_service, NotFoundError
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user
from app.modules.agents.routes.registry import router as registry_router
from app.modules.agents.runtime.routes import router as runtime_router
from app.modules.agents.runtime.session_routes import router as session_router
from app.modules.agents.runtime.pipeline_routes import router as pipeline_router

router = APIRouter()
router.include_router(registry_router, prefix="/registry", tags=["Registry"])
router.include_router(runtime_router, prefix="/runtime", tags=["Agent Runtime"])
router.include_router(session_router, prefix="/runtime", tags=["Sessions"])
router.include_router(pipeline_router, prefix="/pipelines", tags=["Pipelines"])


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
    try:
        item = agent_service.update(id, agent_in)
        return APIResponse(data=item, message="Agent updated successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_agent(id: str, current_user=Depends(get_current_active_user)):
    try:
        agent_service.delete(id)
        return APIResponse(data={"success": True}, message="Agent deleted successfully")
    except NotFoundError:
        raise HTTPException(status_code=404, detail="Agent not found")


__all__ = ["router"]
