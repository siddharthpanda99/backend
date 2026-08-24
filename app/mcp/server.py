import logging
try:
    from app.mcp.fastmcp_compat import FastMCP
except ImportError:
    from mcp.server import MCPServer as FastMCP
from app.mcp.tools.automation import register_automation_tools
from app.mcp.tools.discovery import register_discovery_tools
from app.mcp.tools.agents import register_agent_tools
from app.mcp.tools.memories import register_memory_tools
from app.mcp.tools.models import register_model_tools
from app.mcp.tools.workflows import register_workflow_tools
from app.mcp.tools.workflow_configs import register_workflow_config_tools
from app.mcp.tools.graph import register_graph_tools
from app.mcp.tools.vision import register_vision_tools
from app.mcp.tools.filters import register_filter_tools
from app.mcp.tools.audio import register_audio_tools
from app.mcp.tools.data_forge import register_data_forge_tools
from app.mcp.tools.fleet import register_fleet_tools
from app.mcp.tools.image_edit import register_image_edit_tools
from app.mcp.tools.file_browser import register_file_browser_tools
from app.mcp.tools.plugins import register_plugin_tools
from app.mcp.tools.notifications import register_notification_tools
from app.mcp.tools.music import register_music_tools
from app.mcp.tools.messaging import register_messaging_tools
from app.mcp.tools.data_pipeline import register_data_pipeline_tools
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
from app.mcp.tools.drift_remediation import register_drift_remediation_tools
from app.mcp.tools.collections import register_collection_tools
from app.mcp.tools.chatgpt import register_chatgpt_tools
from app.mcp.tools.rbac import register_rbac_tools
from app.mcp.tools.credentials import register_credentials_tools
from app.mcp.tools.db_provisioning import register_db_provisioning_tools
from app.mcp.tools.doc_processing import register_doc_processing_tools
from app.mcp.tools.excel import register_excel_tools
from app.mcp.tools.events import register_events_tools
from app.mcp.tools.external_platforms import register_external_platforms_tools
from app.mcp.tools.ferment import register_ferment_tools
from app.mcp.tools.file_system import register_file_system_tools
from app.mcp.tools.rules_engine import register_rules_engine_tools
from app.mcp.tools.core_infrastructure import register_core_infrastructure_tools
from app.mcp.tools.image_runtime import register_image_runtime_tools
from app.mcp.tools.data_storage import register_data_storage_tools
from app.mcp.tools.nodes_registry import register_nodes_registry_tools
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
from app.mcp.tools.autoresearch_observability import register_autoresearch_observability_tools
from common_lib.modules.orchestration.response_templates.mcp_tools import register_response_template_tools
from app.mcp.resources.cognitive import register_cognitive_resources
from common_lib.modules.project_management.mcp import register_pm_resources
from common_lib.modules.platform_mcp.mcp import register_platform_tools
from app.mcp.tools.tool_catalog import register_tool_catalog_tools
from app.mcp.tools.prompt_templates import register_prompt_template_tools
from app.mcp.tools.canvas_validator_tools import register_canvas_validation_tools
from app.mcp.tools.chains_tools import register_chains_tools
from app.mcp.tools.multiagent_tools import register_multiagent_tools
from app.mcp.tools.dataset_management import register_dataset_management_tools

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
register_workflow_tools(mcp_server)
register_workflow_config_tools(mcp_server)
register_graph_tools(mcp_server)
register_vision_tools(mcp_server)
register_filter_tools(mcp_server)
register_audio_tools(mcp_server)
register_data_forge_tools(mcp_server)
register_fleet_tools(mcp_server)
register_file_browser_tools(mcp_server)
register_plugin_tools(mcp_server)
register_notification_tools(mcp_server)
register_music_tools(mcp_server)
register_messaging_tools(mcp_server)
register_data_pipeline_tools(mcp_server)
register_project_management_tools(mcp_server)
register_user_tools(mcp_server)
register_session_tools(mcp_server)
register_system_tools(mcp_server)
register_image_edit_tools(mcp_server)
register_hooks_triggers_tools(mcp_server)
register_knowledge_tools(mcp_server)
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
register_external_platforms_tools(mcp_server)
register_ferment_tools(mcp_server)
register_file_system_tools(mcp_server)
register_rules_engine_tools(mcp_server)
register_core_infrastructure_tools(mcp_server)
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
register_platform_tools(mcp_server)
register_tool_catalog_tools(mcp_server)
register_prompt_template_tools(mcp_server)
register_canvas_validation_tools(mcp_server)
register_chains_tools(mcp_server)
register_multiagent_tools(mcp_server)
register_dataset_management_tools(mcp_server)

# 3. Register Modular Resources
register_cognitive_resources(mcp_server)
register_pm_resources(mcp_server)

# 4. Register ALL @node wrappers as individual MCP tools (dynamic registration)
try:
    from app.mcp.node_bridge import register_dynamic_node_tools

    count = register_dynamic_node_tools(mcp_server)
    logger.info("Dynamic @node → MCP: %s tools registered", count)
except Exception as e:
    logger.warning("Dynamic @node registration skipped: %s", e)

logger.info("Cognitive MCP Server fully industrialized with total platform parity.")

# Export for external access
mcp = mcp_server
ROUTER_DEFINITIONS = ROUTER_DEFINITIONS
