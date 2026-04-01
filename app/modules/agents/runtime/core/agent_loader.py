"""
agents/runtime/core/agent_loader.py
-------------------------------------
``load_agent()`` — the single function that wires an agent definition from
the DB into a live, compiled LangGraph.

Pattern is intentionally generic: the same approach will be reused for
skill runtimes, workflow runtimes, and prompt runtimes.

Owned singletons (one per process):
    _engine_manager     — shared inference backend
    _master_agent       — compiled ReactMasterAgent
    _active_session     — dict of what's currently deployed
"""
from __future__ import annotations

import importlib
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool, StructuredTool
from langgraph.checkpoint.memory import MemorySaver

from common_lib.modules.orchestration.agent.react_master_agent import ReactMasterAgent
from common_lib.modules.orchestration.agent.schemas import AgentDefinition, AgentIdentity, AgentType
from common_lib.modules.orchestration.agent.graph_builder import build_agent_graph
from common_lib.modules.core_infrastructure.shared.enums import (
    Status, AgentRole, ReasoningLevel, AutonomyLevel,
)

from app.agentic.master_agent import MasterAgent
from app.modules.agents.runtime.utils.logging import get_logger
from app.modules.agents.runtime.tools.builtins import build_builtin_tools, RuntimeContext
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from app.core.settings import get_settings

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------
_checkpointer: MemorySaver            = MemorySaver()
_engine_manager: Optional[Any]        = None
_master_agent: Optional[ReactMasterAgent] = None
_active_session: Dict[str, Any]       = {}


# ---------------------------------------------------------------------------
# Public getters (used by streaming.py and the router)
# ---------------------------------------------------------------------------

def get_engine_manager() -> Optional[Any]:
    return _engine_manager

def get_master_agent() -> Optional[ReactMasterAgent]:
    return _master_agent

def get_active_session() -> Dict[str, Any]:
    return _active_session


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_handler(path: str) -> Optional[Any]:
    """Resolve a dotted-path string to a callable."""
    if not path or not isinstance(path, str) or "." not in path:
        return None
    try:
        module_path, fn = path.rsplit(".", 1)
        return getattr(importlib.import_module(module_path), fn)
    except Exception as exc:
        logger.error("Cannot resolve handler %s: %s", path, exc)
        return None


