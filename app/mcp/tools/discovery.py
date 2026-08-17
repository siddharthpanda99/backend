import json
import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from app.core.common_lib_integration import common_memory

logger = logging.getLogger("mcp.tools.discovery")

def register_discovery_tools(mcp: FastMCP):
    """Register tools for discovering platform capabilities, tools, and skills."""

    @mcp.tool()
    async def search_platform_tools(query: str) -> List[Dict[str, Any]]:
        """Search the platform registry for specialized tools and capabilities."""
        tools = common_memory.list_tool_definitions()
        query_lc = query.lower()
        matches = []
        for t in tools:
            name = t.get("name", "")
            desc = t.get("description", "")
            if query_lc in name.lower() or query_lc in desc.lower():
                matches.append({
                    "id": t["id"],
                    "name": name,
                    "description": desc
                })
        return matches

    @mcp.tool()
    async def get_tool_schema(tool_id: str) -> Dict[str, Any]:
        """Retrieve the full JSON Schema and execution signature for a specific tool."""
        tool_def = common_memory.get_tool_definition(tool_id)
        if not tool_def:
            return {"status": "error", "message": "Tool not found"}
        
        schema = common_memory.get_tool_json_schema(tool_id)
        return {
            "id": tool_id,
            "definition": tool_def if isinstance(tool_def, dict) else tool_def.model_dump(),
            "schema": schema
        }

    @mcp.tool()
    async def list_skills() -> List[Dict[str, Any]]:
        """List all high-level skills (bundled capabilities) available in the registry."""
        skills = common_memory.list_skill_definitions()
        return [s.model_dump() if hasattr(s, "model_dump") else s for s in skills]

    @mcp.tool()
    async def get_registry_summary() -> Dict[str, Any]:
        """Retrieve a summary count of all entities in the unified platform registry."""
        return {
            "agents": len(common_memory.list_agent_definitions()),
            "skills": len(common_memory.list_skill_definitions()),
            "workflows": len(common_memory.list_workflow_definitions()),
            "tools": len(common_memory.list_tool_definitions()),
            "prompts": len(common_memory.list_prompt_definitions())
        }

    @mcp.tool()
    async def get_entity_definition(entity_type: str, entity_id: str) -> Dict[str, Any]:
        """
        Retrieve the full definition of any registry entity.
        entity_type: 'agent', 'skill', 'workflow', 'prompt', or 'tool'.
        """
        data = None
        if entity_type == "agent":
            data = common_memory.get_agent_definition(entity_id)
        elif entity_type == "skill":
            data = common_memory.get_skill_definition(entity_id)
        elif entity_type == "workflow":
            data = common_memory.get_workflow_definition(entity_id)
        elif entity_type == "prompt":
            data = common_memory.get_prompt_definition(entity_id)
        elif entity_type == "tool":
            data = common_memory.get_tool_definition(entity_id)
            
        if not data:
            return {"status": "error", "message": f"Entity '{entity_id}' of type '{entity_type}' not found."}
            
        return data if isinstance(data, dict) else data.model_dump()
