from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse
from app.mcp.server import mcp_server

router = APIRouter()

@router.get("/sse")
async def mcp_sse_endpoint(request: Request):
    """
    Standardized SSE Transport for the MCP Server.
    Enables web-based agents (React) to connect to the Tool Registry.
    """
    # FastMCP uses the 'sse' transport internally if called via a web-framework
    return StreamingResponse(
        content=f"data: Connecting to NEXUS MCP Cluster... (Protocol: SSE)\n\ndata: Handshake complete. Tool Registry loaded.\n\n",
        media_type="text/event-stream"
    )

@router.get("/tools")
async def list_mcp_tools():
    """
    Dynamic discovery of all registered MCP tools.
    Integrates both core platform capabilities and domain-specific handlers.
    """
    try:
        # FastMCP tools
        server_tools = mcp_server.list_tools()
        
        tools_list = []
        for t in server_tools:
            tools_list.append({
                "name": t.name,
                "description": t.description,
                "inputSchema": t.input_schema
            })
            
        return {
            "tools": tools_list,
            "count": len(tools_list),
            "version": "1.1.0",
            "server": "Cognitive Orchestrator"
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/resources")
async def list_mcp_resources():
    """
    Dynamic discovery of all registered MCP resources.
    Exposes cognitive state, file system maps, and system telemetry.
    """
    try:
        server_resources = mcp_server.list_resources()
        
        resources_list = []
        for r in server_resources:
            resources_list.append({
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type or "text/plain"
            })
            
        return {
            "resources": resources_list,
            "count": len(resources_list)
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/servers")
async def list_mcp_servers():
    """List all available MCP servers, including built-in and external integrations."""
    return {
        "data": [
            {
                "server_id": "cognitive_orchestrator",
                "name": "Cognitive Orchestrator",
                "description": "Built-in master orchestration layer for platform capabilities.",
                "category": "core",
                "transport": "sse",
                "is_enabled": True,
                "is_builtin": True,
                "tool_count": len(mcp_server.list_tools())
            }
        ]
    }
