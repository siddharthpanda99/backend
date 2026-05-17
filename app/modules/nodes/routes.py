"""
Nodes Catalog API

Unified endpoint for node definitions with rich metadata for Nodes Studio.
Merges @node decorator pattern with ComfyUI class pattern.
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
    Return the full catalog of all discovered nodes with rich metadata.

    Supports filtering by category, search query, and tags.
    Returns unified node definitions compatible with both workflow engine
    and ComfyUI execution.
    """
    from common_lib.modules.image_processing.nodes_registry.discovery import (
        get_node_registry,
    )

    try:
        registry = get_node_registry()
        nodes = registry.to_catalog_response()

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


@router.get("/catalog/{node_id}", response_model=NodeDetailResponse)
async def node_detail(node_id: str):
    """
    Return detailed metadata for a specific node.

    Includes full documentation, use cases, examples, I/O ports,
    and ComfyUI compatibility info.
    """
    from common_lib.modules.image_processing.nodes_registry.discovery import (
        get_node_registry,
    )

    try:
        registry = get_node_registry()
        node = registry.get_node(node_id)

        if not node:
            raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found")

        unified_meta = (
            node.get("_unified_metadata", {}) or node.get("_node_metadata", {}) or {}
        )

        detail = {
            # Core identity
            "id": node_id,
            "name": node.get("node_id", node_id),
            "label": node.get("display_name", node_id),
            "class_name": node.get("class_name", ""),
            "category": node["category"],
            "description": node.get("description", ""),
            "version": node.get("version", "1.0.0"),
            "tags": node.get("tags", []),
            # Rich documentation
            "sections": node.get("sections", []),
            "use_cases": node.get("use_cases", []),
            "recommended_usage": node.get("recommended_usage", []),
            "few_shot_examples": node.get("few_shot_examples", []),
            # Ports
            "inputs": node["inputs"],
            "outputs": node["outputs"],
            "input_ports": unified_meta.get("input_ports", []),
            "output_ports": unified_meta.get("output_ports", []),
            # Execution
            "execution_timeout": unified_meta.get("execution_timeout", 60),
            "execution_mode": unified_meta.get("execution_mode", "sync"),
            "cacheable": unified_meta.get("cacheable", False),
            "idempotent": unified_meta.get("idempotent", False),
            "is_output": node.get("is_output", False),
            "function_name": node.get("function_name", "execute"),
            # Source location
            "source_file": node.get("source_file", ""),
            "line_number": node.get("line_number", 0),
            "module_path": node.get("module_path", ""),
            # ComfyUI compatibility
            "comfyui": unified_meta.get("comfyui", {}),
            # UI hints
            "color": _get_category_color(node["category"]),
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
    from common_lib.modules.image_processing.nodes_registry.discovery import (
        get_node_registry,
    )

    try:
        registry = get_node_registry()
        categories = registry.get_categories()

        result = {
            cat: {"count": len(nodes), "nodes": nodes}
            for cat, nodes in categories.items()
        }

        return NodeCatalogResponse(
            status="success",
            message=f"Found {len(result)} categories",
            data={"categories": result},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
