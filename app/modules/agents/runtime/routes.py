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
    GET  /commands                 — list registry slash commands
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

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlmodel import Session, select, func
from app.modules.database.service.connection import get_session as get_db_session
from app.modules.agents.runtime.session_models import (
    AgentSession,
    AgentConversation,
    AgentMessage,
)
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
from common_lib.modules.ai_models.llm.vllm_fleet_manager import (
    vllm_fleet as vllm_manager,
)
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from app.modules.agents.runtime.utils.logging import get_logger

logger = get_logger(__name__)

# API keys are now handled via environment variables/config by the base library.

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DeployRequest(BaseModel):
    model_path: Optional[str] = None
    provider: Optional[str] = None
    agent_id: Optional[str] = "master_agent"
    agent_display_name: Optional[str] = "Master Agent"
    tool_ids: Optional[List[str]] = None
    template_ids: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    guardrails: Optional[List] = None
    use_mcp_discovery: Optional[bool] = False
    global_search_enabled: Optional[bool] = False
    workflow_ids: Optional[List[str]] = None
    engine_id: Optional[str] = None  # Fleet node to connect; None = smart-fallback


class FleetDeployRequest(BaseModel):
    model_path: str
    engine_id: Optional[str] = "main"
    gpu_memory_utilization: Optional[float] = 0.85
    max_model_len: Optional[int] = 4096
    quantization: Optional[str] = "none"


class AgentConnectRequest(BaseModel):
    agent_id: str
    engine_id: Optional[str] = "main"
    tool_ids: Optional[List[str]] = None
    system_prompt: Optional[str] = None
    template_ids: Optional[List[str]] = None
    use_mcp_discovery: Optional[bool] = False
    global_search_enabled: Optional[bool] = False


class StreamRequest(BaseModel):
    message: str
    session_id: str
    provider: Optional[str] = None
    attachments: Optional[List[str]] = None
    decision: Optional[Dict[str, Any]] = None  # HITL decision (approve/reject/modify)


class StateUpdateRequest(BaseModel):
    history: Optional[str] = None
    intermediate_steps: Optional[list] = None
    structured_state: Optional[dict] = None
    hints: Optional[list] = None
    operational_metadata: Optional[dict] = None


class ClearSessionRequest(BaseModel):
    hard_reset: bool = False


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
        media_type="text/event-stream",
    )


@router.post("/fleet/deploy")
async def fleet_deploy(req: FleetDeployRequest):
    """Deploy or reconfigure an inference node (Engine Only)."""
    from common_lib.modules.ai_models.container import AIModelsContainer

    mirror = AIModelsContainer().mirror_service

    # Always use vllm.compose.yml (ignore compose_file from UI)
    return StreamingResponse(
        vllm_manager.deploy_engine_node(
            model_path=req.model_path,
            engine_id=req.engine_id,
            gpu_memory_utilization=req.gpu_memory_utilization,
            max_model_len=req.max_model_len,
            quantization=req.quantization,
            compose_file="resources/vllm.compose.yml",
            mirror_service=mirror,
        ),
        media_type="text/event-stream",
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
            skip_engine_deploy=True,  # New flag to bypass vLLM check
        ),
        media_type="text/event-stream",
    )


