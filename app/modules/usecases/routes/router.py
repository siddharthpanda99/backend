"""
Usecase Builder — Backend Routes

Multi-stage workflow management organized into use cases (apps).

Routes:
  GET    /                        List all use cases
  POST   /                        Create new use case
  GET    /{id}                    Get use case details
  PUT    /{id}                    Update use case
  DELETE /{id}                    Delete use case
  POST   /{id}/duplicate         Clone a use case

  POST   /{id}/stages            Add stage to use case
  PUT    /{id}/stages/{sid}      Update stage
  DELETE /{id}/stages/{sid}      Delete stage
  PUT    /{id}/stages/reorder    Reorder stages

  POST   /{id}/stages/{sid}/nodes       Add node to stage
  PUT    /{id}/stages/{sid}/nodes/{nid} Update node
  DELETE /{id}/stages/{sid}/nodes/{nid} Delete node

  POST   /{id}/stages/{sid}/test        Test a single stage
  POST   /{id}/run                      Run full use case end-to-end

  GET    /templates                     Get built-in templates
  GET    /categories                    Get available categories
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["usecases"])


# ── Schemas ─────────────────────────────────────────────────────────────
class UsecaseCreateRequest(BaseModel):
    name: str
    description: str = ""
    category: str = "custom"
    icon: str = "📋"
    tags: List[str] = Field(default_factory=list)


class UsecaseUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    icon: Optional[str] = None
    tags: Optional[List[str]] = None
    status: Optional[str] = None


class StageCreateRequest(BaseModel):
    name: str
    description: str = ""
    merge_strategy: str = "sequential"


class StageUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    merge_strategy: Optional[str] = None
    parallel: Optional[bool] = None


class NodeCreateRequest(BaseModel):
    name: str
    method: str
    params: Dict[str, Any] = Field(default_factory=dict)
    input_from: Optional[str] = None


class NodeUpdateRequest(BaseModel):
    name: Optional[str] = None
    method: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    input_from: Optional[str] = None


class ReorderRequest(BaseModel):
    stage_ids: List[str]


class TestStageRequest(BaseModel):
    source_image: Optional[str] = None


class RunRequest(BaseModel):
    source_image: Optional[str] = None


# ── Service singleton ───────────────────────────────────────────────────
_service = None


def _get_service():
    global _service
    if _service is None:
        from common_lib.modules.image_processing.services.usecase_builder_service import (
            UsecaseBuilderService,
        )
        _service = UsecaseBuilderService()
    return _service


# ── Usecase CRUD ────────────────────────────────────────────────────────
@router.get("/")
async def list_usecases(category: Optional[str] = None):
    """List all use cases, optionally filtered by category."""
    ucs = _get_service().list_usecases(category)
    return {
        "status": "success",
        "usecases": [_uc_response(u) for u in ucs],
        "total": len(ucs),
    }


@router.post("/")
async def create_usecase(req: UsecaseCreateRequest):
    """Create a new use case."""
    uc = _get_service().create_usecase(
        name=req.name,
        description=req.description,
        category=req.category,
        icon=req.icon,
        tags=req.tags,
    )
    return {"status": "success", "usecase": _uc_response(uc)}


@router.get("/templates")
async def get_templates():
    """Get built-in use case templates."""
    from common_lib.modules.image_processing.services.usecase_builder_service import (
        _ai_influencer_template,
        _nature_photography_template,
        _fashion_clothing_template,
        _product_photography_template,
    )
    templates = [
        _ai_influencer_template(),
        _nature_photography_template(),
        _fashion_clothing_template(),
        _product_photography_template(),
    ]
    return {
        "status": "success",
        "templates": [_uc_response(t) for t in templates],
    }


@router.get("/categories")
async def get_categories():
    """Get available use case categories."""
    return {
        "status": "success",
        "categories": [
            {"id": "ai_influencer", "label": "AI Influencer", "icon": "👤"},
            {"id": "nature", "label": "Nature Photography", "icon": "🌄"},
            {"id": "fashion", "label": "Fashion & Clothing", "icon": "👗"},
            {"id": "product", "label": "Product Photography", "icon": "📦"},
            {"id": "portrait", "label": "Portrait Studio", "icon": "🖼️"},
            {"id": "creative", "label": "Creative & Artistic", "icon": "🎨"},
            {"id": "video", "label": "Video & Animation", "icon": "🎬"},
            {"id": "custom", "label": "Custom", "icon": "📋"},
        ],
    }


@router.get("/{uc_id}")
async def get_usecase(uc_id: str):
    """Get use case details with all stages and nodes."""
    uc = _get_service().get_usecase(uc_id)
    if not uc:
        raise HTTPException(status_code=404, detail=f"Use case {uc_id} not found")
    return {"status": "success", "usecase": _uc_response(uc)}


@router.put("/{uc_id}")
async def update_usecase(uc_id: str, req: UsecaseUpdateRequest):
    """Update use case metadata."""
    updates = req.model_dump(exclude_none=True)
    uc = _get_service().update_usecase(uc_id, **updates)
    if not uc:
        raise HTTPException(status_code=404, detail=f"Use case {uc_id} not found")
    return {"status": "success", "usecase": _uc_response(uc)}


@router.delete("/{uc_id}")
async def delete_usecase(uc_id: str):
    """Delete a use case."""
    deleted = _get_service().delete_usecase(uc_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Use case {uc_id} not found")
    return {"status": "success", "deleted": uc_id}


@router.post("/{uc_id}/duplicate")
async def duplicate_usecase(uc_id: str, name: Optional[str] = None):
    """Clone a use case with all its stages and nodes."""
    clone = _get_service().duplicate_usecase(uc_id, name)
    if not clone:
        raise HTTPException(status_code=404, detail=f"Use case {uc_id} not found")
    return {"status": "success", "usecase": _uc_response(clone)}


# ── Stage Management ────────────────────────────────────────────────────
@router.post("/{uc_id}/stages")
async def add_stage(uc_id: str, req: StageCreateRequest):
    """Add a workflow stage to a use case."""
    stage = _get_service().add_stage(
        uc_id, name=req.name, description=req.description,
        merge_strategy=req.merge_strategy,
    )
    if not stage:
        raise HTTPException(status_code=404, detail=f"Use case {uc_id} not found")
    return {"status": "success", "stage": _stage_response(stage)}


@router.put("/{uc_id}/stages/{stage_id}")
async def update_stage(uc_id: str, stage_id: str, req: StageUpdateRequest):
    """Update a workflow stage."""
    updates = req.model_dump(exclude_none=True)
    stage = _get_service().update_stage(uc_id, stage_id, **updates)
    if not stage:
        raise HTTPException(status_code=404, detail="Stage not found")
    return {"status": "success", "stage": _stage_response(stage)}


@router.delete("/{uc_id}/stages/{stage_id}")
async def delete_stage(uc_id: str, stage_id: str):
    """Delete a workflow stage."""
    deleted = _get_service().delete_stage(uc_id, stage_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Stage not found")
    return {"status": "success", "deleted": stage_id}


@router.put("/{uc_id}/stages/reorder")
async def reorder_stages(uc_id: str, req: ReorderRequest):
    """Reorder stages within a use case."""
    ok = _get_service().reorder_stages(uc_id, req.stage_ids)
    if not ok:
        raise HTTPException(status_code=400, detail="Reorder failed")
    return {"status": "success"}


# ── Node Management ─────────────────────────────────────────────────────
@router.post("/{uc_id}/stages/{stage_id}/nodes")
async def add_node(uc_id: str, stage_id: str, req: NodeCreateRequest):
    """Add a node (operation) to a workflow stage."""
    node = _get_service().add_node(
        uc_id, stage_id,
        name=req.name, method=req.method,
        params=req.params, input_from=req.input_from,
    )
    if not node:
        raise HTTPException(status_code=404, detail="Stage not found")
    return {"status": "success", "node": _node_response(node)}


@router.put("/{uc_id}/stages/{stage_id}/nodes/{node_id}")
async def update_node(uc_id: str, stage_id: str, node_id: str, req: NodeUpdateRequest):
    """Update a node's configuration."""
    updates = req.model_dump(exclude_none=True)
    node = _get_service().update_node(uc_id, stage_id, node_id, **updates)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "success", "node": _node_response(node)}


