from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from mcp.server.fastmcp import FastMCP
from app.modules.mcp.server import mcp_server

router = APIRouter()

@router.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """
    Standardized SSE Transport for the MCP Server.
    Enables web-based agents (React) to connect to the Tool Registry.
    """
    # FastMCP uses the 'sse' transport internally if called via a web-framework
    # In a real scenario, this would return an EventSource-compatible response.
    # For this demo, we expose the discovery endpoints directly via FastAPI for the UI.
    return StreamingResponse(
        content=f"data: Connecting to NEXUS MCP Cluster... (Standard SSE Protocol)\n\n",
        media_type="text/event-stream"
    )

@router.get("/tools")
async def list_mcp_tools():
    """Proxy for MCP 'tools/list' capability (UI Visualization)."""
    # Mapping our 507 tool definitions to the MCP Tool Schema
    try:
        from app.core.common_lib_integration import common_memory
        tools = common_memory.list_tool_definitions()
        mcp_tools = []
        for t in tools:
            mcp_tools.append({
                "name": t["id"].replace(".", "__"),
                "description": t["description"],
                "inputSchema": common_memory.get_tool_json_schema(t["id"])
            })
        return {"tools": mcp_tools, "count": len(mcp_tools)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/resources")
async def list_mcp_resources():
    """Proxy for MCP 'resources/list' capability (Cognitive Audit)."""
    return {
        "resources": [
            {"uri": "cognitive://persona", "name": "Agent Persona", "type": "text/markdown"},
            {"uri": "cognitive://mission", "name": "Mission & KPIs", "type": "text/markdown"},
            {"uri": "cognitive://memory", "name": "Episodic Context", "type": "application/json"}
        ]
    }
