"""Extensions Server — Hot-Loadable Extensions for the Platform.

A separate FastAPI server that:
1. Manages extensions (ComfyUI nodes, git repos, Python packages)
2. Hot-loads them without restart
3. Exposes them via REST API and MCP
4. The main platform accesses them via HTTP or MCP bridge

Run:
    python -m app.extensions_server.main
    # or
    uvicorn app.extensions_server.main:app --host 0.0.0.0 --port 8082

Architecture:
    ┌─────────────────────────────────────────┐
    │         Extensions Server (8082)        │
    │  ┌──────────┐  ┌──────────┐  ┌───────┐ │
    │  │ REST API │  │MCP Server│  │Loader │ │
    │  └────┬─────┘  └────┬─────┘  └───┬───┘ │
    │       └──────────────┼────────────┘     │
    │                      ▼                  │
    │              ExtensionRegistry          │
    │  ┌──────────┐ ┌──────────┐ ┌────────┐  │
    │  │ ComfyUI  │ │Git Repos │ │Packages│  │
    │  │  Nodes   │ │          │ │        │  │
    │  └──────────┘ └──────────┘ └────────┘  │
    └─────────────────────────────────────────┘
              │ API/MCP
              ▼
    ┌─────────────────────────────────────────┐
    │      Main Platform (8000)               │
    │  - Discovers extension nodes            │
    │  - Executes extension functions         │
    │  - Exposes to AI agents via @node       │
    └─────────────────────────────────────────┘
"""

from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add common_lib to path
_common_lib_src = os.path.join(
    os.path.dirname(__file__), "..", "..", "..",
    "Backend Monorepo", "Python Libs", "common_lib", "src"
)
if os.path.isdir(_common_lib_src):
    sys.path.insert(0, _common_lib_src)

from common_lib.modules.extensions.models import (
    Extension,
    ExtensionCreate,
    ExtensionStatus,
    ExtensionType,
    ExtensionUpdate,
)
from common_lib.modules.extensions.registry.extension_registry import (
    get_extension_registry,
)

logger = logging.getLogger(__name__)

# ── Lifespan ────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    logger.info("Extensions Server starting...")

    # Auto-discover ComfyUI custom nodes from Extras/ComfyUI/custom_nodes/
    _auto_discover_comfyui_nodes()

    registry = get_extension_registry()
    snapshot = registry.snapshot()
    logger.info(
        f"Extensions Server ready: {snapshot['total_extensions']} extensions, "
        f"{snapshot['total_nodes']} nodes"
    )
    yield
    logger.info("Extensions Server shutting down...")


def _auto_discover_comfyui_nodes():
    """Auto-discover ComfyUI custom nodes from the Extras directory."""
    registry = get_extension_registry()

    # Find the ComfyUI custom_nodes directory
    extras_dir = None
    for candidate in [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "Extras", "ComfyUI", "custom_nodes"),
        os.path.join(os.environ.get("MONOREPO_ROOT", "."), "Extras", "ComfyUI", "custom_nodes"),
    ]:
        candidate = os.path.normpath(candidate)
        if os.path.isdir(candidate):
            extras_dir = candidate
            break

    if not extras_dir:
        logger.warning("ComfyUI custom_nodes directory not found — skipping auto-discovery")
        return

    logger.info(f"Auto-discovering ComfyUI nodes from {extras_dir}")

    discovered = 0
    for item in os.listdir(extras_dir):
        item_path = os.path.join(extras_dir, item)
        if not os.path.isdir(item_path) or item.startswith("_"):
            continue

        # Check if it has __init__.py or .py files
        has_python = any(f.endswith(".py") for f in os.listdir(item_path))
        if not has_python:
            continue

        # Register but don't load (lazy)
        ext = Extension(
            name=f"comfyui.{item}",
            extension_type=ExtensionType.COMFYUI_NODE,
            source_path=item_path,
            description=f"ComfyUI custom node: {item}",
            tags=["comfyui", "auto-discovered"],
            status=ExtensionStatus.REGISTERED,
        )
        registry.register(ext)
        discovered += 1

    logger.info(f"Auto-discovered {discovered} ComfyUI custom node packages")


# ── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(
    title="Extensions Server",
    description="Hot-loadable extensions for the AI platform. Manages ComfyUI nodes, git repos, and Python packages.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── REST API ────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check."""
    registry = get_extension_registry()
    return {"status": "ok", **registry.snapshot()}


@app.get("/extensions")
async def list_extensions(
    status: Optional[str] = None,
    extension_type: Optional[str] = None,
):
    """List all registered extensions."""
    registry = get_extension_registry()
    status_enum = ExtensionStatus(status) if status else None
    type_enum = ExtensionType(extension_type) if extension_type else None
    extensions = registry.list_extensions(status=status_enum, extension_type=type_enum)
    return {"extensions": [ext.model_dump() for ext in extensions]}


@app.get("/extensions/{extension_id}")
async def get_extension(extension_id: str):
    """Get a specific extension."""
    registry = get_extension_registry()
    ext = registry.get(extension_id)
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_id}' not found")
    return ext.model_dump()