@router.post("/fleet/sync")
async def fleet_sync():
    """Syncs the registry with Docker state and prunes ghost containers."""
    vllm_manager.sync_registry_with_docker()
    vllm_manager.prune_ghost_containers()
    return {
        "status": "success",
        "message": "Fleet synchronized and ghost containers pruned.",
    }


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
        media_type="text/event-stream",
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
            stderr=subprocess.DEVNULL,
        )
        vrams = [float(x.strip()) for x in output.strip().split("\n") if x.strip()]
        return sum(vrams) / 1024.0  # MB -> GB
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
    LLM_PROVIDERS = {
        "vllm",
        "openrouter",
        "groq",
        "gemini",
        "huggingface",
        "mock",
        "local_llama",
    }

    try:
        from common_lib.modules.ai_models.container import AIModelsContainer

        container = AIModelsContainer()
        # Run health check to update is_local status before listing
        container.health_monitor.verify_all_models()
        models = container.registry_service.list_models()

        from app.core.common_lib_integration import common_memory

        agents = common_memory.list_agent_definitions()

        # vLLM-supported architectures
        VLLM_SUPPORTED_ARCHS = {
            "llama",
            "mistral",
            "qwen2",
            "qwen3",
            "gemma",
            "gemma2",
            "gemma3",
            "gemma4",
            "phi3",
            "phi4",
            "deepseek",
            "mixtral",
            "starcoder",
            "falcon",
            "olmo",
            "cohere",
            "dbrx",
            "arctic",
            "internlm",
            "minicpm",
            "chatglm",
            "baichuan",
            "bloom",
            "mpt",
            "gpt2",
            "opt",
            "gptj",
            "gpt_neox",
            "gpt_bigcode",
            "stablelm",
        }

        from common_lib.modules.ai_models.domain.enums import ModelStatus

        ui_models = []
        for m in models:
            # Skip models that are not fully downloaded/local
            # Based on user feedback: hide non-completed models
            if (
                not getattr(m, "is_local", False)
                or getattr(m, "status", None) != ModelStatus.COMPLETED
            ):
                continue

            modality = getattr(m, "modality", None) or "text"
            tasks = list(getattr(m, "tasks", None) or [])
            provider = getattr(m, "provider", None) or "unknown"

            # Refined LLM detection: Text or Multimodal with Chat/Gen tasks
            is_llm = bool(
                provider in LLM_PROVIDERS
                or (
                    modality in ("text", "multimodal")
                    and any(
                        t in tasks
                        for t in ("text_generation", "chat", "multimodal_chat")
                    )
                )
            )

            # Determine engine support
            quant = (getattr(m, "quantization", None) or "").lower()
            is_gguf = (
                quant == "gguf" or "gguf" in (getattr(m, "file_path", "") or "").lower()
            )
            is_awq = (
                quant == "awq" or "awq" in (getattr(m, "file_path", "") or "").lower()
            )
            is_fp16 = quant in ("none", "half", "float16", "bfloat16")

            # Check if vLLM can serve this model
            vllm_supported = m.is_local and (is_gguf or is_awq or is_fp16)

            # Determine model capabilities
            model_capabilities = list(getattr(m, "capabilities", None) or [])
            model_modality = (getattr(m, "modality", None) or "text").lower()
            # If no explicit vision capability, check modality and task
            has_vision = (
                "vision" in model_capabilities
                or "image_input" in model_capabilities
                or model_modality in ("multimodal", "image")
                or any(
                    t in tasks
                    for t in (
                        "multimodal_chat",
                        "image_to_text",
                        "visual_question_answering",
                    )
                )
            )
            if not has_vision and m.is_local:
                model_capabilities.append("text_only")

            # Determine the engine label
            if is_gguf:
                engine = "vllm-gguf"
            elif is_awq:
                engine = "vllm-awq"
            elif is_fp16:
                engine = "vllm"
            else:
                engine = "unknown"

            m_dict = m.model_dump()
            m_dict["path"] = m.id
            m_dict["type"] = provider
            m_dict["modality"] = modality
            m_dict["tasks"] = tasks
            m_dict["is_llm"] = is_llm
            m_dict["engine"] = engine
            m_dict["vllm_supported"] = vllm_supported
            m_dict["capabilities"] = model_capabilities
            m_dict["repo_id"] = getattr(m, "repo_id", None)
            m_dict.setdefault("display_group", provider.capitalize())

            # Show all models for now - fleet check not working correctly
            m_dict["_isLive"] = True

            ui_models.append(m_dict)

        return {
            "models": ui_models,
            "agents": agents,
            "system_vram_gb": get_system_vram_gb(),
            "available_provisioning_engines": vllm_manager.discover_engines(),
        }
    except Exception as exc:
        logger.error("Failed to fetch runtime config: %s", exc)
        return {
            "models": [],
            "agents": [],
            "system_vram_gb": 8.0,
            "available_provisioning_engines": [],
        }


