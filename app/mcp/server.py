import logging
import os
import threading

try:
    from app.mcp.fastmcp_compat import FastMCP
except ImportError:
    from mcp.server import MCPServer as FastMCP
from app.mcp.tools.automation import register_automation_tools
from app.mcp.tools.discovery import register_discovery_tools
from app.mcp.tools.agents import register_agent_tools
from app.mcp.tools.memories import register_memory_tools
from app.mcp.tools.models import register_model_tools
from app.mcp.tools.open_code_review import register_open_code_review_tools
from app.mcp.tools.workflows import register_workflow_tools
from app.mcp.tools.workflow_configs import register_workflow_config_tools
from app.mcp.tools.graph import register_graph_tools
from app.mcp.tools.vision import register_vision_tools
from app.mcp.tools.filters import register_filter_tools
from app.mcp.tools.audio import register_audio_tools
from app.mcp.tools.audio_parity import register_audio_parity_tools
from app.mcp.tools.data_forge import register_data_forge_tools
from app.mcp.tools.fleet import register_fleet_tools
from app.mcp.tools.image_edit import register_image_edit_tools
from app.mcp.tools.file_browser import register_file_browser_tools
from app.mcp.tools.plugins import register_plugin_tools
from app.mcp.tools.notifications import register_notification_tools
from app.mcp.tools.music import register_music_tools
from app.mcp.tools.messaging import register_messaging_tools
from app.mcp.tools.users import register_user_tools
from app.mcp.tools.sessions import register_session_tools
from app.mcp.tools.system import register_system_tools
from app.mcp.tools.governance import register_governance_tools
from app.mcp.tools.hooks_triggers import register_hooks_triggers_tools
from app.mcp.tools.knowledge import register_knowledge_tools
from app.mcp.tools.knowledgebase import register_knowledgebase_tools
from app.mcp.tools.kpe import register_kpe_tools
from app.mcp.tools.learning import register_learning_tools
from app.mcp.tools.explainer import register_explainer_tools
from app.mcp.tools.generators import register_generator_tools
from app.mcp.tools.patterns import register_pattern_tools
from app.mcp.tools.drift import register_drift_tools
from app.mcp.tools.drift_alerts import register_drift_alert_tools
from app.mcp.tools.behaviour_tools import register_behaviour_tools
from app.mcp.tools.drift_remediation import register_drift_remediation_tools
from app.mcp.tools.collections import register_collection_tools
from app.mcp.tools.chatgpt import register_chatgpt_tools
from app.mcp.tools.i2w import register_i2w_tools
from app.mcp.tools.rbac import register_rbac_tools
from app.mcp.tools.credentials import register_credentials_tools
from app.mcp.tools.db_provisioning import register_db_provisioning_tools
from app.mcp.tools.doc_processing import register_doc_processing_tools
from app.mcp.tools.excel import register_excel_tools
from app.mcp.tools.events import register_events_tools
from app.mcp.tools.ferment import register_ferment_tools
from app.mcp.tools.file_system import register_file_system_tools
from app.mcp.tools.image_runtime import register_image_runtime_tools
from app.mcp.tools.data_storage import register_data_storage_tools
from app.mcp.tools.nodes_registry import register_nodes_registry_tools
from app.mcp.tools.alerts import register_alerts_tools
from app.mcp.tools.db_studio.database_connections import (
    register_database_connections_tools,
)
from app.mcp.tools.db_studio.query_workbench import register_query_workbench_tools
from app.mcp.tools.db_studio.schema_browser import register_schema_browser_tools
from app.mcp.tools.db_studio.data_browser import register_data_browser_tools
from app.mcp.tools.db_studio.visual_designers import register_visual_designers_tools
from app.mcp.tools.db_studio.ai_copilot import register_ai_copilot_tools
from app.mcp.tools.db_studio.query_execution import register_query_execution_tools
from app.mcp.tools.db_studio.connector_sdk import register_connector_sdk_tools
from app.mcp.tools.db_studio.capability_registry import (
    register_capability_registry_tools,
)
from app.mcp.tools.db_studio.administration import register_administration_tools
from app.mcp.tools.db_studio.performance import register_performance_tools
from app.mcp.tools.db_studio.backup import register_backup_tools
from app.mcp.tools.db_studio.migration import register_migration_tools
from app.mcp.tools.db_studio.data_exchange import register_data_exchange_tools
from app.mcp.tools.db_studio.etl import register_etl_tools
from app.mcp.tools.db_studio.data_quality import register_data_quality_tools
from app.mcp.tools.db_studio.observability import register_observability_tools
from app.mcp.tools.db_studio.security import register_security_tools
from app.mcp.tools.db_studio.collaboration import register_collaboration_tools
from app.mcp.tools.db_studio.notebook import register_notebook_tools
from app.mcp.tools.db_studio.knowledge_library import register_knowledge_library_tools
from app.mcp.tools.db_studio.automation import (
    register_automation_tools as register_db_studio_automation_tools,
)
from app.mcp.tools.db_studio.plugin_marketplace import register_plugin_marketplace_tools
from app.mcp.tools.db_studio.workspace_environment import register_workspace_tools
from app.mcp.tools.db_studio.discovery import (
    register_discovery_tools as register_db_studio_discovery_tools,
)
from app.mcp.tools.db_studio.governance import (
    register_governance_tools as register_db_studio_governance_tools,
)
from app.mcp.tools.db_studio.visualization import register_visualization_tools
from app.mcp.tools.db_studio.api_integration import register_api_integration_tools
from app.mcp.tools.db_studio.backend_architecture import (
    register_backend_architecture_tools,
)
from app.mcp.tools.db_studio.frontend_design import register_frontend_design_tools
from app.mcp.tools.tool_search import register_tool_search_tools
from app.mcp.tools.project_management import register_project_management_tools
from app.mcp.tools.dynamic_workflows import register_dynamic_workflow_tools
from app.mcp.tools.plugin_services import register_plugin_service_tools
from app.mcp.tools.claude_mem import register_claude_mem_tools
from app.mcp.tools.memory_features import register_memory_feature_tools
from app.mcp.tools.autoresearch import register_autoresearch_tools
from app.mcp.tools.autoresearch_observability import (
    register_autoresearch_observability_tools,
)
from common_lib.modules.orchestration.response_templates.mcp_tools import (
    register_response_template_tools,
)
from app.mcp.resources.cognitive import register_cognitive_resources
from common_lib.modules.project_management.mcp import register_pm_resources
from common_lib.modules.platform_mcp.mcp import register_platform_tools
from app.mcp.tools.tool_catalog import register_tool_catalog_tools
from app.mcp.tools.prompt_templates import register_prompt_template_tools
from app.mcp.tools.knowledge_api import register_knowledge_api_tools
from app.mcp.tools.canvas_validator_tools import register_canvas_validation_tools
from app.mcp.tools.chains_tools import register_chains_tools
from app.mcp.tools.multiagent_tools import register_multiagent_tools
from app.mcp.tools.dataset_management import register_dataset_management_tools
from app.mcp.tools.decision_engine import register_decision_engine_tools
from app.mcp.tools.cognitive_runtime import register_cognitive_runtime_tools

