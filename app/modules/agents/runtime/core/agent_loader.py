"""
agents/runtime/core/agent_loader.py
-------------------------------------
Proxy for the common_lib AgentLoader.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from common_lib.modules.orchestration import agent_loader as cl_loader
from app.core.common_lib_integration import common_memory

# Re-export singletons for backward compatibility
def get_engine_manager() -> Optional[Any]:
    return cl_loader.get_engine_manager()

def get_master_agent() -> Optional[Any]:
    return cl_loader.get_master_agent()

def get_active_session() -> Dict[str, Any]:
    return cl_loader.get_active_session()

def clear_checkpointer():
    return cl_loader.clear_checkpointer()

def get_system_vram_gb() -> float:
    return cl_loader.get_system_vram_gb()

def get_vram_usage() -> float:
    return cl_loader.get_vram_usage()

def load_agent(
    model_path: Optional[str]   = None,
    provider: str               = "vllm",
    agent_id: str               = "master_agent",
    agent_display_name: str     = "Master Agent",
    tool_ids: Optional[List[str]] = None,
    system_prompt: Optional[str]  = None,
    guardrails: Optional[List]    = None,
    use_mcp_discovery: bool       = False,
    global_search_enabled: bool   = False,
    workflow_ids: Optional[List[str]] = None,
    preload: bool                 = True,
    skip_engine_deploy: bool      = False,
    engine_id: str                = "main",
    auto_deploy_llm: bool         = False,
) -> Any:
    """
    Proxy to common_lib.load_agent with backend-specific context (common_memory).
    If provider is vLLM and skip_engine_deploy is False, triggers container redeploy.
    """
    # Orchestrate vLLM Container Lifecycle
    # auto_deploy_llm=False (default): never touch Docker during agent deploy.
    # auto_deploy_llm=True: trigger deploy_engine_node if selected config not found.
    if provider == "vllm" and model_path and not skip_engine_deploy and auto_deploy_llm:
        from common_lib.modules.ai_models.container import AIModelsContainer
        from common_lib.modules.ai_models.llm.vllm_fleet_manager import vllm_fleet as vllm_manager
        
        container = AIModelsContainer()
        model_meta = container.repository.get_model(model_path)
        
        if model_meta and model_meta.file_path:
            list(vllm_manager.deploy_engine_node(
                model_path=model_meta.file_path,
                engine_id=engine_id,
                quantization=model_meta.quantization,
                gpu_memory_utilization=model_meta.gpu_memory_utilization,
                max_model_len=model_meta.max_model_len,
                trust_remote_code=model_meta.trust_remote_code,
                mirror_service=container.mirror_service
            ))

    return cl_loader.load_agent(
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
        # preload=True triggers vLLM deploy inside EngineManager — only allow when auto_deploy_llm
        preload=auto_deploy_llm,
        memory_store=common_memory,
        engine_id=engine_id
    )

def load_agent_generator(
    model_path: Optional[str]   = None,
    provider: str               = "vllm",
    agent_id: str               = "master_agent",
    agent_display_name: str     = "Master Agent",
    tool_ids: Optional[List[str]] = None,
    system_prompt: Optional[str]  = None,
    guardrails: Optional[List]    = None,
    use_mcp_discovery: bool       = False,
    global_search_enabled: bool   = False,
    workflow_ids: Optional[List[str]] = None,
    template_ids: Optional[List[str]] = None,
    preload: bool                 = True,
    skip_engine_deploy: bool      = False,
    engine_id: str                = "main",
    auto_deploy_llm: bool         = False,
) -> Any:
    """
    Generator version of load_agent for streaming deployment status.
    Yields strings formatted for SSE: data: <payload>\n\n
    """
    # Orchestrate vLLM Container Lifecycle
    # When auto_deploy_llm=False (default), skip Docker entirely and connect to
    # whatever vLLM node is already running via the fleet registry smart fallback.
    if provider == "vllm" and model_path and auto_deploy_llm:
        from common_lib.modules.ai_models.container import AIModelsContainer
        from common_lib.modules.ai_models.llm.vllm_fleet_manager import vllm_fleet as vllm_manager
        
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
                gpu_memory_utilization=gpu_util_override if gpu_util_override is not None else model_meta.gpu_memory_utilization,
                max_model_len=max_len_override if max_len_override is not None else model_meta.max_model_len,
                trust_remote_code=model_meta.trust_remote_code,
                mirror_service=container.mirror_service
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
            yield f"data: STATUS:RETRYING:Memory limit reached. Retrying with Safe Defaults ({SAFE_UTIL} Util / {SAFE_LEN} Context)...\n\n"
            
            success = False
            for update in run_deploy(gpu_util_override=SAFE_UTIL, max_len_override=SAFE_LEN):
                if "STATUS:READY" in update:
                    success = True
                yield f"data: {update}\n\n"
            
            if success:
                # Update registry so this model works first time next load
                try:
                    model_meta.gpu_memory_utilization = SAFE_UTIL
                    model_meta.max_model_len = SAFE_LEN
                    container.repository.register_model(model_meta)
                    yield f"data: LOG:Registry updated with safe memory settings for {model_path}.\n\n"
                except Exception as ex:
                    yield f"data: LOG:Failed to persist safe settings: {str(ex)}\n\n"
    else:
        yield "data: STATUS:STARTING:Configuring non-vLLM provider...\n\n"

    # Final Compilation
    try:
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
        )
        yield "data: STATUS:READY:Agent successfully deployed.\n\n"
    except Exception as e:
        yield f"data: STATUS:ERROR:Compilation failed: {str(e)}\n\n"
