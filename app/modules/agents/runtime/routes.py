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
    POST /upload                  — upload a file for the current session
    POST /set_quota_tier           — update quota tier
    POST /sync_quota               — sync client-side quota counters
    GET  /gemini_models            — live Gemini model list
"""
from __future__ import annotations

import traceback
import asyncio
import time
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import shutil
from pathlib import Path

from app.modules.agents.runtime.core import (
    load_agent,
    load_agent_generator,
    get_master_agent,
    get_engine_manager,
    get_active_session,
    clear_checkpointer,
    get_system_vram_gb,
    get_vram_usage,
    stream_agent_generator,
)
from common_lib.modules.ai_models.llm.vllm_fleet_manager import vllm_fleet as vllm_manager
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from app.modules.agents.runtime.utils.logging import get_logger

logger = get_logger(__name__)

# API keys are now handled via environment variables/config by the base library.

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class DeployRequest(BaseModel):
    model_path:            Optional[str]       = None
    provider:              Optional[str]       = None
    agent_id:              Optional[str]       = "master_agent"
    agent_display_name:    Optional[str]       = "Master Agent"
    tool_ids:              Optional[List[str]] = None
    template_ids:          Optional[List[str]] = None
    system_prompt:         Optional[str]       = None
    guardrails:            Optional[List]      = None
    use_mcp_discovery:     Optional[bool]      = False
    global_search_enabled: Optional[bool]      = False
    workflow_ids:          Optional[List[str]] = None
    engine_id:             Optional[str]       = None  # Fleet node to connect; None = smart-fallback


class FleetDeployRequest(BaseModel):
    model_path:            str
    engine_id:             Optional[str]  = "main"
    gpu_memory_utilization: Optional[float] = 0.85
    max_model_len:         Optional[int]   = 4096
    quantization:          Optional[str]   = "none"

class AgentConnectRequest(BaseModel):
    agent_id:              str
    engine_id:             Optional[str]  = "main"
    tool_ids:              Optional[List[str]] = None
    system_prompt:         Optional[str]       = None
    template_ids:          Optional[List[str]] = None
    use_mcp_discovery:     Optional[bool]      = False
    global_search_enabled: Optional[bool]      = False

class StreamRequest(BaseModel):
    message:    str
    session_id: str
    provider:   Optional[str] = None
    attachments: Optional[List[str]] = None


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
    """Compile and activate a custom agent with live SSE progress streaming (Unified)."""
    return StreamingResponse(
        load_agent_generator(
            model_path=req.model_path,
            provider=req.provider,
            agent_id=req.agent_id,
            agent_display_name=req.agent_display_name,
            tool_ids=req.tool_ids,
            template_ids=req.template_ids,
            system_prompt=req.system_prompt,
            guardrails=req.guardrails,
            use_mcp_discovery=req.use_mcp_discovery,
            global_search_enabled=req.global_search_enabled,
            workflow_ids=req.workflow_ids,
            engine_id=req.engine_id or "main",
        ),
        media_type="text/event-stream"
    )

@router.post("/fleet/deploy")
async def fleet_deploy(req: FleetDeployRequest):
    """Deploy or reconfigure an inference node (Engine Only)."""
    return StreamingResponse(
        vllm_manager.deploy_engine_node(
            model_path=req.model_path,
            engine_id=req.engine_id,
            gpu_memory_utilization=req.gpu_memory_utilization,
            max_model_len=req.max_model_len,
            quantization=req.quantization
        ),
        media_type="text/event-stream"
    )

@router.post("/agent/connect")
async def agent_connect(req: AgentConnectRequest):
    """Bind a persona to an existing engine node (Agent Only)."""
    # This calls the load_agent logic but skips engine deployment if already ready
    return StreamingResponse(
        load_agent_generator(
            agent_id=req.agent_id,
            engine_id=req.engine_id,
            tool_ids=req.tool_ids,
            system_prompt=req.system_prompt,
            template_ids=req.template_ids,
            use_mcp_discovery=req.use_mcp_discovery,
            global_search_enabled=req.global_search_enabled,
            skip_engine_deploy=True # New flag to bypass vLLM check
        ),
        media_type="text/event-stream"
    )

@router.post("/fleet/sync")
async def fleet_sync():
    """Syncs the registry with Docker state and prunes ghost containers."""
    vllm_manager.sync_registry_with_docker()
    vllm_manager.prune_ghost_containers()
    return {"status": "success", "message": "Fleet synchronized and ghost containers pruned."}

@router.post("/fleet/terminate/{engine_id}")
async def fleet_terminate(engine_id: str):
    """Hard shutdown of an inference node."""
    return vllm_manager.terminate_engine_node(engine_id)

@router.get("/fleet/logs/{engine_id}")
async def fleet_logs(engine_id: str):
    """Streams live container logs via SSE."""
    container_name = f"vllm-server-{engine_id}"
    return StreamingResponse(
        vllm_manager.stream_container_logs(container_name),
        media_type="text/event-stream"
    )

@router.get("/fleet/status/stream")
async def fleet_status_stream():
    """SSE stream for real-time fleet health (VRAM, Node states with probing)."""
    async def event_generator():
        while True:
            try:
                payload = vllm_manager.get_cached_status()
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def get_system_vram_gb() -> float:
    """Detect total VRAM on the host using nvidia-smi."""
    try:
        import subprocess
        # Query total memory for all GPUs
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8",
            stderr=subprocess.DEVNULL
        )
        vrams = [float(x.strip()) for x in output.strip().split("\n") if x.strip()]
        return sum(vrams) / 1024.0 # MB -> GB
    except Exception:
        # Fallback to a safe default if nvidia-smi is unavailable
        return 8.0

@router.get("/config")
async def get_config():
    """
    Returns available models, agent definitions, and system hardware info for the UI.
    All model dicts include standardized type metadata (is_llm, modality, tasks) so
    the Agent Gateway can filter to text/chat models without guessing by display_group.
    """
    # Canonical text-generation providers
    LLM_PROVIDERS = {'vllm', 'openrouter', 'groq', 'gemini', 'huggingface', 'mock', 'local_llama'}

    try:
        from common_lib.modules.ai_models.container import AIModelsContainer
        container = AIModelsContainer()
        models = container.registry_service.list_models()

        from app.core.common_lib_integration import common_memory
        agents = common_memory.list_agent_definitions()

        ui_models = []
        for m in models:
            modality = getattr(m, 'modality', None) or 'text'
            tasks    = list(getattr(m, 'tasks', None) or [])
            provider = getattr(m, 'provider', None) or 'unknown'
            is_llm   = bool(
                provider in LLM_PROVIDERS or
                (modality == 'text' and any(t in tasks for t in ('text_generation', 'chat')))
            )
            m_dict = m.model_dump()
            m_dict['path']     = m.id
            m_dict['type']     = provider
            m_dict['modality'] = modality
            m_dict['tasks']    = tasks
            m_dict['is_llm']   = is_llm
            m_dict.setdefault('display_group', provider.capitalize())
            ui_models.append(m_dict)

        return {
            'models': ui_models,
            'agents': agents,
            'system_vram_gb': get_system_vram_gb(),
            'available_provisioning_engines': vllm_manager.discover_engines()
        }
    except Exception as exc:
        logger.error('Failed to fetch runtime config: %s', exc)
        return {'models': [], 'agents': [], 'system_vram_gb': 8.0, 'available_provisioning_engines': []}


@router.get("/session")
async def get_session():
    """Return the currently active agent session metadata."""
    sess  = get_active_session()

    if sess.get("status") == "inactive":
        return {"status": "inactive"}

    agent = get_master_agent()
    info = {**sess}
    if agent and hasattr(agent, "model_provider") and agent.model_provider:
        info.update(agent.model_provider.get_info())
    return info


@router.post("/clear_session")
async def clear_session(req: ClearSessionRequest):
    """
    Clears the current session.
    hard_reset=true  -> Restarts the vLLM container.
    hard_reset=false -> Wipes LangGraph checkpoints (history).
    """
    try:
        if req.hard_reset:
            sess = get_active_session()
            if sess.get("provider") == "vllm" and sess.get("model"):
                logger.info("[Routes] Triggering Hard Reset for model: %s", sess["model"])
                return StreamingResponse(
                    load_agent_generator(
                        model_path=sess["model"],
                        provider="vllm"
                    ),
                    media_type="text/event-stream"
                )
            else:
                return {"status": "error", "message": "No active vLLM model to reset."}
        else:
            clear_checkpointer()
            return {"status": "success", "message": "Session history cleared."}
    except Exception as exc:
        logger.error("Failed to clear session: %s", exc)
        return {"status": "error", "message": str(exc)}


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


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to the server and return its local path."""
    try:
        upload_dir = Path("assets/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = upload_dir / file.filename
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "status": "success",
            "filename": file.filename,
            "local_path": str(file_path.absolute()),
            "url": f"/assets/uploads/{file.filename}"
        }
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        return {"status": "error", "message": str(exc)}


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