@app.post("/extensions")
async def create_extension(request: ExtensionCreate):
    """Register a new extension."""
    registry = get_extension_registry()
    ext = Extension(
        name=request.name,
        extension_type=request.extension_type,
        source_url=request.source_url,
        source_path=request.source_path,
        source_branch=request.source_branch,
        description=request.description,
        author=request.author,
        tags=request.tags,
        config=request.config,
    )
    registry.register(ext)
    return ext.model_dump()


@app.put("/extensions/{extension_id}")
async def update_extension(extension_id: str, request: ExtensionUpdate):
    """Update an extension's metadata."""
    registry = get_extension_registry()
    ext = registry.get(extension_id)
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_id}' not found")

    if request.description is not None:
        ext.description = request.description
    if request.source_branch is not None:
        ext.source_branch = request.source_branch
    if request.config is not None:
        ext.config = request.config
    if request.tags is not None:
        ext.tags = request.tags

    ext.updated_at = __import__("datetime").datetime.utcnow()
    return ext.model_dump()


@app.delete("/extensions/{extension_id}")
async def delete_extension(extension_id: str):
    """Unregister and remove an extension."""
    registry = get_extension_registry()
    success = registry.unregister(extension_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_id}' not found")
    return {"status": "deleted", "extension_id": extension_id}


# ── Loading ─────────────────────────────────────────────────────────

@app.post("/extensions/{extension_id}/load")
async def load_extension(extension_id: str):
    """Load an extension's nodes into memory."""
    registry = get_extension_registry()
    success = registry.load(extension_id)
    ext = registry.get(extension_id)
    if not ext:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_id}' not found")
    return {
        "status": "loaded" if success else "error",
        "extension_id": extension_id,
        "nodes_loaded": len(ext.nodes),
        "error": ext.error_message,
    }


@app.post("/extensions/{extension_id}/unload")
async def unload_extension(extension_id: str):
    """Unload an extension's nodes."""
    registry = get_extension_registry()
    success = registry.unload(extension_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Extension '{extension_id}' not found")
    return {"status": "unloaded", "extension_id": extension_id}


@app.post("/extensions/{extension_id}/reload")
async def reload_extension(extension_id: str):
    """Reload an extension (unload + load)."""
    registry = get_extension_registry()
    success = registry.reload(extension_id)
    ext = registry.get(extension_id)
    return {
        "status": "reloaded" if success else "error",
        "extension_id": extension_id,
        "nodes_loaded": len(ext.nodes) if ext else 0,
        "error": ext.error_message if ext else None,
    }


@app.post("/extensions/{extension_id}/sync")
async def sync_extension(extension_id: str):
    """Sync an extension from its source (git pull, etc.)."""
    registry = get_extension_registry()
    result = registry.sync_from_source(extension_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Sync failed"))
    return result


@app.post("/extensions/load-all")
async def load_all_extensions():
    """Load all registered extensions."""
    registry = get_extension_registry()
    results = []
    for ext in registry.list_extensions(status=ExtensionStatus.REGISTERED):
        success = registry.load(ext.id)
        results.append({
            "extension_id": ext.id,
            "name": ext.name,
            "success": success,
            "nodes_loaded": len(ext.nodes),
        })
    return {"results": results}


# ── Node Discovery ──────────────────────────────────────────────────

@app.get("/nodes")
async def list_all_nodes():
    """List all nodes from all active extensions."""
    registry = get_extension_registry()
    return {"nodes": registry.get_all_nodes()}


@app.get("/nodes/{node_name}")
async def get_node(node_name: str):
    """Get a specific node's details."""
    registry = get_extension_registry()
    for node in registry.get_all_nodes():
        if node["name"] == node_name:
            return node
    raise HTTPException(status_code=404, detail=f"Node '{node_name}' not found")


@app.post("/nodes/{node_name}/execute")
async def execute_node(node_name: str, kwargs: Dict[str, Any] = {}):
    """Execute a node by name."""
    registry = get_extension_registry()
    try:
        result = registry.execute_node(node_name, **kwargs)
        return {"status": "success", "result": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Snapshot ────────────────────────────────────────────────────────

@app.get("/snapshot")
async def snapshot():
    """Get a snapshot of the entire extensions registry."""
    registry = get_extension_registry()
    return registry.snapshot()


# ── MCP Bridge ──────────────────────────────────────────────────────

@app.get("/mcp/tools")
async def mcp_tools():
    """List all extension nodes as MCP-compatible tools."""
    registry = get_extension_registry()
    nodes = registry.get_all_nodes()
    tools = []
    for node in nodes:
        tools.append({
            "name": node["name"],
            "description": node["description"],
            "inputSchema": node["input_schema"],
            "category": node["category"],
            "source": f"extension:{node['extension_name']}",
        })
    return {"tools": tools, "count": len(tools)}


@app.post("/mcp/execute")
async def mcp_execute(request: Dict[str, Any]):
    """Execute a tool via MCP interface."""
    tool_name = request.get("name", "")
    arguments = request.get("arguments", {})

    registry = get_extension_registry()
    try:
        result = registry.execute_node(tool_name, **arguments)
        return {"content": [{"type": "text", "text": str(result)}]}
    except ValueError as e:
        return {"content": [{"type": "text", "text": f"Error: {e}"}], "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": f"Execution error: {e}"}], "isError": True}


# ── Main ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO)
    port = int(os.environ.get("EXTENSIONS_SERVER_PORT", 8082))
    uvicorn.run(app, host="0.0.0.0", port=port)