@router.delete("/{uc_id}/stages/{stage_id}/nodes/{node_id}")
async def delete_node(uc_id: str, stage_id: str, node_id: str):
    """Delete a node from a stage."""
    deleted = _get_service().delete_node(uc_id, stage_id, node_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"status": "success", "deleted": node_id}


# ── Execution ───────────────────────────────────────────────────────────
@router.post("/{uc_id}/stages/{stage_id}/test")
async def test_stage(uc_id: str, stage_id: str, req: TestStageRequest = None):
    """Test a single stage independently."""
    source = req.source_image if req else None
    result = await _get_service().test_stage(uc_id, stage_id, source)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success", **result}


@router.post("/{uc_id}/run")
async def run_usecase(uc_id: str, req: RunRequest = None):
    """Run the full use case end-to-end across all stages."""
    source = req.source_image if req else None
    result = await _get_service().run_usecase(uc_id, source)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"status": "success", **result}


# ── Analytics ──────────────────────────────────────────────────────────

@router.get("/analytics")
async def get_all_analytics():
    """Get analytics across all use cases."""
    return {"status": "success", "analytics": _get_service().get_analytics()}


@router.get("/{uc_id}/analytics")
async def get_usecase_analytics(uc_id: str):
    """Get analytics for a specific use case."""
    result = _get_service().get_analytics(uc_id)
    if 'error' in result:
        raise HTTPException(status_code=404, detail=result['error'])
    return {"status": "success", "analytics": result}