# Setup MCP-specific logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app.mcp")

# Initialize FastMCP Server
mcp_server = FastMCP(
    "Cognitive Orchestrator",
    dependencies=["pydantic", "sqlalchemy", "psutil"],
)

# 1. Register Core Transports & Middlewares (handled by routes.py)

# 2. Register Modular Tools
register_automation_tools(mcp_server)
register_discovery_tools(mcp_server)
register_agent_tools(mcp_server)
register_memory_tools(mcp_server)
register_model_tools(mcp_server)
register_open_code_review_tools(mcp_server)
register_workflow_tools(mcp_server)
register_workflow_config_tools(mcp_server)
register_graph_tools(mcp_server)
register_vision_tools(mcp_server)
register_filter_tools(mcp_server)
register_audio_tools(mcp_server)
register_audio_parity_tools(mcp_server)
register_data_forge_tools(mcp_server)
register_fleet_tools(mcp_server)
register_file_browser_tools(mcp_server)
register_plugin_tools(mcp_server)
register_notification_tools(mcp_server)
register_music_tools(mcp_server)
register_messaging_tools(mcp_server)
register_project_management_tools(mcp_server)
register_user_tools(mcp_server)
register_session_tools(mcp_server)
register_system_tools(mcp_server)
register_image_edit_tools(mcp_server)
register_hooks_triggers_tools(mcp_server)
register_knowledge_tools(mcp_server)
register_knowledge_api_tools(mcp_server)
register_alerts_tools(mcp_server)
register_knowledgebase_tools(mcp_server)
register_kpe_tools(mcp_server)
register_learning_tools(mcp_server)
register_explainer_tools(mcp_server)
register_generator_tools(mcp_server)
register_pattern_tools(mcp_server)
register_drift_tools(mcp_server)
register_drift_alert_tools(mcp_server)
register_drift_remediation_tools(mcp_server)
register_collection_tools(mcp_server)
register_chatgpt_tools(mcp_server)
register_rbac_tools(mcp_server)
register_credentials_tools(mcp_server)
register_db_provisioning_tools(mcp_server)
register_doc_processing_tools(mcp_server)
register_excel_tools(mcp_server)
register_events_tools(mcp_server)
register_ferment_tools(mcp_server)
register_file_system_tools(mcp_server)
register_image_runtime_tools(mcp_server)
register_data_storage_tools(mcp_server)
register_nodes_registry_tools(mcp_server)
register_database_connections_tools(mcp_server)
register_query_workbench_tools(mcp_server)
register_schema_browser_tools(mcp_server)
register_data_browser_tools(mcp_server)
register_visual_designers_tools(mcp_server)
register_ai_copilot_tools(mcp_server)
register_query_execution_tools(mcp_server)
register_connector_sdk_tools(mcp_server)
register_capability_registry_tools(mcp_server)
register_administration_tools(mcp_server)
register_performance_tools(mcp_server)
register_backup_tools(mcp_server)
register_migration_tools(mcp_server)
register_data_exchange_tools(mcp_server)
register_etl_tools(mcp_server)
register_data_quality_tools(mcp_server)
register_observability_tools(mcp_server)
register_security_tools(mcp_server)
register_collaboration_tools(mcp_server)
register_notebook_tools(mcp_server)
register_knowledge_library_tools(mcp_server)
register_db_studio_automation_tools(mcp_server)
register_plugin_marketplace_tools(mcp_server)
register_workspace_tools(mcp_server)
register_db_studio_discovery_tools(mcp_server)
register_db_studio_governance_tools(mcp_server)
register_visualization_tools(mcp_server)
register_api_integration_tools(mcp_server)
register_backend_architecture_tools(mcp_server)
register_frontend_design_tools(mcp_server)
register_tool_search_tools(mcp_server)
register_dynamic_workflow_tools(mcp_server)
register_plugin_service_tools(mcp_server)
register_claude_mem_tools(mcp_server)
register_memory_feature_tools(mcp_server)
register_autoresearch_tools(mcp_server)
register_autoresearch_observability_tools(mcp_server)
register_response_template_tools(mcp_server)
# register_platform_tools(mcp_server) is deliberately NOT called at module scope.
#
# It delegated to platform_mcp.node_tools.register_node_tools, a bulk
# `@node` -> MCP registration: it discovered ~24.7k nodes, registered ~25.5k
# tools, and measured ~140-230s. At module scope that ran inside
# `import app.mcp.server`, i.e. inside `import app.main`, so every consumer of
# the app (tests, scripts, CLI tooling, and the HTTP server itself) paid for it
# before anything could be served. It now runs on the background warmup thread
# (see `start_node_tool_warmup`), which the FastAPI lifespan starts.
#
# The deferred `register_dynamic_node_tools` (app.mcp node_bridge) discovers
# from a DIFFERENT registry and is NOT a substitute: measured against this call
# it covers 20,652 tools versus 21,893, missing 1,241 that only this path
# contributes ("A/B Analyze", "Add Policy", "Agent Create", ...). The warmup
# therefore runs both, in this order.
register_tool_catalog_tools(mcp_server)
register_prompt_template_tools(mcp_server)
register_canvas_validation_tools(mcp_server)
register_chains_tools(mcp_server)
register_multiagent_tools(mcp_server)
register_dataset_management_tools(mcp_server)
register_behaviour_tools(mcp_server)
register_i2w_tools(mcp_server)
register_decision_engine_tools(mcp_server)
register_cognitive_runtime_tools(mcp_server)

