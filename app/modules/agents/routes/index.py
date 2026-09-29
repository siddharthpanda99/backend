from typing import List
from fastapi import APIRouter, HTTPException, Depends
from common_lib.modules.agents.crud.schemas import AgentRead, AgentCreate, AgentUpdate
from common_lib.modules.agents.crud.service import agent_service, NotFoundError
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user
from app.modules.agents.routes.registry import router as registry_router
from app.modules.agents.routes.runtime_routes import router as runtime_router
from app.modules.agents.routes.session_routes import router as session_router
from app.modules.agents.routes.pipeline_routes import router as pipeline_router
from app.modules.agents.routes.tracing_routes import router as tracing_router
from app.modules.agents.routes.policy_routes import router as policy_router
from app.modules.agents.routes.task_routes import router as task_router
from app.modules.agents.routes.profile_routes import router as profile_router
from app.modules.agents.routes.skill_routes import router as skill_router
from app.modules.agents.routes.daemon_routes import router as daemon_router
from app.modules.agents.routes.doom_loop_routes import router as doom_loop_router
from app.modules.agents.routes.tool_artifact_routes import (
    router as tool_artifact_router,
)
from app.modules.agents.routes.checkpoint_routes import router as checkpoint_router
from app.modules.agents.routes.playbook_routes import router as playbook_router
from app.modules.agents.routes.snapshots_routes import router as snapshots_router

router = APIRouter()
router.include_router(registry_router, prefix="/registry", tags=["Registry"])
# Policy routes were previously mounted bare at `/agents` in ROUTER_DEFINITIONS,
# which collided with this router's own collection root and with `@router.get(
# "/{id}")` — so /agents/policies and /agents/multi-agent 404'd as "Agent not
# found". Mounted here instead, alongside every sibling.
router.include_router(policy_router, prefix="", tags=["Policy & Multi-Agent"])
router.include_router(runtime_router, prefix="/runtime", tags=["Agent Runtime"])
router.include_router(session_router, prefix="/runtime", tags=["Sessions"])
router.include_router(pipeline_router, prefix="/pipelines", tags=["Pipelines"])
router.include_router(tracing_router, prefix="/traces", tags=["Agent Tracing"])
router.include_router(task_router, prefix="/tasks", tags=["Task Queue"])
router.include_router(profile_router, prefix="/profiles", tags=["Agent Profiles"])
router.include_router(skill_router, prefix="/skills", tags=["Skill Bridge"])
router.include_router(daemon_router, prefix="/daemons", tags=["Agent Daemons"])
router.include_router(
    doom_loop_router, prefix="/doom-loops", tags=["Doom Loop Detection"]
)
router.include_router(
    tool_artifact_router, prefix="/tool-artifacts", tags=["Tool Artifacts"]
)
router.include_router(
    checkpoint_router, prefix="/checkpoints", tags=["Context Checkpoints"]
)
router.include_router(playbook_router, prefix="/playbooks", tags=["Playbooks"])
# Snapshot routes were written but never mounted anywhere in the app — the
# module had zero importers of `snapshots_routes`, so every snapshot endpoint
# was unreachable. Mounted here under a `/snapshots` prefix so the paths do not
# collide with the `/{id}` CRUD routes declared below.
router.include_router(snapshots_router, prefix="/snapshots", tags=["Snapshots"])


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
