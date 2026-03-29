import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from app.core.common_lib_integration import common_memory

# Setup MCP-specific logging
logger = logging.getLogger("mcp.server")
logger.setLevel(logging.INFO)

# 1. Initialize FastMCP Server
mcp_server = FastMCP(
    "NEXUS-Agent-Registry",
    dependencies=["sqlmodel", "common_lib"]
)

@mcp_server.tool()
def search_tools(query: str) -> str:
    """
    Search the standardized tool registry for specialized functions.
    Use this when you need a capability (e.g., 'pdf-extraction') not in your current context.
    """
    try:
        tools = common_memory.list_tool_definitions()
        matches = []
        query_lc = query.lower()
        
        for t in tools:
            # Check name and description
            text = (t.get("name", "") + " " + t.get("description", "")).lower()
            if query_lc in text:
                matches.append({
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"]
                })
        
        if not matches:
            return f"No tools found matching '{query}'. Try broader keywords."
            
        res = f"Found {len(matches)} matching tools:\n"
        for m in matches[:10]:
            res += f"- **{m['name']}** (`{m['id']}`): {m['description']}\n"
        return res
    except Exception as e:
        return f"Discovery error: {str(e)}"

@mcp_server.tool()
def get_tool_schema(tool_id: str) -> str:
    """
    Retrieve the full JSON Schema and execution details for a specific tool.
    Call this once you have identified the tool ID via 'search_tools'.
    """
    try:
        tool_def = common_memory.get_tool_definition(tool_id)
        if not tool_def:
            return f"Error: Tool '{tool_id}' not found in registry."
            
        # Standardize output for the LLM
        return f"### Tool: {tool_def.get('name')}\nID: {tool_id}\n\nSchema:\n```json\n{common_memory.get_tool_json_schema(tool_id)}\n```"
    except Exception as e:
        return f"Schema retrieval error: {str(e)}"

# 2. Resource Management (Cognitive Segments)
@mcp_server.resource("cognitive://persona")
def get_agent_persona() -> str:
    """Read-only access to the agent's core persona and identity segments."""
    # This would typically pull from the active session or registry
    return "# Agent Persona\nYou are a high-performance cognitive agent..."

@mcp_server.resource("cognitive://mission")
def get_mission_statement() -> str:
    """Read-only access to the agent's primary mission and KPIs."""
    return "# Mission\n1. Solve user queries accurately.\n2. Minimize latency."

def start_mcp_server():
    """Entry point for standalone or integrated server start."""
    logger.info("Starting NEXUS MCP Standardized Registry Server...")
    # In a real scenario, this would choose transport (SSE or Stdio)
    # FastMCP handles transport based on the entry point (CLI vs Code)
    pass
