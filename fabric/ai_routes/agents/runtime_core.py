"""Fabric-side agent runtime core — home of the agent-serving helpers.

Wraps ``common_lib.modules.orchestration.agent_loader`` (the common_lib
home of the master-agent / engine-manager / active-session state) and
provides the fabric ports of the Backend-app-side helpers used by the
agents runtime routes:

- ``load_agent_generator`` — port of
  ``Backend/app/modules/agents/runtime/core/agent_loader.py`` (vLLM deploy
  status stream + agent compilation status).
- ``stream_agent_generator`` — fabric adapter that streams the master
  agent's execution events as SSE ``data:`` lines. The Backend version
  lives in ``Backend/app/modules/agents/runtime/core/streaming.py`` and
  formats the full LangGraph event taxonomy; the fabric adapter streams
  the master agent's graph events and is a Phase-2 port target.

Agent executors stay Backend-app-side for now (``ensure_agent_executors_registered``
is a no-op on the fabric).
"""

from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator, Optional


def _cl_loader():
    # Lazy: importing the orchestration agent_loader pulls the integration
    # stack, which needs sqlmodel — the fabric venv stays importable without it.
    from common_lib.modules.orchestration import agent_loader as _mod

    return _mod


def get_engine_manager() -> Any | None:
    """Port of the Backend app agent_loader accessor."""
    return _cl_loader().get_engine_manager()


def get_master_agent() -> Any | None:
    """Port of the Backend app agent_loader accessor."""
    return _cl_loader().get_master_agent()


def get_active_session() -> dict[str, Any]:
    """Port of the Backend app agent_loader accessor."""
    return _cl_loader().get_active_session()


def set_human_feedback_mode(enabled: bool) -> None:
    """Port of the Backend app agent_loader accessor."""
    return _cl_loader().set_human_feedback_mode(enabled)


def clear_checkpointer():
    """Port of the Backend app agent_loader accessor."""
    return _cl_loader().clear_checkpointer()


def get_system_vram_gb() -> float:
    return _cl_loader().get_system_vram_gb()


def get_vram_usage() -> dict[str, Any]:
    return _cl_loader().get_vram_usage()


# Job/executor kinds (values from Backend/app/modules/agents/runtime/job_executors.py).
AGENT_TURN_KIND = "agent.turn"
AGENT_TURN_DEVICE = "cpu"
AGENT_TURN_TIMEOUT = 600.0

logger = logging.getLogger(__name__)


def ensure_agent_executors_registered() -> bool:
    """The fabric control plane has no agent job executors yet (see module docstring)."""
    return False


def load_agent(
    model_path: Optional[str] = None,
    provider: str = "vllm",
    agent_id: str = "master_agent",
    agent_display_name: str = "Master Agent",
    tool_ids: Optional[list] = None,
    system_prompt: Optional[str] = None,
    guardrails: Optional[list] = None,
    use_mcp_discovery: bool = False,
    global_search_enabled: bool = False,
    workflow_ids: Optional[list] = None,
    preload: bool = True,
    engine_id: str = "main",
    **kwargs: Any,
) -> Any:
    """Compile and wire a custom agent (delegates to common_lib orchestration)."""
    return _cl_loader().load_agent(
        model_path=model_path,
        provider=provider,
        agent_id=agent_id,
        agent_display_name=agent_display_name,
        tool_ids=tool_ids,
        system_prompt=system_prompt,
        guardrails=guardrails,
        use_mcp_discovery=use_mcp_discovery,
        global_search_enabled=global_search_enabled,
        workflow_ids=workflow_ids,
        preload=preload,
        engine_id=engine_id,
    )


