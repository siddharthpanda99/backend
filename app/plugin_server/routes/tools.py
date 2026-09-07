"""Plugin Server routes — tool execution (the hot path).

This is the endpoint that the main backend calls for every AI
tool invocation. It must be:
  - Fast (low overhead)
  - Safe (cooperative with the SafeReloadGuard)
  - Bounded (timeout to prevent runaway tools)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response, status

logger = logging.getLogger(__name__)
router = APIRouter()


# Default per-tool timeout in seconds. Can be overridden by
# passing "timeout_sec" in the request body, or by setting the
# tool's @node execution_timeout.
_DEFAULT_TIMEOUT = float(
    __import__("os").environ.get("PLUGIN_SERVER_TOOL_TIMEOUT_SEC", "60")
)


@router.post("/execute")
async def execute_tool(
    request: Request, body: dict, response: Response
) -> dict[str, Any]:
    """Execute a tool on a registered plugin. The hot path.

    Request body:
        {
            "plugin_id": "github",
            "tool_name": "create_issue",
            "params": {"title": "...", "body": "..."},
            "timeout_sec": 30   # optional, default 60
        }

    Response (200):
        {"success": true, "result": {...}, "duration_ms": 142}

    Response (404):
        {"success": false, "error": "Plugin not found"}

    Response (503):
        {"success": false, "error": "plugin is reloading; retry shortly",
         "retry_after": 5}
    """
    from common_lib.modules.plugins.engine.safe_reload import SafeReloadError

    plugin_id = body.get("plugin_id")
    tool_name = body.get("tool_name")
    params = body.get("params", {}) or {}
    timeout_sec = float(body.get("timeout_sec", _DEFAULT_TIMEOUT))

    if not plugin_id or not tool_name:
        raise HTTPException(
            status_code=400, detail="plugin_id and tool_name are required"
        )

    components = getattr(request.app.state, "components", {})
    mgr = components.get("tool_manager")
    if mgr is None:
        raise HTTPException(
            status_code=503, detail="Tool plugin manager not initialized"
        )

    # Find the plugin
    target = None
    for p in mgr.engine.list_plugins():
        if p.id == plugin_id:
            target = p
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    start = time.time()
    try:
        # safe_invoke handles drain/swap protection.
        # The plugin's @node execution_timeout is the plugin-side
        # ceiling; the timeout_sec is the server-side ceiling.
        # The server-side is enforced below via asyncio.wait_for.
        from functools import partial

        async def _invoke():
            loop = asyncio.get_running_loop()
            # Run the synchronous handler in a thread pool so it
            # doesn't block the asyncio event loop.
            return await loop.run_in_executor(
                None,
                partial(
                    target.safe_invoke,
                    f"{plugin_id}.{tool_name}",
                    **params,
                ),
            )

        result = await asyncio.wait_for(_invoke(), timeout=timeout_sec)
        return {
            "success": True,
            "result": result,
            "duration_ms": int((time.time() - start) * 1000),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"tool execution timed out after {timeout_sec}s",
            "duration_ms": int((time.time() - start) * 1000),
        }
    except SafeReloadError as e:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "success": False,
            "error": str(e),
            "retry_after": 5,
            "detail": "plugin is reloading; retry shortly",
        }
    except Exception as e:
        logger.exception(f"Tool execution failed: {plugin_id}.{tool_name}")
        return {
            "success": False,
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }


# ── @node discovery endpoints ────────────────────────────────────


@router.get("/nodes")
async def list_nodes(category: str | None = None) -> dict[str, Any]:
    """List all discoverable @node wrappers across the platform."""
    try:
        from common_lib.modules.plugins.nodes_registry import (
            get_node_registry,
        )

        reg = get_node_registry()
        names = reg.names if hasattr(reg, "names") else []
    except Exception as e:
        return {"nodes": [], "error": str(e)}
    if category:
        return {"nodes": [n for n in names if n.get("category") == category]}
    return {"nodes": names}


@router.get("/nodes/{node_path:path}")
async def get_node(node_path: str) -> dict[str, Any]:
    """Get one @node wrapper by its fully-qualified name."""
    try:
        from common_lib.modules.plugins.nodes_registry import (
            get_node_registry,
        )

        reg = get_node_registry()
        if hasattr(reg, "get"):
            entry = reg.get(node_path)
            if entry is None:
                raise HTTPException(
                    status_code=404, detail=f"Node '{node_path}' not found"
                )
            return entry if isinstance(entry, dict) else {"node": str(entry)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/nodes/{node_path:path}/execute")
async def execute_node(
    node_path: str, body: dict, response: Response
) -> dict[str, Any]:
    """Execute a @node wrapper by its fully-qualified name."""
    params = body.get("params", {}) or {}
    timeout_sec = float(body.get("timeout_sec", _DEFAULT_TIMEOUT))

    try:
        from common_lib.modules.plugins.nodes_registry import (
            get_node_registry,
        )

        reg = get_node_registry()
        if hasattr(reg, "get"):
            entry = reg.get(node_path)
        else:
            entry = None
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if entry is None:
        raise HTTPException(status_code=404, detail=f"Node '{node_path}' not found")

    # The entry may be a NodeInfo dataclass or a dict; get callable
    callable_fn = getattr(entry, "callable", None) or entry
    if not callable(callable_fn):
        raise HTTPException(
            status_code=400,
            detail=f"Node '{node_path}' has no callable handler",
        )

    start = time.time()
    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, lambda: callable_fn(**params)),
            timeout=timeout_sec,
        )
        return {
            "success": True,
            "result": result,
            "duration_ms": int((time.time() - start) * 1000),
        }
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"node execution timed out after {timeout_sec}s",
            "duration_ms": int((time.time() - start) * 1000),
        }
    except Exception as e:
        logger.exception(f"Node execution failed: {node_path}")
        return {
            "success": False,
            "error": str(e),
            "duration_ms": int((time.time() - start) * 1000),
        }
