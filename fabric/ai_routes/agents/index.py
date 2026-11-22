"""Combined agents router — root CRUD + the five AI-runtime sub-routers.

Port of ``Backend/app/modules/agents/routes/index.py`` trimmed to the
AI-model-serving surface: the registry, runtime, sessions, pipelines and
traces sub-routers (Backend tags: "Registry", "Agent Runtime", "Sessions",
"Pipelines", "Agent Tracing") plus the root agent CRUD routes.

Fabric notes:
- ``response_model=`` is omitted on the root CRUD routes — the
  ``common_lib.modules.agents.crud.schemas`` models need sqlmodel, which
  the fabric control-plane venv does not carry. Handlers still return the
  same ``APIResponse`` envelopes, so the wire shape is unchanged.
- Agent auth deps are dropped (the fabric control plane has no auth).
"""

from __future__ import annotations

from typing import List
from fastapi import APIRouter, HTTPException
from common_lib.modules.agents.crud.schemas import AgentRead, AgentCreate, AgentUpdate
from fabric.ai_routes.api_schemas import APIResponse

from fabric.ai_routes.agents.registry import (
    router as registry_router,
)
from fabric.ai_routes.agents.runtime_routes import (
    router as runtime_router,
)
from fabric.ai_routes.agents.session_routes import (
    router as session_router,
)
from fabric.ai_routes.agents.pipeline_routes import (
    router as pipeline_router,
)
from fabric.ai_routes.agents.tracing_routes import (
    router as tracing_router,
)

router = APIRouter()
router.include_router(registry_router, prefix="/registry", tags=["Registry"])
router.include_router(runtime_router, prefix="/runtime", tags=["Agent Runtime"])
router.include_router(session_router, prefix="/runtime", tags=["Sessions"])
router.include_router(pipeline_router, prefix="/pipelines", tags=["Pipelines"])
router.include_router(tracing_router, prefix="/traces", tags=["Agent Tracing"])


def _agent_service():
    # Lazy: the fabric control-plane venv has no sqlmodel.
    from common_lib.modules.agents.crud.service import agent_service

    return agent_service


def _not_found_error():
    from common_lib.modules.agents.crud.service import NotFoundError

    return NotFoundError


@router.get("/", response_model=APIResponse[List[AgentRead]])
def list_agents(skip: int = 0, limit: int = 100):
    items = _agent_service().get_all(skip=skip, limit=limit)
    return APIResponse(data=items, message="Retrieved list of agents")


@router.post("/", response_model=APIResponse[AgentRead])
def create_agent(agent_in: AgentCreate):
    item = _agent_service().create(agent_in)
    return APIResponse(data=item, message="Agent created successfully")


@router.get("/{id}", response_model=APIResponse[AgentRead])
def get_agent(id: str):
    item = _agent_service().get_by_id(id)
    if not item:
        raise HTTPException(status_code=404, detail="Agent not found")
    return APIResponse(data=item, message="Agent retrieved successfully")


@router.put("/{id}", response_model=APIResponse[AgentRead])
def update_agent(id: str, agent_in: AgentUpdate):
    try:
        item = _agent_service().update(id, agent_in)
        return APIResponse(data=item, message="Agent updated successfully")
    except _not_found_error():
        raise HTTPException(status_code=404, detail="Agent not found")


@router.delete("/{id}", response_model=APIResponse[dict])
def delete_agent(id: str):
    try:
        _agent_service().delete(id)
        return APIResponse(data={"success": True}, message="Agent deleted successfully")
    except _not_found_error():
        raise HTTPException(status_code=404, detail="Agent not found")


__all__ = ["router"]