@router.get("/session")
async def get_session():
    """Return the currently active agent session metadata."""
    import logging

    logger = logging.getLogger(__name__)

    sess = get_active_session()

    if sess.get("status") == "inactive":
        return {"status": "inactive"}

    agent = get_master_agent()
    info = {**sess}
    if agent and hasattr(agent, "model_provider") and agent.model_provider:
        info.update(agent.model_provider.get_info())

    # Include full agent definition from active_session (set during deployment)
    if "full_definition" in sess:
        logger.info("[get_session] Using full_definition from active_session")
        info["agent_definition"] = sess["full_definition"]

    # Include system prompt
    if "system_prompt" in sess:
        info["system_prompt"] = sess["system_prompt"]

    # Include thread_id for LangGraph state lookup (this is the LangGraph thread ID, not DB session ID)
    if "session_id" in sess:
        info["thread_id"] = sess["session_id"]

    logger.info(f"[get_session] Response keys: {list(info.keys())}")
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
                logger.info(
                    "[Routes] Triggering Hard Reset for model: %s", sess["model"]
                )
                return StreamingResponse(
                    load_agent_generator(model_path=sess["model"], provider="vllm"),
                    media_type="text/event-stream",
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
        stream_agent_generator(req.message, req.session_id, decision=req.decision),
        media_type="text/event-stream",
    )