# ── Helpers ─────────────────────────────────────────────────────────────
def _uc_response(uc) -> Dict[str, Any]:
    return {
        "id": uc.id,
        "name": uc.name,
        "description": uc.description,
        "category": uc.category,
        "icon": uc.icon,
        "stages": [_stage_response(s) for s in uc.stages],
        "merge_strategy": uc.merge_strategy.value if hasattr(uc.merge_strategy, "value") else uc.merge_strategy,
        "status": uc.status.value if hasattr(uc.status, "value") else uc.status,
        "tags": uc.tags,
        "stage_count": len(uc.stages),
        "node_count": sum(len(s.nodes) for s in uc.stages),
        "run_count": len(uc.run_history),
        "last_run": uc.run_history[-1] if uc.run_history else None,
        "created_at": uc.created_at,
        "updated_at": uc.updated_at,
    }


def _stage_response(stage) -> Dict[str, Any]:
    return {
        "id": stage.id,
        "name": stage.name,
        "description": stage.description,
        "nodes": [_node_response(n) for n in stage.nodes],
        "merge_strategy": stage.merge_strategy.value if hasattr(stage.merge_strategy, "value") else stage.merge_strategy,
        "parallel": stage.parallel,
        "status": stage.status.value if hasattr(stage.status, "value") else stage.status,
        "node_count": len(stage.nodes),
        "last_run_at": stage.last_run_at,
        "last_result_summary": stage.last_result_summary,
    }


def _node_response(node) -> Dict[str, Any]:
    return {
        "id": node.id,
        "name": node.name,
        "method": node.method,
        "params": node.params,
        "input_from": node.input_from,
        "output_key": node.output_key,
        "status": node.status.value if hasattr(node.status, "value") else node.status,
        "last_run_ms": node.last_run_ms,
        "last_error": node.last_error,
    }
