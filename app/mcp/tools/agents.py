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
