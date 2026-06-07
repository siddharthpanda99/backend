import logging
import asyncio
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from ..mcp_dependencies import (
    resolve_agent_service, 
    resolve_runtime_session, 
    resolve_master_agent, 
    resolve_engine_manager
)

logger = logging.getLogger("mcp.tools.agents")

def register_agent_tools(mcp: FastMCP):
    """Register tools for managing platform agents and their execution runtime."""

    @mcp.tool()
    async def list_agents(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """List all platform agents registered in the system."""
        service = resolve_agent_service()
        agents = service.get_all(skip=skip, limit=limit)
        return [a.model_dump() if hasattr(a, "model_dump") else a for a in agents]

    @mcp.tool()
    async def get_agent_details(agent_id: str) -> Dict[str, Any]:
        """Retrieve the full profile and configuration for a specific agent."""
        service = resolve_agent_service()
        agent = service.get_by_id(agent_id)
        if not agent:
            return {"status": "error", "message": "Agent not found"}
        return agent.model_dump() if hasattr(agent, "model_dump") else agent

    @mcp.tool()
    async def create_agent(name: str, description: str, system_prompt: str, model_id: str) -> Dict[str, Any]:
        """Create a new platform agent with specific instructions and model pairing."""
        service = resolve_agent_service()
        from common_lib.modules.agents.schemas import AgentCreate
        agent_in = AgentCreate(
            name=name,
            description=description,
            system_prompt=system_prompt,
            model_id=model_id
        )
        agent = service.create(agent_in)
        return agent.model_dump() if hasattr(agent, "model_dump") else agent

    # --- RUNTIME TOOLS ---

    @mcp.tool()
    async def get_active_agent_session() -> Dict[str, Any]:
        """Retrieve metadata about the currently active agent session (model, status, persona)."""
        session = resolve_runtime_session()
        return session if session else {"status": "inactive"}

    @mcp.tool()
    async def set_human_feedback_mode(enabled: bool) -> Dict[str, Any]:
        """Toggle Human-in-the-Loop (HITL) mode for the active agent session."""
        from app.modules.agents.runtime.core import set_human_feedback_mode as set_hitl
        set_hitl(enabled)
        return {"status": "updated", "hitl_enabled": enabled}

    # --- HITL REQUEST TOOLS ---

    HITL_REQUEST_ATTRS = [
        "approval_policy_id", "agent_id", "action", "tool", "risk_score",
        "justification", "route_to", "requested_at", "expires_at", "decided_by",
        "decided_at", "decision_notes", "approval_token", "source", "session_id",
        "trace_id", "tool_input", "modified_tool_input", "executed_at",
        "execution_outcome", "feedback_rating", "feedback_comment", "timeline",
    ]

    @mcp.tool()
    async def request_hitl_approval(
        agent_id: str,
        action: str = "",
        tool: str = "",
        risk_score: int = 0,
        justification: str = "",
        tool_input: Optional[Dict[str, Any]] = None,
        approval_policy_id: str = "",
        session_id: str = "",
    ) -> Dict[str, Any]:
        """Submit a new HITL approval request. Returns the pending request with its status and token."""
        from common_lib.modules.governance.hitl.service import get_hitl_service
        svc = get_hitl_service()
        item = svc.create_request(
            approval_policy_id=approval_policy_id,
            agent_id=agent_id,
            action=action,
            tool=tool,
            risk_score=risk_score,
            justification=justification,
            route_to="",
            source="mcp",
            session_id=session_id,
            trace_id="",
            tool_input=tool_input or {},
        )
        result = {"id": getattr(item, "id", ""), "status": getattr(item, "status", "pending")}
        for attr in HITL_REQUEST_ATTRS:
            if hasattr(item, attr):
                result[attr] = getattr(item, attr)
        return result

    @mcp.tool()
    async def check_hitl_status(request_id: str) -> Dict[str, Any]:
        """Check the current status of a HITL approval request by its ID."""
        from common_lib.modules.governance.hitl.service import get_hitl_service
        svc = get_hitl_service()
        item = svc.get_request(request_id)
        if not item:
            return {"status": "not_found", "id": request_id}
        result = {"id": getattr(item, "id", ""), "status": getattr(item, "status", "unknown")}
        for attr in HITL_REQUEST_ATTRS:
            if hasattr(item, attr):
                result[attr] = getattr(item, attr)
        return result

    @mcp.tool()
    async def list_hitl_overrides() -> List[Dict[str, Any]]:
        """List all emergency overrides currently active in the HITL system."""
        from common_lib.modules.governance.hitl.service import get_hitl_service
        svc = get_hitl_service()
        items = svc.list_overrides()
        result = []
        for item in items:
            d = {}
            for attr in [
                "target", "target_type", "action", "reason",
                "authorized_by", "incident_id", "created_at",
            ]:
                if hasattr(item, attr):
                    v = getattr(item, attr)
                    d[attr] = (
                        str(v)
                        if not isinstance(v, (str, int, float, bool, type(None)))
                        else v
                    )
            result.append(d)
        return result

    @mcp.tool()
    async def deploy_agent_persona(model_path: str, provider: str = "vllm", agent_id: str = "master_agent", system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Deploy and activate a custom agent persona on the specified inference engine."""
        from app.modules.agents.runtime.core import load_agent_generator
        await asyncio.to_thread(load_agent_generator, model_path=model_path, provider=provider, agent_id=agent_id, system_prompt=system_prompt)
        return {"status": "deployment_initiated", "agent_id": agent_id, "model": model_path}

    @mcp.tool()
    async def clear_agent_session(hard_reset: bool = False) -> Dict[str, Any]:
        """Clear the current session history or perform a hard reset of the inference engine."""
        from app.modules.agents.runtime.core import clear_checkpointer
        if hard_reset:
            # Trigger engine restart logic
            return {"status": "reset_initiated", "type": "hard"}
        else:
            clear_checkpointer()
            return {"status": "history_cleared", "type": "soft"}
