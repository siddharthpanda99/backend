import json
import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP
from app.core.common_lib_integration import common_memory

logger = logging.getLogger("mcp.tools.workflows")

def register_workflow_tools(mcp: FastMCP):
    """Register tools for automation workflow discovery and execution."""

    @mcp.tool()
    async def list_workflows() -> List[Dict[str, Any]]:
        """List all registered automation workflows in the platform."""
        workflows = common_memory.list_workflow_definitions()
        return [w.model_dump() if hasattr(w, "model_dump") else w for w in workflows]

    @mcp.tool()
    async def list_agentic_loops() -> List[Dict[str, Any]]:
        """List workflows configured specifically as executable agentic loops."""
        all_wfs = common_memory.list_workflow_definitions()
        loops = []
        for wf in all_wfs:
            defn = wf.get("definition", {}) if isinstance(wf, dict) else getattr(wf, "definition", {})
            if defn.get("workflow_type") == "executable_graph":
                loops.append(wf.model_dump() if hasattr(wf, "model_dump") else wf)
        return loops

    @mcp.tool()
    async def run_workflow_graph(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]], inputs: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Execute an ad-hoc workflow graph with provided nodes and edges."""
        from app.modules.workflows.routes.index import run_workflow_stream
        # Note: run_workflow_stream is an SSE generator, here we trigger it
        # and return a status. In a real scenario, we might want a job ID.
        try:
            await run_workflow_stream(nodes=nodes, edges=edges, inputs=inputs)
            return {"status": "success", "message": "Workflow graph execution triggered"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
