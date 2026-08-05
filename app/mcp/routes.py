from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.mcp.server import mcp_server

router = APIRouter()


class CallToolRequest(BaseModel):
    """Request body for invoking an MCP tool over HTTP."""

    name: str = Field(..., description="Tool name, e.g. pm.workflows.create_workflow")
    arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments matching the tool's input schema"
    )


def _extract_call_result(result: Any) -> Any:
    """Normalize FastMCP call_tool output into a JSON-safe value.

    call_tool returns either a dict (structured content) or a sequence of
    ContentBlocks. Our @node-based handlers return {"result": ...} dicts, so
    prefer that shape; otherwise collect text from content blocks.
    """
    if isinstance(result, dict):
        return result
    if isinstance(result, (list, tuple)):
        parts = []
        for block in result:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif isinstance(block, dict):
                parts.append(block)
            else:
                parts.append(str(block))
        if len(parts) == 1:
            return parts[0]
        return parts
    return result


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
                "mimeType": getattr(r, "mimeType", None)
                or getattr(r, "mime_type", None)
                or "text/plain",
            }
            for r in server_resources
        ]
        return {"resources": resources_list, "count": len(resources_list)}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/resources/read")
async def read_mcp_resource(uri: str = Query(..., description="Resource URI, e.g. pm://workflows")):
    """Read a single MCP resource by URI (returns rendered text content)."""
    try:
        contents = await mcp_server.read_resource(uri)
        text_parts = []
        for content in contents:
            if hasattr(content, "text"):
                text_parts.append(content.text)
            else:
                text_parts.append(str(content))
        return {"uri": uri, "content": "\n".join(text_parts)}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e), "uri": uri})


@router.post("/tools/call")
async def call_mcp_tool(req: CallToolRequest):
    """Invoke an MCP tool by name with arguments."""
    try:
        result = await mcp_server.call_tool(req.name, req.arguments)
        return {"name": req.name, "result": _extract_call_result(result)}
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e), "name": req.name})


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
