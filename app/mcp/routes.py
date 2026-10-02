from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from app.mcp.identity import bind_principal, reset_principal, resolve_mcp_principal
from app.mcp.server import mcp_server, wait_for_node_tools

router = APIRouter()

# The bulk @node -> MCP scan runs on a background thread at startup so the app
# can serve HTTP before it finishes. Every route below that reads the tool list
# waits for it first, so a client never observes a partially registered server.
# The wait is bounded: on timeout the request proceeds with whatever is
# registered rather than hanging, and the scan completes in the background.
_NODE_TOOLS_WAIT_SECONDS = float(
    __import__("os").getenv("MCP_NODE_TOOLS_WAIT_SECONDS", "300")
)


def _await_node_tools() -> None:
    """Block until the background @node scan has finished (bounded)."""
    try:
        if not wait_for_node_tools(timeout=_NODE_TOOLS_WAIT_SECONDS):
            import logging

            logging.getLogger(__name__).warning(
                "MCP node-tool registration still in progress after %ss; "
                "serving the tools registered so far",
                _NODE_TOOLS_WAIT_SECONDS,
            )
    except Exception:
        # A failure to wait must not take the endpoint down.
        pass


class CallToolRequest(BaseModel):
    """Request body for invoking an MCP tool over HTTP."""

    name: str = Field(..., description="Tool name, e.g. pm.workflows.create_workflow")
    arguments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Tool arguments matching the tool's input schema",
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
        _await_node_tools()
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
async def read_mcp_resource(
    uri: str = Query(..., description="Resource URI, e.g. pm://workflows"),
):
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
async def call_mcp_tool(req: CallToolRequest, request: Request):
    """Invoke an MCP tool by name with arguments.

    The calling principal is established here and bound to the request scope
    for the duration of the call. The router is mounted with ``"auth": True``
    so ``get_current_active_user`` has already verified the bearer token by
    this point; this re-verifies the same token via the shared
    ``identity_context`` resolver purely to obtain a ``Principal`` the tool
    body can read. It fails closed -- an unusable header yields anonymous,
    never an elevated identity.

    This is what makes an identity *available* to tools; it is not the only
    transport. The SSE mount at ``app/main.py:1629`` uses ``app.mount`` and
    bypasses router dependencies, so tool calls arriving there find no bound
    context and correctly report anonymous.
    """
    principal = resolve_mcp_principal(request.headers.get("Authorization"))
    token = bind_principal(principal)
    try:
        _await_node_tools()
        result = await mcp_server.call_tool(req.name, req.arguments)
        return {"name": req.name, "result": _extract_call_result(result)}
    except Exception as e:
        return JSONResponse(
            status_code=400, content={"error": str(e), "name": req.name}
        )
    finally:
        # Always release: a leaked binding would let one request's identity be
        # served to the next request handled by the same worker.
        reset_principal(token)


@router.get("/servers")
async def list_mcp_servers():
    _await_node_tools()
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
