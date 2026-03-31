"""
agents/runtime/routes.py
--------------------------
FastAPI router for the agent runtime.

Registered at: /api/v1/agents/runtime/

Endpoints:
    POST /deploy                   — load/reload a custom agent
    GET  /session                  — current session info
    POST /stream                   — stream SSE events for a message
    GET  /session_state/{id}       — read full LangGraph state for a thread
    POST /session_state/{id}       — override state (history, hints, etc.)
    GET  /available_tools          — list all available tools (builtins + registry)
    GET  /available_workflows      — list available workflows
    POST /set_quota_tier           — update quota tier
    POST /sync_quota               — sync client-side quota counters
    GET  /gemini_models            — live Gemini model list
"""
from __future__ import annotations

import traceback
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.modules.agents.runtime.core import (
    load_keys,
    load_agent,
    get_master_agent,
    get_engine_manager,
    get_active_session,
    stream_agent_generator,
)
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from app.modules.agents.runtime.utils.logging import get_logger

logger = get_logger(__name__)

# Load API keys at import time (non-blocking)
load_keys()

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DeployRequest(BaseModel):
    model_path:            Optional[str]       = None
    provider:              Optional[str]       = "local_llama"
    agent_id:              Optional[str]       = "master_agent"
    agent_display_name:    Optional[str]       = "Master Agent"
    tool_ids:              Optional[List[str]] = None
    system_prompt:         Optional[str]       = None
    guardrails:            Optional[List]      = None
    use_mcp_discovery:     Optional[bool]      = False
    global_search_enabled: Optional[bool]      = False
    workflow_ids:          Optional[List[str]] = None


class StreamRequest(BaseModel):
    message:    str
    session_id: str
    provider:   Optional[str] = None


class StateUpdateRequest(BaseModel):
    history:              Optional[str]  = None
    intermediate_steps:   Optional[list] = None
    structured_state:     Optional[dict] = None
    hints:                Optional[list] = None
    operational_metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/deploy")
async def deploy(req: DeployRequest):
    """Compile and activate a custom agent for the given configuration."""
    try:
        load_agent(
            model_path=req.model_path,
            provider=req.provider,
            agent_id=req.agent_id,
            agent_display_name=req.agent_display_name,
            tool_ids=req.tool_ids,
            system_prompt=req.system_prompt,
            guardrails=req.guardrails,
            use_mcp_discovery=req.use_mcp_discovery,
            global_search_enabled=req.global_search_enabled,
            workflow_ids=req.workflow_ids,
        )
        return {"status": "success", "info": await get_session()}
    except Exception as exc:
        logger.error(traceback.format_exc())
        return {"status": "error", "message": str(exc)}


@router.get("/session")
async def get_session():
    """Return the currently active agent session metadata."""
    em    = get_engine_manager()
    agent = get_master_agent()
    sess  = get_active_session()

    if not em:
        return {"status": "inactive"}

    info = {**sess}
    if agent and agent.model_provider:
        info.update(agent.model_provider.get_info())
    return info


@router.post("/stream")
async def stream(req: StreamRequest):
    """Stream agent reasoning as Server-Sent Events."""
    return StreamingResponse(
        stream_agent_generator(req.message, req.session_id),
        media_type="text/event-stream",
    )


@router.get("/session_state/{session_id}")
async def read_session_state(session_id: str):
    """Read the full LangGraph checkpoint state for a thread."""
    agent = get_master_agent()
    if not agent or not agent.graph:
        return {"error": "Agent not deployed"}

    state = agent.graph.get_state({"configurable": {"thread_id": session_id}})
    v = state.values
    return {
        "session_id":          session_id,
        "history":             v.get("conversation_history", ""),
        "intermediate_steps":  v.get("intermediate_steps", []),
        "structured_state":    v.get("structured_state", {}),
        "hints":               v.get("hints", []),
        "operational_metadata": v.get("operational_metadata", {}),
        "last_input":          v.get("input", ""),
        "checkpoint_id":       str(state.config.get("configurable", {}).get("checkpoint_id", "initial")),
    }