def _schema_to_langchain(schema: Any) -> Optional[StructuredTool]:
    handler = _resolve_handler(schema.execution.handler)
    if not handler:
        return None
    return StructuredTool.from_function(
        func=handler,
        name=schema.id.replace(".", "__"),
        description=schema.capability.description,
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_agent(
    model_path: Optional[str]   = None,
    provider: str               = "local_llama",
    agent_id: str               = "master_agent",
    agent_display_name: str     = "Master Agent",
    tool_ids: Optional[List[str]] = None,
    system_prompt: Optional[str]  = None,
    guardrails: Optional[List]    = None,
    use_mcp_discovery: bool       = False,
    global_search_enabled: bool   = False,
    workflow_ids: Optional[List[str]] = None,
    preload: bool                 = True,
) -> ReactMasterAgent:
    """
    Wire and compile a custom agent for the given configuration.

    Steps:
      1. Init EngineManager + LLM adapter
      2. Build ``RuntimeContext`` → de-globalised builtin tools
      3. Layer on registry and MCP tools
      4. Call ``common_lib.graph_builder.build_agent_graph()``
      5. Compile → ``ReactMasterAgent``

    This same pattern will be reused for skill/workflow/prompt runtimes,
    just swapping the tool list and system prompt.
    """
    global _engine_manager, _master_agent, _active_session

    from inference_platform.core.engine_manager import EngineManager
    from common_lib.modules.ai_models.llm.langchain_adapter import LangChainModelAdapter

    from app.core.common_lib_integration import common_memory

    # 1. Fetch Definition from Registry
    raw_record = common_memory.get_agent_definition(agent_id)
    if raw_record:
        # Wrap in Pydantic for consistent attribute access
        agent_record = AgentDefinition(**raw_record)
    else:
        logger.warning("Agent '%s' not found in registry, using defaults.", agent_id)
        # Create a basic definition if missing
        agent_record = AgentDefinition(
            identity=AgentIdentity(
                agent_name=agent_id,
                display_name=agent_display_name,
                version="1.0.0",
                status=Status.ACTIVE,
                owner="admin"
            )
        )

    # 2. Resolve Parameters (DB > Args > Defaults)
    selected_provider = provider or agent_record.runtime_config.get("provider") if agent_record.runtime_config else None
    selected_provider = selected_provider or os.getenv("LLM_PROVIDER_TYPE", "local_llama")

    selected_model = model_path or agent_record.runtime_config.get("model_path") if agent_record.runtime_config else None
    selected_model = selected_model or (
        os.getenv("LOCAL_LLM_MODEL_PATH") or os.getenv("LOCAL_HF_MODEL_PATH")
    )

    actual_system_prompt = system_prompt or agent_record.resolved_prompt or agent_record.instructions_text

    # 2.5 Dynamic Registry Configuration (Hardening)
    # We dump to dict to safely use .get() for both nested models and legacy flat fields
    agent_dict = agent_record.model_dump()
    planning_config = agent_dict.get("execution_constraints") or {}
    safety_config = agent_dict.get("safety") or {}
    
    selected_max_steps = planning_config.get("max_steps", 12) if isinstance(planning_config, dict) else (planning_config.max_steps if planning_config else 12)
    selected_guardrails = guardrails or (safety_config.get("forbidden_actions", []) if isinstance(safety_config, dict) else (safety_config.forbidden_actions if safety_config else []))
    
    selected_use_mcp = (
        use_mcp_discovery or 
        (agent_record.runtime_config.get("use_mcp_discovery", False) if agent_record.runtime_config else False) or
        (agent_dict.get("tool_access") or {}).get("discovery", {}).get("all", False) if isinstance(agent_dict.get("tool_access"), dict) else False
    )

    # 3. Engine Setup
    if _engine_manager is None:
        class _DummyCtx: adapter = service = None
        _engine_manager = EngineManager(_DummyCtx())

    _engine_manager.setup(
        target_files=[],
        model_path=selected_model,
        provider_type=selected_provider,
        preload=preload,
    )
    model_provider = LangChainModelAdapter(provider=_engine_manager.main_llm)

    # 2. RuntimeContext → builtin tools (no globals)
    ctx = RuntimeContext(
        session_config=_active_session,
        engine_manager=_engine_manager,
        model_provider=model_provider,
        tool_registry=BUILTIN_TOOL_REGISTRY,
    )
    builtin_tools = build_builtin_tools(ctx)

    # 5. Service (Hydrate with Section Configs)
    service = MasterAgent(
        model_provider=model_provider,
        engine_manager=_engine_manager,
        system_prompt=actual_system_prompt,
        guardrails=selected_guardrails,
        use_mcp_discovery=selected_use_mcp,
        max_steps=selected_max_steps
    )

    # Link Runtime/Lifecycle sections if present
    if agent_record.runtime_config:
        service.set_reasoning_level(agent_record.runtime_config.get("reasoning_level", "analytical"))
    if agent_record.lifecycle:
        # Placeholder for deeper lifecycle linkage (e.g. timeouts)
        pass

    # MCP bridge tool
    @tool
    def tool_search_mcp(query: str) -> str:
        """Search the MCP registry for specialised tools matching your query."""
        return service.query_capability_inventory(query)

    # 4. Assemble tool list
    selected_tools: List[Any]   = []
    active_tool_meta: List[Dict] = []

    if use_mcp_discovery:
        selected_tools.append(tool_search_mcp)
        active_tool_meta.append({
            "id": "tool_search_mcp", "name": "MCP Tool Search",
            "description": "Search specialised MCP functions.",
        })
        selected_tools += [
            bt for bt in builtin_tools
            if bt.name in {"query_capability_inventory", "remember_info", "extract_and_remember_hints"}
        ]
    else:
        for bt in builtin_tools:
            entry = next((e for e in BUILTIN_TOOL_REGISTRY if e["id"] == bt.name), None)
            if not tool_ids or (entry and entry["id"] in tool_ids):
                selected_tools.append(bt)
                if entry:
                    active_tool_meta.append({
                        "id": entry["id"], "name": entry["name"],
                        "description": entry["description"],
                    })

        # Dynamic registry tools
        if tool_ids and _engine_manager.registry_svc and not get_settings().SKIP_REGISTRY_SYNC:
            _engine_manager.sync_registry()
            for tid in tool_ids:
                if any(m["id"] == tid for m in active_tool_meta):
                    continue
                schema = _engine_manager.registry_svc.get_tool(tid)
                if schema:
                    lc_tool = _schema_to_langchain(schema)
                    if lc_tool:
                        selected_tools.append(lc_tool)
                        active_tool_meta.append({
                            "id": tid, "name": schema.name,
                            "description": schema.capability.description,
                        })

    # 5. Build + compile graph
    workflow = build_agent_graph(service, selected_tools)
    compiled  = workflow.compile(checkpointer=_checkpointer)

    _master_agent = ReactMasterAgent(
        definition=AgentDefinition(
            identity=AgentIdentity(
                agent_name=agent_id,
                display_name=agent_display_name,
                version="1.0.0",
                status=Status.ACTIVE,
                owner="admin",
            ),
            type=AgentType(
                role=AgentRole.ORCHESTRATOR,
                secondary_roles=[],
                reasoning_level=ReasoningLevel.ANALYTICAL,
                autonomy=AutonomyLevel.BOUNDED,
            ),
            system_prompt_override=service.get_formatted_prompt(
                strategy=model_provider.get_agent_strategy()
            ),
        ),
        model_provider=model_provider,
        tools=selected_tools,
        use_mcp_discovery=use_mcp_discovery,
        whitelist=tool_ids or [],
        global_search_enabled=global_search_enabled,
    )
    _master_agent.graph = compiled

    _active_session = {
        "agent":                 agent_display_name,
        "model":                 model_provider.config.model_path,
        "provider":              model_provider.config.provider_type,
        "tools":                 active_tool_meta,
        "tool_count":            len(tool_ids) if tool_ids else len(selected_tools),
        "workflow_count":        len(workflow_ids) if workflow_ids else 0,
        "whitelist":             tool_ids or [],
        "use_mcp_discovery":     use_mcp_discovery,
        "global_search_enabled": global_search_enabled,
        "session_id":            f"session-{datetime.now().strftime('%m%d%H%M')}",
        "full_definition":       agent_record.definition,
        "system_prompt":         _master_agent.definition.system_prompt_override,
    }

    logger.info(
        "Agent '%s' (%s) deployed with %d tool(s) via %s",
        agent_id, agent_display_name, len(selected_tools), selected_provider,
    )
    return _master_agent
