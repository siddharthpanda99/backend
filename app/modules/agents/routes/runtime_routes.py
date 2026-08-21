"""
agents/runtime/routes.py — Thin API layer delegating to common_lib services.

Registered at: /api/v1/agents/runtime/
"""

from __future__ import annotations

import json
import asyncio
import shutil
import logging
from typing import Any, Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from common_lib.modules.data_storage.database.connection import (
    get_session as get_db_session,
)
from app.modules.agents.runtime.session_models import (
    AgentSession,
    AgentConversation,
    AgentMessage,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.modules.agents.runtime.core import (
    load_agent_generator,
    get_master_agent,
    get_engine_manager,
    get_active_session,
    set_human_feedback_mode,
    clear_checkpointer,
    stream_agent_generator,
)
from common_lib.modules.ai_models.llm.vllm_fleet_manager import (
    vllm_fleet as vllm_manager,
)
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from app.modules.agents.runtime.utils.logging import get_logger

from common_lib.modules.agents.runtime.service import (
    build_model_config,
    list_available_tools as _list_tools,
    list_available_workflows as _list_workflows,
    list_available_loops as _list_loops,
    list_commands as _list_commands,
    list_gemini_models as _list_gemini,
)

logger = get_logger(__name__)

router = APIRouter()


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
    engine_id: Optional[str] = None


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
    decision: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None
    system_prompt: Optional[str] = None
    model_path: Optional[str] = None
    loop_id: Optional[str] = None
    # ── Reasoning Mode ──────────────────────────────────────────
    reasoning_mode: Optional[bool] = False
    reasoning_plan_id: Optional[str] = None
    # ``brief`` (default) | ``final`` | ``detailed`` — verbosity of the
    # per-step ``reasoning`` SSE events.
    reasoning_level: Optional[str] = "brief"
    # ── Comprehensive chat settings object ──────────────────────
    # Optional inline settings object. When omitted, the persisted per-
    # session chat settings are used (see GET/PUT /settings). Inline values
    # win over persisted ones for this single turn.
    settings: Optional[Dict[str, Any]] = None


class StateUpdateRequest(BaseModel):
    history: Optional[str] = None
    intermediate_steps: Optional[list] = None
    structured_state: Optional[dict] = None
    hints: Optional[list] = None
    operational_metadata: Optional[dict] = None


class ClearSessionRequest(BaseModel):
    hard_reset: bool = False


class HITLModeRequest(BaseModel):
    enabled: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/set_human_feedback_mode")
async def set_hitl_mode(req: HITLModeRequest):
    set_human_feedback_mode(req.enabled)
    return {"status": "success", "human_feedback_mode": req.enabled}


# ── Comprehensive chat settings object ──────────────────────────────────────
# GET/PUT/DELETE the full per-session chat settings object so the same
# configuration is identically available via UI, API and CLI.


@router.get("/settings/{session_id}")
async def get_chat_settings(session_id: str):
    """Get the full chat settings object for a session (or defaults)."""
    from common_lib.modules.agents.chat_settings.service import (
        get_chat_settings_service,
    )

    return get_chat_settings_service().get_settings(session_id)


@router.put("/settings/{session_id}")
async def put_chat_settings(session_id: str, req: Dict[str, Any]):
    """Update (merge) the chat settings object for a session.

    Body: a partial ChatSettings payload — only the provided fields change.
    Returns the merged, persisted settings object.
    """
    from common_lib.modules.agents.chat_settings.schemas import ChatSettingsUpdate
    from common_lib.modules.agents.chat_settings.service import (
        get_chat_settings_service,
    )

    update = ChatSettingsUpdate(**dict(req or {}))
    result = get_chat_settings_service().set_settings(session_id, update)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.delete("/settings/{session_id}")
async def reset_chat_settings(session_id: str):
    """Reset a session's chat settings object to the defaults."""
    from common_lib.modules.agents.chat_settings.service import (
        get_chat_settings_service,
    )

    return get_chat_settings_service().reset_settings(session_id)


@router.post("/deploy")
async def deploy(req: DeployRequest):
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
    from common_lib.modules.ai_models.container import AIModelsContainer

    mirror = AIModelsContainer().mirror_service
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
    return StreamingResponse(
        load_agent_generator(
            agent_id=req.agent_id,
            engine_id=req.engine_id,
            tool_ids=req.tool_ids,
            system_prompt=req.system_prompt,
            template_ids=req.template_ids,
            use_mcp_discovery=req.use_mcp_discovery,
            global_search_enabled=req.global_search_enabled,
            skip_engine_deploy=True,
        ),
        media_type="text/event-stream",
    )


@router.post("/fleet/sync")
async def fleet_sync():
    vllm_manager.sync_registry_with_docker()
    vllm_manager.prune_ghost_containers()
    return {
        "status": "success",
        "message": "Fleet synchronized and ghost containers pruned.",
    }


@router.post("/fleet/terminate/{engine_id}")
async def fleet_terminate(engine_id: str):
    return vllm_manager.terminate_engine_node(engine_id)


@router.get("/fleet/logs/{engine_id}")
async def fleet_logs(engine_id: str):
    container_name = f"vllm-server-{engine_id}"
    return StreamingResponse(
        vllm_manager.stream_container_logs(container_name),
        media_type="text/event-stream",
    )


@router.get("/fleet/status/stream")
async def fleet_status_stream():
    async def event_generator():
        while True:
            try:
                payload = vllm_manager.get_cached_status()
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/config")
async def get_config():
    from app.core.common_lib_integration import common_memory

    try:
        return build_model_config(
            common_memory=common_memory,
            vllm_manager=vllm_manager,
        )
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
    sess = get_active_session()
    if sess.get("status") == "inactive":
        return {"status": "inactive"}

    agent = get_master_agent()
    info = {**sess}
    if agent and hasattr(agent, "model_provider") and agent.model_provider:
        info.update(agent.model_provider.get_info())

    if "full_definition" in sess:
        info["agent_definition"] = sess["full_definition"]
    if "system_prompt" in sess:
        info["system_prompt"] = sess["system_prompt"]
    if "session_id" in sess:
        info["thread_id"] = sess["session_id"]

    return info


@router.post("/clear_session")
async def clear_session(req: ClearSessionRequest):
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
    # Merge the comprehensive chat settings object into this turn: persisted
    # per-session settings first, then the inline (per-request) overrides.
    from common_lib.modules.agents.chat_settings.service import (
        apply_settings_to_request,
        get_chat_settings_service,
    )

    svc = get_chat_settings_service()
    persisted = svc.get_settings(req.session_id) if svc else {}
    merged = apply_settings_to_request(persisted, req.settings or {})
    # The explicit StreamRequest fields ALWAYS win over the settings object
    # (both persisted and inline). ``is not None`` guards let callers turn a
    # persisted ``true`` off or downgrade a persisted level explicitly.
    if req.reasoning_mode is not None:
        merged["reasoning_mode"] = bool(req.reasoning_mode)
    if req.reasoning_plan_id is not None:
        merged["reasoning_plan_id"] = req.reasoning_plan_id
    if req.reasoning_level is not None:
        merged["reasoning_level"] = req.reasoning_level

    return StreamingResponse(
        stream_agent_generator(
            req.message,
            req.session_id,
            decision=req.decision,
            # Explicit request fields take precedence over persisted settings
            # (persisted defaults like ``agent_id="master_agent"`` must never
            # silently override an explicit caller value).
            agent_id=req.agent_id or merged.get("agent_id"),
            system_prompt=req.system_prompt or merged.get("system_prompt"),
            model_path=req.model_path,
            provider=req.provider or merged.get("provider"),
            loop_id=req.loop_id,
            reasoning_mode=bool(merged.get("reasoning_mode", False)),
            reasoning_plan_id=req.reasoning_plan_id,
            reasoning_level=str(merged.get("reasoning_level") or "brief"),
        ),
        media_type="text/event-stream",
    )


from common_lib.modules.agents.runtime import (
    read_session_state as _read_session_state,
    update_session_state as _update_session_state,
)


@router.get("/session_state/{session_id}")
async def read_session_state_endpoint(
    session_id: str, thread_id: str = None, db: Session = Depends(get_db_session)
):
    """Read the full LangGraph checkpoint state for a thread, plus DB messages."""
    try:
        return _read_session_state(db, session_id, thread_id)
    except Exception as e:
        import traceback

        logger.error(f"session_state error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
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

    res = _update_session_state(session_id, updates)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.get("/available_tools")
async def available_tools():
    em = get_engine_manager()
    return _list_tools(BUILTIN_TOOL_REGISTRY, em)


@router.get("/commands")
async def list_commands():
    from app.core.common_lib_integration import common_memory

    return _list_commands(common_memory)


@router.get("/available_workflows")
async def available_workflows():
    from app.core.common_lib_integration import common_memory

    return _list_workflows(common_memory)


@router.get("/available_loops")
async def available_loops():
    from app.core.common_lib_integration import common_memory

    return _list_loops(common_memory)


@router.get("/gemini_models")
async def gemini_models():
    em = get_engine_manager()
    return _list_gemini(em)


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
