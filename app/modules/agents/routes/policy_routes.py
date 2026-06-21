"""
Policy & Multi-Agent API Routes
-------------------------
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from datetime import datetime
import logging

from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Policy & Multi-Agent"])


class PolicyCreateRequest(BaseModel):
    policy_id: str
    name: str
    description: str = ""
    permissions: dict = {}


class MultiAgentExecuteRequest(BaseModel):
    user_request: str
    available_agents: List[str] = []
    context: dict = {}
    use_critic: bool = True


_policy_manager = None
_coordinator = None


def set_policy_manager(manager):
    global _policy_manager
    _policy_manager = manager


def set_multi_agent_coordinator(coordinator):
    global _coordinator
    _coordinator = coordinator


@router.post("/policies", response_model=APIResponse[dict])
async def create_policy(
    request: PolicyCreateRequest, current_user=Depends(get_current_active_user)
):
    """Create a tool policy."""
    if not _policy_manager:
        raise HTTPException(status_code=500, detail="Policy manager not configured")

    try:
        from common_lib.modules.orchestration.tools.sandbox import (
            ToolPolicy,
            ToolPermissionManager,
        )

        policy = ToolPolicy(
            policy_id=request.policy_id,
            name=request.name,
            description=request.description,
            permissions={},
        )

        success = _policy_manager.register_policy(policy)

        return APIResponse(
            data={"policy_id": request.policy_id, "created": success},
            message="Policy created" if success else "Failed",
        )
    except Exception as e:
        logger.error(f"Policy creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/policies", response_model=APIResponse[List[dict]])
async def list_policies(current_user=Depends(get_current_active_user)):
    """List policies."""
    if not _policy_manager:
        return APIResponse(data=[], message="No policies")

    policies = _policy_manager._policies
    return APIResponse(
        data=[
            {
                "policy_id": p.policy_id,
                "name": p.name,
                "description": p.description,
            }
            for p in policies.values()
        ],
        message=f"Retrieved {len(policies)} policies",
    )


@router.post("/policies/{policy_id}/assign", response_model=APIResponse[dict])
async def assign_policy(
    policy_id: str, agent_id: str, current_user=Depends(get_current_active_user)
):
    """Assign a policy to an agent."""
    if not _policy_manager:
        raise HTTPException(status_code=500, detail="Policy manager not configured")

    success = _policy_manager.assign_policy_to_agent(agent_id, policy_id)

    return APIResponse(
        data={"assigned": success},
        message="Policy assigned" if success else "Failed",
    )


@router.post("/multi-agent/execute", response_model=APIResponse[dict])
async def execute_multi_agent(
    request: MultiAgentExecuteRequest, current_user=Depends(get_current_active_user)
):
    """Execute task with multi-agent coordination."""
    if not _coordinator:
        raise HTTPException(status_code=500, detail="Coordinator not configured")

    try:
        result = await _coordinator.execute(
            user_request=request.user_request,
            available_agents=request.available_agents,
            context=request.context,
            use_critic=request.use_critic,
        )

        return APIResponse(
            data={
                "coordination_id": result.coordination_id,
                "status": result.status,
                "tasks": [
                    {
                        "task_id": t.task_id,
                        "role": t.agent_role,
                        "description": t.description,
                        "status": t.status,
                    }
                    for t in result.tasks
                ],
                "final_result": result.final_result,
                "duration_ms": result.duration_ms,
            },
            message=f"Multi-agent {result.status}",
        )
    except Exception as e:
        logger.error(f"Multi-agent execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/multi-agent/executions", response_model=APIResponse[List[dict]])
async def list_multi_agent_executions(
    limit: int = 20, current_user=Depends(get_current_active_user)
):
    """List multi-agent executions."""
    if not _coordinator:
        return APIResponse(data=[], message="No executions")

    coordinations = _coordinator.list_coordinations()

    return APIResponse(
        data=[
            {
                "coordination_id": c.coordination_id,
                "status": c.status,
                "task_count": len(c.tasks),
                "duration_ms": c.duration_ms,
            }
            for c in coordinations[:limit]
        ],
        message=f"Retrieved {len(coordinations)} coordinations",
    )


@router.get(
    "/multi-agent/executions/{coordination_id}", response_model=APIResponse[dict]
)
async def get_multi_agent_execution(
    coordination_id: str, current_user=Depends(get_current_active_user)
):
    """Get a multi-agent execution."""
    if not _coordinator:
        raise HTTPException(status_code=500, detail="Coordinator not configured")

    coordination = _coordinator.get_coordination(coordination_id)
    if not coordination:
        raise HTTPException(status_code=404, detail="Coordination not found")

    return APIResponse(
        data={
            "coordination_id": coordination.coordination_id,
            "status": coordination.status,
            "tasks": [
                {
                    "task_id": t.task_id,
                    "role": t.agent_role,
                    "description": t.description,
                    "status": t.status,
                    "result": t.result,
                }
                for t in coordination.tasks
            ],
            "final_result": coordination.final_result,
            "duration_ms": coordination.duration_ms,
        },
        message="Coordination retrieved",
    )
