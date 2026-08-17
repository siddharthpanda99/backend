"""
Nodes Catalog API

Unified endpoint for node definitions with rich metadata for Nodes Studio.
Surfaces **every** @node-decorated function across the codebase via the global
node registry (common_lib.modules.plugins.nodes_registry), which AST-scans all modules
and aggregates nodes regardless of package.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix="/nodes", tags=["nodes"])


class NodeCatalogResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]


class NodeDetailResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]


@router.get("/catalog", response_model=NodeCatalogResponse)
async def nodes_catalog(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search query"),
    tag: Optional[str] = Query(None, description="Filter by tag"),
):
    """
    Return the full catalog of **all** discovered @node functions with rich metadata.

    Powered by the global node registry (common_lib.modules.plugins.nodes_registry), which
    scans every module — so nodes defined outside image_processing (scaffolder,
    data_pipeline, memory, workflows, plugins, ...) are included too.
    """
    from common_lib.modules.plugins.nodes_registry import get_node_registry

    try:
        registry = get_node_registry()
        nodes = [_nodeinfo_to_catalog(n) for n in registry.list_nodes()]

        # Apply filters
        if category:
            nodes = [n for n in nodes if category.lower() in n["category"].lower()]
        if search:
            search_lower = search.lower()
            nodes = [
                n
                for n in nodes
                if search_lower in n["name"].lower()
                or search_lower in n.get("description", "").lower()
                or search_lower in n["category"].lower()
                or any(search_lower in t for t in n.get("tags", []))
            ]
        if tag:
            nodes = [n for n in nodes if tag in n.get("tags", [])]

        # Build category tree
        categories = {}
        for node in nodes:
            cat = node["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(node["id"])

        return NodeCatalogResponse(
            status="success",
            message=f"Found {len(nodes)} nodes",
            data={
                "nodes": nodes,
                "categories": categories,
                "total": len(nodes),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{node_id:path}", response_model=NodeDetailResponse)
async def node_detail(node_id: str):
    """
    Return detailed metadata for a specific node.
    """
    from common_lib.modules.plugins.nodes_registry import get_node_registry

    try:
        registry = get_node_registry()
        node = registry.get(node_id)

        if not node:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

        m = node.metadata or {}
        detail = {
            "id": node_id,
            "name": node.name,
            "label": node.name,
            "class_name": node.qualname,
            "category": node.category,
            "description": node.description,
            "version": node.version,
            "tags": node.tags,
            "sections": m.get("sections", []),
            "use_cases": m.get("use_cases", []),
            "recommended_usage": m.get("recommended_usage", []),
            "few_shot_examples": m.get("examples", []),
            "inputs": [{"name": k, "type": v} for k, v in node.input_schema.items()],
            "outputs": [{"name": k, "type": v} for k, v in node.output_schema.items()],
            "input_ports": m.get("input_ports", []),
            "output_ports": m.get("output_ports", []),
            "execution_timeout": node.execution_timeout,
            "execution_mode": node.execution_mode,
            "cacheable": node.cacheable,
            "idempotent": node.idempotent,
            "is_output": m.get("is_output", False),
            "function_name": "execute",
            "source_file": "",
            "line_number": 0,
            "module_path": node.module,
            "comfyui": m.get("comfyui", {}),
            "color": _get_category_color(node.category),
        }

        return NodeDetailResponse(
            status="success",
            message=f"Node '{node_id}' details",
            data=detail,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=NodeCatalogResponse)
async def node_categories():
    """Return all node categories with node counts."""
    from common_lib.modules.plugins.nodes_registry import get_node_registry

    try:
        registry = get_node_registry()
        categories: Dict[str, Dict[str, Any]] = {}
        for node in registry.list_nodes():
            cat = node.category
            if cat not in categories:
                categories[cat] = {"count": 0, "nodes": []}
            categories[cat]["count"] += 1
            categories[cat]["nodes"].append(node.name)

        return NodeCatalogResponse(
            status="success",
            message=f"Found {len(categories)} categories",
            data={"categories": categories},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _nodeinfo_to_catalog(node) -> Dict[str, Any]:
    """Map a global-registry NodeInfo into the catalog node shape."""
    return {
        "id": node.name,
        "node_id": node.name,
        "name": node.name,
        "display_name": node.name,
        "label": node.name,
        "class_name": node.qualname,
        "category": node.category,
        "description": node.description,
        "version": node.version,
        "tags": node.tags,
        "inputs": [{"name": k, "type": v} for k, v in node.input_schema.items()],
        "outputs": [{"name": k, "type": v} for k, v in node.output_schema.items()],
        "module_path": node.module,
        "function_name": "execute",
        "source_file": "",
        "line_number": 0,
        "is_output": False,
        "color": _get_category_color(node.category),
    }


def _get_category_color(category: str) -> str:
    """Get color for category."""
    colors = {
        "sam3": "#8b5cf6",
        "vision": "#10b981",
        "output": "#6366f1",
        "loaders": "#f59e0b",
        "conditioning": "#8b5cf6",
        "sampling": "#ec4899",
        "mask": "#14b8a6",
        "advanced_controlnet": "#f97316",
        "rgthree": "#06b6d4",
        "kjnodes": "#84cc16",
        "adetailer": "#ef4444",
        "segment-anything": "#22c55e",
        "segmentation": "#a855f7",
    }
    cat_lower = category.lower().split("/")[0].strip()
    return colors.get(cat_lower, "#6b7280")


class NodeSyncResponse(BaseModel):
    status: str
    message: str
    data: Dict[str, Any]


@router.post("/sync", response_model=NodeSyncResponse)
async def sync_nodes():
    """
    Discover every @node across the codebase and persist the catalog to the
    ``node_definitions`` table. This is what makes node functionality queryable
    by AI agents via the API.

    Logic lives in common_lib (image_processing.nodes_registry.startup); this
    endpoint is just the thin trigger.
    """
    from common_lib.modules.image_processing.nodes_registry.startup import (
        sync_nodes_on_startup,
    )

    try:
        count = sync_nodes_on_startup()
        return NodeSyncResponse(
            status="success",
            message=f"Synced {count} nodes to node_definitions",
            data={"synced": count},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
