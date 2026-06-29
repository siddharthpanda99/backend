"""FastAPI MCP server wrapper for workflow testing.

Delegates all logic to pure handler functions in common_lib.
No business logic lives here — this is a thin FastAPI wrapper only.
"""

import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


def create_app(registry=None, suite=None):
    """Create a FastAPI app that wraps the pure RPC handlers from common_lib.

    This is the only function in this file that depends on FastAPI.
    All business logic is delegated to common_lib handlers.
    The handlers lazily initialise their own state from common_lib's module scope.
    """
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from common_lib.modules.workflows.testing.mcp_server import (
        handle_rpc,
        _make_rpc,
        get_agent_examples,
        HandlerNotFound,
    )

    app = FastAPI(
        title="Workflow Testing MCP Server",
        description="MCP server for AI-driven workflow testing. "
        "Exposes workflow discovery, config generation, execution, and reporting.",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    _AGENT_EXAMPLES = get_agent_examples()

    @app.post("/")
    async def rpc_handler(request: Request):
        body = await request.json()
        req_id = body.get("id", 1)
        method = body.get("method", "")
        params = body.get("params", {})

        try:
            result = await handle_rpc(method, params)
            return _make_rpc(method, result=result, req_id=req_id)
        except HandlerNotFound as e:
            return _make_rpc(
                method,
                error={"code": -32000, "message": str(e)},
                req_id=req_id,
            )
        except ValueError as e:
            return _make_rpc(
                method,
                error={
                    "code": -32601,
                    "message": str(e),
                    "data": {"available_methods": list(_AGENT_EXAMPLES.keys())},
                },
                req_id=req_id,
            )
        except Exception as e:
            logger.exception(f"MCP method {method} failed")
            return _make_rpc(
                method,
                error={"code": -32603, "message": str(e), "data": traceback.format_exc()},
                req_id=req_id,
            )

    @app.get("/health")
    async def health():
        return {
            "jsonrpc": "2.0",
            "result": {
                "status": "ok",
                "service": "Workflow Testing MCP Server",
                "version": "1.0.0",
                "methods": list(_AGENT_EXAMPLES.keys()),
                "timestamp": datetime.utcnow().isoformat(),
            },
            "id": None,
        }

    @app.get("/tools")
    async def tools():
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": {
                    name: {"method": name, "agent_description": info["agent_description"]}
                    for name, info in _AGENT_EXAMPLES.items()
                }
            },
            "id": None,
        }

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_json():
        return app.openapi()

    return app