# 3. Register Modular Resources
register_cognitive_resources(mcp_server)
register_pm_resources(mcp_server)

# 4. Register ALL @node wrappers as individual MCP tools (dynamic registration)
#
# This is deliberately NOT done at import time. It costs roughly 100s, and it is
# almost entirely node discovery: an AST scan plus `import_module` of ~3.7k
# modules under common_lib/modules. (Registering the tools themselves is cheap in
# comparison - on this server 19040 of the 19980 unique node names already have a
# statically registered tool of the same name, so only ~940 are actually added.)
# Paying that during `import app.main` taxed every consumer of the app - tests,
# scripts, CLI tooling - for a tool registry that is only ever read over HTTP.
#
# It is instead done once from the FastAPI lifespan hook (see
# `register_dynamic_node_tools_once`, called from `app.main.lifespan`). Every
# consumer reads the tool list lazily, so served behaviour is unchanged:
#   - `app/mcp/routes.py` calls `mcp_server.list_tools()` / `call_tool()` per request.
#   - `app.main` mounts `mcp_server.sse_app()`, which only wires closures; the
#     underlying server enumerates tools per connection, at request time.
#   - `app/mcp/standalone_node_server.py` is the stdio entry point and calls
#     `register_dynamic_node_tools` itself, so it never depended on this module.
# Lifespan runs to completion before the app serves its first request, so no
# client can observe a partially-registered tool list.
logger.info("Cognitive MCP Server fully industrialized with total platform parity.")

