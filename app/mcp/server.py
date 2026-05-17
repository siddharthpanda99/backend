import logging
from mcp.server.fastmcp import FastMCP
from app.mcp.tools.automation import register_automation_tools
from app.mcp.tools.discovery import register_discovery_tools
from app.mcp.tools.agents import register_agent_tools
from app.mcp.tools.memories import register_memory_tools
from app.mcp.tools.models import register_model_tools
from app.mcp.tools.workflows import register_workflow_tools
from app.mcp.tools.workflow_configs import register_workflow_config_tools
from app.mcp.tools.graph import register_graph_tools
from app.mcp.tools.vision import register_vision_tools
from app.mcp.tools.audio import register_audio_tools
from app.mcp.tools.data_forge import register_data_forge_tools
from app.mcp.tools.fleet import register_fleet_tools
from app.mcp.tools.file_browser import register_file_browser_tools
from app.mcp.tools.plugins import register_plugin_tools
from app.mcp.tools.notifications import register_notification_tools
from app.mcp.tools.music import register_music_tools
from app.mcp.tools.data_pipeline import register_data_pipeline_tools
from app.mcp.tools.users import register_user_tools
from app.mcp.tools.sessions import register_session_tools
from app.mcp.tools.system import register_system_tools
from app.mcp.resources.cognitive import register_cognitive_resources

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
register_audio_tools(mcp_server)
register_data_forge_tools(mcp_server)
register_fleet_tools(mcp_server)
register_file_browser_tools(mcp_server)
register_plugin_tools(mcp_server)
register_notification_tools(mcp_server)
register_music_tools(mcp_server)
register_data_pipeline_tools(mcp_server)
register_user_tools(mcp_server)
register_session_tools(mcp_server)
register_system_tools(mcp_server)

# 3. Register Modular Resources
register_cognitive_resources(mcp_server)

logger.info("Cognitive MCP Server fully industrialized with total platform parity.")
