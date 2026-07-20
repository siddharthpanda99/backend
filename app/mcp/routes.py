from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse
from app.mcp.server import mcp_server

router = APIRouter()


@router.get("/sse")
async def mcp_sse_endpoint():
    """
    Real SSE transport is at GET /mcp/transport/sse (FastMCP-native).
    This endpoint redirects for discoverability.
    """
    return RedirectResponse(url="/mcp/transport/sse")


@router.get("/tools")
async def list_mcp_tools():
    """
    Dynamic discovery of all registered MCP tools.
    Integrates both core platform capabilities and domain-specific handlers.
    """
    try:
        server_tools = await mcp_server.list_tools()
        tools_list = [
            {
                "name": t.name,
                "description": t.description,
                "inputSchema": t.inputSchema,
            }
            for t in server_tools
        ]
        return {
            "tools": tools_list,
            "count": len(tools_list),
            "version": "1.1.0",
            "server": "Cognitive Orchestrator",
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/resources")
async def list_mcp_resources():
    try:
        server_resources = await mcp_server.list_resources()
        resources_list = [
            {
                "uri": str(r.uri),
                "name": r.name,
                "description": r.description,
                "mimeType": r.mime_type or "text/plain",
            }
            for r in server_resources
        ]
        return {"resources": resources_list, "count": len(resources_list)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/servers")
async def list_mcp_servers():
    tools = await mcp_server.list_tools()
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
                "tool_count": len(tools),
            }
        ]
    }