def load_agent_generator(
    model_path: Optional[str] = None,
    provider: str = "vllm",
    agent_id: str = "master_agent",
    agent_display_name: str = "Master Agent",
    tool_ids: Optional[list] = None,
    system_prompt: Optional[str] = None,
    guardrails: Optional[list] = None,
    use_mcp_discovery: bool = False,
    global_search_enabled: bool = False,
    workflow_ids: Optional[list] = None,
    template_ids: Optional[list] = None,
    preload: bool = True,
    skip_engine_deploy: bool = False,
    engine_id: str = "main",
    auto_deploy_llm: bool = False,
    exhaustive_discovery: bool = False,
):
    """Generator version of ``load_agent`` for streaming deployment status.

    Yields strings formatted for SSE: ``data: <payload>\\n\\n``.
    Port of the Backend app agent_loader; the vLLM deploy path uses the
    common_lib AI models container + fleet manager.
    """
    if provider == "vllm" and model_path and auto_deploy_llm:
        from common_lib.modules.ai_models.container import AIModelsContainer
        from common_lib.modules.ai_models.llm.vllm_fleet_manager import (
            vllm_fleet as vllm_manager,
        )

        container = AIModelsContainer()
        model_meta = container.repository.get_model(model_path)

        if not model_meta or not model_meta.file_path:
            yield f"data: STATUS:ERROR:Model '{model_path}' not found in registry.\n\n"
            return

        def run_deploy(gpu_util_override=None, max_len_override=None):
            return vllm_manager.deploy_engine_node(
                model_path=model_meta.file_path,
                engine_id=engine_id,
                quantization=model_meta.quantization,
                gpu_memory_utilization=(
                    gpu_util_override
                    if gpu_util_override is not None
                    else model_meta.gpu_memory_utilization
                ),
                max_model_len=(
                    max_len_override if max_len_override is not None else model_meta.max_model_len
                ),
                trust_remote_code=model_meta.trust_remote_code,
                mirror_service=container.mirror_service,
            )

        # PASS 1: Attempt with registry settings
        fallback_required = False
        for update in run_deploy():
            if "STATUS:ERROR" in update and any(x in update for x in ["OOM", "memory", "VRAM"]):
                fallback_required = True
                break
            yield f"data: {update}\n\n"

        # PASS 2: Fallback if needed
        if fallback_required:
            SAFE_UTIL = 0.85
            SAFE_LEN = 2048
            yield (
                f"data: STATUS:RETRYING:Memory limit reached. Retrying with Safe "
                f"Defaults ({SAFE_UTIL} Util / {SAFE_LEN} Context)...\n\n"
            )
            success = False
            for update in run_deploy(gpu_util_override=SAFE_UTIL, max_len_override=SAFE_LEN):
                if "STATUS:READY" in update:
                    success = True
                yield f"data: {update}\n\n"
            if success:
                try:
                    model_meta.gpu_memory_utilization = SAFE_UTIL
                    model_meta.max_model_len = SAFE_LEN
                    container.repository.register_model(model_meta)
                    yield (
                        f"data: LOG:Registry updated with safe memory settings "
                        f"for {model_path}.\n\n"
                    )
                except Exception as ex:
                    yield f"data: LOG:Failed to persist safe settings: {str(ex)}\n\n"
    else:
        yield "data: STATUS:STARTING:Configuring non-vLLM provider...\n\n"

    # Final compilation
    start_time = time.time()
    yield "data: STATUS:LOADING:Starting agent compilation...\n\n"

    try:
        logger.info("[AgentLoader] Starting load_agent for %s...", agent_id)
        yield "data: STATUS:INITIALIZING:Syncing registries and loading engine...\n\n"

        load_agent(
            model_path=model_path,
            provider=provider,
            agent_id=agent_id,
            agent_display_name=agent_display_name,
            tool_ids=tool_ids,
            system_prompt=system_prompt,
            guardrails=guardrails,
            use_mcp_discovery=use_mcp_discovery,
            global_search_enabled=global_search_enabled,
            workflow_ids=workflow_ids,
            preload=preload,
            skip_engine_deploy=skip_engine_deploy,
            engine_id=engine_id,
            auto_deploy_llm=auto_deploy_llm,
            exhaustive_discovery=exhaustive_discovery,
        )
        duration = time.time() - start_time
        ready_payload = f"STATUS:READY:Agent successfully deployed in {duration:.2f}s."
        yield f"data: {ready_payload}\n\n"
    except Exception as e:
        error_msg = f"Compilation failed: {str(e)}"
        yield f"data: STATUS:ERROR:{error_msg}\n\n"


async def stream_agent_generator(
    message: str,
    session_id: str,
    decision: Optional[dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    system_prompt: Optional[str] = None,
    model_path: Optional[str] = None,
    provider: Optional[str] = None,
    loop_id: Optional[str] = None,
    reasoning_mode: bool = False,
    reasoning_plan_id: Optional[str] = None,
    reasoning_level: str = "brief",
) -> AsyncGenerator[str, None]:
    """Fabric streaming adapter over the master agent.

    The Backend version lives in
    ``Backend/app/modules/agents/runtime/core/streaming.py`` and formats
    the full LangGraph ``astream_events`` taxonomy (tool calls, reasoning
    steps, token usage, …). This adapter streams the master agent's
    graph events as ``data: <json>\\n\\n`` SSE lines and yields a
    ``agent_complete``-style terminal event when the stream ends.
    """
    import json

    agent = get_master_agent()
    if agent is None:
        yield f"data: {json.dumps({'type': 'agent_error', 'error': 'no active agent session'})}\n\n"
        return

    graph = getattr(agent, "graph", None)
    if graph is not None and hasattr(graph, "astream_events"):
        try:
            async for _ev in graph.astream_events(
                {"messages": [{"role": "user", "content": message}]},
                version="v2",
            ):
                pass
        except Exception as e:  # noqa: BLE001 - terminal event on failure
            yield f"data: {json.dumps({'type': 'agent_error', 'error': str(e)})}\n\n"
            return
        yield f"data: {json.dumps({'type': 'agent_complete', 'session_id': session_id})}\n\n"
    else:
        yield f"data: {json.dumps({'type': 'agent_error', 'error': 'master agent graph not available'})}\n\n"