@router.get("/session_state/{session_id}")
async def read_session_state(
    session_id: str, thread_id: str = None, db: Session = Depends(get_db_session)
):
    """Read the full LangGraph checkpoint state for a thread.

    Use thread_id query param to specify the LangGraph thread ID.
    If not provided, uses session_id as fallback.
    """
    agent = get_master_agent()
    # actual_thread_id logic remains for graph state, but we also fetch DB messages
    actual_thread_id = thread_id or session_id

    # 1. Try to get LangGraph state Values
    v = {}
    checkpoint_id = "initial"
    if agent and agent.graph:
        try:
            state = agent.graph.get_state(
                {"configurable": {"thread_id": actual_thread_id}}
            )
            v = state.values
            checkpoint_id = str(
                state.config.get("configurable", {}).get("checkpoint_id", "initial")
            )
        except Exception:
            pass  # Graph state might be empty for new sessions

    # 2. Fetch last 50 messages from DB for the session (ChatGPT style flat stream)
    # Join Message -> Conversation -> Session to ensure we get messages for this session
    messages_query = (
        select(AgentMessage)
        .join(AgentConversation)
        .where(AgentConversation.session_id == session_id)
        .order_by(AgentMessage.created_at.desc())
        .limit(50)
    )
    db_messages = db.exec(messages_query).all()
    # Reverse to get chronological order (ASC)
    db_messages = list(reversed(db_messages))

    # Convert to JSON serializable format
    formatted_messages = []
    for m in db_messages:
        formatted_messages.append(
            {
                "id": m.id,
                "role": m.role,  # assistant/user
                "content": m.content,
                "reasoning": m.reasoning,
                "trace": json.loads(m.trace_events) if m.trace_events else [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "conversation_id": m.conversation_id,
            }
        )

    # Check if more messages exist
    has_more = False
    if len(db_messages) == 50:
        first_msg_id = db_messages[0].id
        has_more_query = (
            select(func.count(AgentMessage.id))
            .join(AgentConversation)
            .where(AgentConversation.session_id == session_id)
            .where(AgentMessage.created_at < db_messages[0].created_at)
        )
        has_more = db.exec(has_more_query).one() > 0

    # 3. Get session metadata for hydration
    session = db.get(AgentSession, session_id)
    model_id = session.model_id if session else None
    agent_id = session.agent_id if session else None

    return {
        "session_id": session_id,
        "thread_id": actual_thread_id,
        "model_id": model_id,
        "agent_id": agent_id,
        "history": v.get("conversation_history", ""),
        "messages": formatted_messages,
        "has_more": has_more,
        "intermediate_steps": v.get("intermediate_steps", []),
        "structured_state": v.get("structured_state", {}),
        "hints": v.get("hints", []),
        "operational_metadata": v.get("operational_metadata", {}),
        "last_input": v.get("input", ""),
        "checkpoint_id": checkpoint_id,
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
            "url": f"/assets/uploads/{file.filename}",
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
    if req.history is not None:
        updates["conversation_history"] = req.history
    if req.intermediate_steps is not None:
        updates["intermediate_steps"] = req.intermediate_steps
    if req.structured_state is not None:
        updates["structured_state"] = req.structured_state
    if req.hints is not None:
        updates["hints"] = req.hints
    if req.operational_metadata is not None:
        updates["operational_metadata"] = req.operational_metadata

    try:
        agent.graph.update_state({"configurable": {"thread_id": session_id}}, updates)
        return {"status": "success", "message": "State updated"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.get("/available_tools")
async def available_tools():
    """List all available tools grouped by category."""
    from app.core.common_lib_integration import common_memory

    em = get_engine_manager()
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
        [
            {"id": cat, "name": cat.replace("_", " ").title(), "tools": tools}
            for cat, tools in groups.items()
        ],
        key=lambda x: x["name"],
    )


@router.get("/commands")
async def list_commands():
    """List all available slash commands from the registry."""
    from app.core.common_lib_integration import common_memory

    try:
        commands = common_memory.list_command_definitions()
        return [
            {
                "id": c["id"],
                "name": c["name"],
                "description": c["description"],
                "trigger": c.get("trigger") or f"/{c['id']}",
                "documentation": c.get("documentation", ""),
            }
            for c in commands
        ]
    except Exception as exc:
        logger.error("Command list failed: %s", exc)
        return []


@router.get("/available_workflows")
async def available_workflows():
    """List all available workflows grouped by category."""
    from app.core.common_lib_integration import common_memory

    try:
        wfs = common_memory.list_workflow_definitions()
        groups: Dict[str, List] = {}
        for w in wfs:
            defn = w.get("definition", {})
            cat = defn.get("category") or defn.get("group") or "General"
            name = (
                defn.get("name") or w.get("name") or w["id"].replace("_", " ").title()
            )
            groups.setdefault(cat, []).append(
                {
                    "id": w["id"],
                    "name": name,
                    "description": defn.get("description", "Workflow."),
                    "category": cat.replace("_", " ").title(),
                }
            )
        return sorted(
            [
                {"id": f"wf_{c.lower()}", "name": f"{c} (Workflows)", "items": items}
                for c, items in groups.items()
            ],
            key=lambda x: x["name"],
        )
    except Exception as exc:
        logger.error("Workflow list failed: %s", exc)
        return []


@router.get("/available_loops")
async def available_loops():
    """List all valid executable agentic loops from DB.

    Filter workflows where definition.workflow_type = executable_graph
    """
    from app.core.common_lib_integration import common_memory

    try:
        all_wfs = common_memory.list_workflow_definitions()
        loops = []

        for wf in all_wfs:
            defn = wf.get("definition", {})
            workflow_type = defn.get("workflow_type", "")

            if workflow_type == "executable_graph":
                loops.append(
                    {
                        "id": wf.get("id"),
                        "name": defn.get("name", wf["id"].replace("_", " ").title()),
                        "description": defn.get("description", "Agentic loop."),
                        "workflow_type": workflow_type,
                    }
                )

        return loops
    except Exception as e:
        logger.error(f"Available loops failed: {e}")
        return []


@router.get("/gemini_models")
async def gemini_models():
    """Return the live list of available Gemini models."""
    em = get_engine_manager()
    if em and em.main_llm and hasattr(em.main_llm, "list_models"):
        return em.main_llm.list_models()
    try:
        from common_lib.modules.ai_models.llm.gemini import GeminiProvider
        from common_lib.modules.orchestration.inference.schemas import (
            ModelConfiguration,
        )

        p = GeminiProvider(
            ModelConfiguration(
                provider_id="temp", provider_type="gemini", model_name="gemini-1.5-pro"
            )
        )
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