@router.post("/session_state/{session_id}")
async def update_session_state(session_id: str, req: StateUpdateRequest):
    """Manually override agent memory/history for a thread."""
    agent = get_master_agent()
    if not agent or not agent.graph:
        return {"error": "Agent not deployed"}

    updates: Dict[str, Any] = {}
    if req.history              is not None: updates["conversation_history"] = req.history
    if req.intermediate_steps   is not None: updates["intermediate_steps"]   = req.intermediate_steps
    if req.structured_state     is not None: updates["structured_state"]     = req.structured_state
    if req.hints                is not None: updates["hints"]                = req.hints
    if req.operational_metadata is not None: updates["operational_metadata"] = req.operational_metadata

    try:
        agent.graph.update_state({"configurable": {"thread_id": session_id}}, updates)
        return {"status": "success", "message": "State updated"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/available_tools")
async def available_tools():
    """List all available tools grouped by category."""
    from app.core.common_lib_integration import common_memory

    em     = get_engine_manager()
    groups: Dict[str, List[Dict]] = {}

    # Builtins
    for t in BUILTIN_TOOL_REGISTRY:
        groups.setdefault(t["category"], []).append(
            {"id": t["id"], "name": t["name"], "description": t["description"]}
        )

    # Dynamic registry
    if em and em.registry_svc:
        for cat, tools in em.registry_svc.get_tools_by_category().items():
            for t in tools:
                if any(e["id"] == t["id"] for e in groups.get(cat, [])):
                    continue
                if (t.get("metadata") or {}).get("entity_type") == "workflow":
                    continue
                groups.setdefault(cat, []).append(
                    {"id": t["id"], "name": t["name"], "description": t["description"]}
                )

    return sorted(
        [{"id": cat, "name": cat.replace("_", " ").title(), "tools": tools}
         for cat, tools in groups.items()],
        key=lambda x: x["name"],
    )


@router.get("/available_workflows")
async def available_workflows():
    """List all available workflows grouped by category."""
    from app.core.common_lib_integration import common_memory

    try:
        wfs    = common_memory.list_workflow_definitions()
        groups: Dict[str, List] = {}
        for w in wfs:
            defn = w.get("definition", {})
            cat  = defn.get("category") or defn.get("group") or "General"
            name = defn.get("name") or w.get("name") or w["id"].replace("_", " ").title()
            groups.setdefault(cat, []).append({
                "id": w["id"], "name": name,
                "description": defn.get("description", "Workflow."),
                "category": cat.replace("_", " ").title(),
            })
        return sorted(
            [{"id": f"wf_{c.lower()}", "name": f"{c} (Workflows)", "items": items}
             for c, items in groups.items()],
            key=lambda x: x["name"],
        )
    except Exception as exc:
        logger.error("Workflow list failed: %s", exc)
        return []


@router.get("/gemini_models")
async def gemini_models():
    """Return the live list of available Gemini models."""
    em = get_engine_manager()
    if em and em.main_llm and hasattr(em.main_llm, "list_models"):
        return em.main_llm.list_models()
    try:
        from common_lib.modules.ai_models.llm.gemini import GeminiProvider
        from common_lib.modules.orchestration.inference.schemas import ModelConfiguration
        p = GeminiProvider(ModelConfiguration(
            provider_id="temp", provider_type="gemini", model_name="gemini-1.5-pro"
        ))
        return p.list_models()
    except Exception as exc:
        logger.error("Gemini model list failed: %s", exc)
        return []


@router.post("/set_quota_tier")
async def set_quota_tier(tier: str):
    from common_lib.modules.ai_models.llm.quota import quota_manager
    quota_manager.set_tier(tier)
    return {"status": "success", "tier": tier}


@router.post("/sync_quota")
async def sync_quota(usage_data: Dict[str, Any]):
    from common_lib.modules.ai_models.llm.quota import quota_manager
    quota_manager.sync_from_client(usage_data)
    return {"status": "success"}