# Export for external access
mcp = mcp_server

_dynamic_nodes_registered = False
# Completion signal for the background @node warmup. Distinct from
# `_dynamic_nodes_registered`, which flips to True *before* the scan starts.
_node_tools_ready = threading.Event()
_node_tools_warmup_lock = threading.Lock()
_node_tools_warmup_thread: threading.Thread | None = None


def register_dynamic_node_tools_once() -> int:
    """Register every @node wrapper as an MCP tool. Idempotent.

    Deferred out of import time; see the comment above. Safe to call more than
    once (the lifespan hook can run repeatedly, e.g. under `TestClient`): only
    the first call registers, so tools are never duplicated.

    Returns:
        Number of tools registered by this call (0 if already done, or on error).
    """
    global _dynamic_nodes_registered
    if _dynamic_nodes_registered:
        return 0
    # Set before registering: a partial failure must not leave us retrying into
    # a half-populated server on every subsequent startup.
    _dynamic_nodes_registered = True
    total = 0
    try:
        # Superset first. platform_mcp.node_tools.register_node_tools covers
        # 1,241 tools the node_bridge discovery below does not, so running it
        # alone would silently shrink the MCP tool surface.
        try:
            from common_lib.modules.platform_mcp.mcp import register_platform_tools

            added = register_platform_tools(mcp_server)
            logger.info("Bulk @node -> MCP (platform nodes): %s registered", added)
            total += added
        except Exception as e:
            logger.warning("Bulk @node registration (platform nodes) failed: %s", e)

        try:
            from app.mcp.node_bridge import register_dynamic_node_tools

            added = register_dynamic_node_tools(mcp_server)
            logger.info("Dynamic @node -> MCP: %s tools registered", added)
            total += added
        except Exception as e:
            logger.warning("Dynamic @node registration skipped: %s", e)

        return total
    finally:
        # Release anyone blocked in wait_for_node_tools(), including on the
        # error path, so a failure can never wedge a tool request.
        _node_tools_ready.set()


def start_node_tool_warmup() -> bool:
    """Begin bulk @node registration on a background thread.

    The scan imports ~3.7k modules and measures ~140s. Running it inline in the
    FastAPI lifespan keeps the process from serving anything for that whole
    window, which is dead time for every HTTP client even though only MCP
    consumers need the result. A daemon thread lets the app bind and serve
    immediately; `wait_for_node_tools()` is the gate that keeps the tool list
    from being observed half-populated.

    Set `MCP_NODE_TOOLS_WARMUP=0` to fall back to inline registration, and
    `MCP_NODE_TOOLS_WARMUP=off` to skip the scan entirely.

    Returns:
        True if a warmup thread was started, False if inline/skipped/already
        running.
    """
    global _node_tools_warmup_thread
    if _node_tools_ready.is_set():
        return False
    mode = os.getenv("MCP_NODE_TOOLS_WARMUP", "thread").strip().lower()
    if mode in ("0", "off", "false", "no", "disabled"):
        logger.info("MCP node-tool warmup disabled; registering inline")
        register_dynamic_node_tools_once()
        return False
    if mode in ("sync", "inline", "blocking"):
        logger.info("MCP node-tool warmup set to inline")
        register_dynamic_node_tools_once()
        return False
    with _node_tools_warmup_lock:
        if _node_tools_warmup_thread is not None and _node_tools_warmup_thread.is_alive():
            return False
        thread = threading.Thread(
            target=register_dynamic_node_tools_once,
            name="mcp-node-tool-warmup",
            daemon=True,
        )
        _node_tools_warmup_thread = thread
        thread.start()
    logger.info("MCP node-tool warmup started in background")
    return True


def wait_for_node_tools(timeout: float | None = None) -> bool:
    """Block until bulk @node registration has finished.

    Call this before serving a request that reads the tool list, so no client
    can observe a partially registered server. Returns True if registration
    completed (or had already), False if the wait timed out.

    The readiness event, not `_dynamic_nodes_registered`, is the thing to wait
    on: that flag is set *before* the scan begins so concurrent callers do not
    start a second scan, which means it is true while the server is still empty.
    """
    if _node_tools_ready.is_set():
        return True
    if _node_tools_warmup_thread is None and not _dynamic_nodes_registered:
        # Nothing has kicked off registration: do it inline rather than return
        # early with an empty tool list.
        register_dynamic_node_tools_once()
        return _node_tools_ready.is_set()
    return _node_tools_ready.wait(timeout)


def node_tools_ready() -> bool:
    """True once bulk @node registration has finished."""
    return _node_tools_ready.is_set()
