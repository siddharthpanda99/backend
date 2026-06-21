"""
Visual UI Builder — FastAPI Routes

/api/v1/builder/ — CRUD for canvas presets, design tokens, and canvas state
"""

import logging
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schemas import (
    CanvasPresetCreate, CanvasPresetUpdate, CanvasPresetSchema,
    PresetListResponse, APIResponse,
    DesignTokenCreate, DesignTokenUpdate, DesignTokenSchema,
    DesignTokenListResponse,
    CanvasStateSave, CanvasStateResponse,
    DataBindingCreate, DataBindingUpdate, DataBindingSchema,
    DataBindingListResponse, DataBindingTestRequest, DataBindingTestResponse,
    PresetVersionCreate, PresetVersionSchema, PresetVersionListResponse,
    CommentCreate, CommentUpdate, CommentSchema, CommentListResponse,
    InteractionCreate, InteractionUpdate, InteractionSchema, InteractionListResponse,
    AssetCreate, AssetSchema, AssetListResponse,
    PluginCreate, PluginUpdate, PluginSchema, PluginListResponse,
)
from common_lib.modules.app_builder.service import BuilderService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/builder", tags=["UI Builder"])
service = BuilderService()


# ═══════════════════════════════════════════════════════════════════
# Canvas Presets
# ═══════════════════════════════════════════════════════════════════

@router.get("/presets", response_model=PresetListResponse)
async def list_presets(
    app_id: str = Query(..., description="App ID to scope presets"),
    category: Optional[str] = Query(None),
    preset_type: Optional[str] = Query(None),
    parent_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_session),
):
    """List all presets for an app with optional filters."""
    presets, total = service.list_presets(
        db, app_id, category=category, preset_type=preset_type,
        parent_id=parent_id, search=search, page=page, page_size=page_size
    )
    return PresetListResponse(presets=presets, total=total, app_id=app_id)


@router.get("/presets/{preset_id}", response_model=CanvasPresetSchema)
async def get_preset(preset_id: str, db: Session = Depends(get_session)):
    """Get a single preset by ID."""
    preset = service.get_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    return preset


@router.post("/presets", response_model=APIResponse, status_code=201)
async def create_preset(
    app_id: str = Query(...),
    data: CanvasPresetCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Create a new preset for an app."""
    preset = service.create_preset(db, app_id, data)
    return APIResponse(
        status="success",
        message=f"Preset '{preset.name}' created",
        data=preset.model_dump(),
    )


@router.put("/presets/{preset_id}", response_model=APIResponse)
async def update_preset(
    preset_id: str,
    data: CanvasPresetUpdate = Body(...),
    db: Session = Depends(get_session),
):
    """Update an existing preset."""
    preset = service.update_preset(db, preset_id, data)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    return APIResponse(
        status="success",
        message=f"Preset '{preset.name}' updated",
        data=preset.model_dump(),
    )


@router.delete("/presets/{preset_id}", response_model=APIResponse)
async def delete_preset(preset_id: str, db: Session = Depends(get_session)):
    """Delete a preset and its child presets."""
    success = service.delete_preset(db, preset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    return APIResponse(status="success", message=f"Preset '{preset_id}' deleted")


@router.post("/presets/{preset_id}/duplicate", response_model=APIResponse, status_code=201)
async def duplicate_preset(
    preset_id: str,
    app_id: str = Query(...),
    db: Session = Depends(get_session),
):
    """Duplicate a preset (including its children)."""
    preset = service.duplicate_preset(db, preset_id, app_id)
    if not preset:
        raise HTTPException(status_code=404, detail=f"Preset '{preset_id}' not found")
    return APIResponse(
        status="success",
        message=f"Preset duplicated as '{preset.name}'",
        data=preset.model_dump(),
    )


# ═══════════════════════════════════════════════════════════════════
# Canvas State (Bulk Save/Load)
# ═══════════════════════════════════════════════════════════════════

@router.get("/canvas/{app_id}", response_model=CanvasStateResponse)
async def get_canvas_state(app_id: str, db: Session = Depends(get_session)):
    """Load the full canvas state for an app (all presets + view state)."""
    return service.get_canvas_state(db, app_id)


@router.post("/canvas/{app_id}", response_model=APIResponse)
async def save_canvas_state(
    app_id: str,
    data: CanvasStateSave = Body(...),
    db: Session = Depends(get_session),
):
    """Save the full DesignCanvas state for an app (replaces all presets)."""
    presets = service.save_canvas_state(db, app_id, data)
    return APIResponse(
        status="success",
        message=f"Canvas state saved ({len(presets)} presets)",
        data={"presets": [p.model_dump() for p in presets]},
    )


# ═══════════════════════════════════════════════════════════════════
# Design Tokens
# ═══════════════════════════════════════════════════════════════════

@router.get("/tokens", response_model=DesignTokenListResponse)
async def list_tokens(
    app_id: str = Query(...),
    mode: Optional[str] = Query(None),
    token_type: Optional[str] = Query(None),
    namespace: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """List design tokens for an app."""
    tokens = service.list_tokens(db, app_id, mode=mode, token_type=token_type, namespace=namespace)
    return DesignTokenListResponse(
        tokens=tokens,
        total=len(tokens),
        app_id=app_id,
    )


@router.post("/tokens", response_model=APIResponse, status_code=201)
async def create_token(
    app_id: str = Query(...),
    data: DesignTokenCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Create a new design token."""
    token = service.create_token(db, app_id, data)
    return APIResponse(
        status="success",
        message=f"Token '{token.name}' created",
        data=token.model_dump(),
    )


@router.put("/tokens/{token_id}", response_model=APIResponse)
async def update_token(
    token_id: str,
    data: DesignTokenUpdate = Body(...),
    db: Session = Depends(get_session),
):
    """Update a design token."""
    token = service.update_token(db, token_id, data)
    if not token:
        raise HTTPException(status_code=404, detail=f"Token '{token_id}' not found")
    return APIResponse(
        status="success",
        message=f"Token '{token.name}' updated",
        data=token.model_dump(),
    )


@router.delete("/tokens/{token_id}", response_model=APIResponse)
async def delete_token(token_id: str, db: Session = Depends(get_session)):
    """Delete a design token."""
    success = service.delete_token(db, token_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Token '{token_id}' not found")
    return APIResponse(status="success", message=f"Token '{token_id}' deleted")


# ═══════════════════════════════════════════════════════════════════
# Data Bindings
# ═══════════════════════════════════════════════════════════════════

@router.get("/bindings", response_model=DataBindingListResponse)
async def list_bindings(
    app_id: str = Query(...),
    preset_id: Optional[str] = Query(None, description="Filter by preset"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    db: Session = Depends(get_session),
):
    """List data bindings for an app, optionally filtered by preset."""
    bindings = service.list_bindings(db, app_id, preset_id=preset_id, source_type=source_type)
    return DataBindingListResponse(
        bindings=bindings,
        total=len(bindings),
        app_id=app_id,
    )


@router.post("/bindings", response_model=APIResponse, status_code=201)
async def create_binding(
    app_id: str = Query(...),
    data: DataBindingCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Create a new data binding."""
    binding = service.create_binding(db, app_id, data)
    return APIResponse(
        status="success",
        message=f"Binding '{binding.id}' created",
        data=binding.model_dump(),
    )


@router.put("/bindings/{binding_id}", response_model=APIResponse)
async def update_binding(
    binding_id: str,
    data: DataBindingUpdate = Body(...),
    db: Session = Depends(get_session),
):
    """Update a data binding."""
    binding = service.update_binding(db, binding_id, data)
    if not binding:
        raise HTTPException(status_code=404, detail=f"Binding '{binding_id}' not found")
    return APIResponse(
        status="success",
        message=f"Binding '{binding.id}' updated",
        data=binding.model_dump(),
    )


@router.delete("/bindings/{binding_id}", response_model=APIResponse)
async def delete_binding(binding_id: str, db: Session = Depends(get_session)):
    """Delete a data binding."""
    success = service.delete_binding(db, binding_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Binding '{binding_id}' not found")
    return APIResponse(status="success", message=f"Binding '{binding_id}' deleted")


@router.post("/bindings/test", response_model=DataBindingTestResponse)
async def test_binding(
    data: DataBindingTestRequest = Body(...),
):
    """Test a data source connection and return a preview of the data."""
    return await service.test_binding(data)


@router.post("/bindings/{binding_id}/test", response_model=DataBindingTestResponse)
async def test_existing_binding(
    binding_id: str,
    db: Session = Depends(get_session),
):
    """Test an existing data binding by its ID."""
    try:
        return await service.test_existing_binding(db, binding_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Layout Computation (Auto-Layout + Constraints)
# ═══════════════════════════════════════════════════════════════════

from pydantic import BaseModel

class LayoutComputeRequest(BaseModel):
    """Request to compute auto-layout positions for presets."""
    presets: List[Dict[str, Any]] = []
    parent_id: str = ""
    parent_width: float = 0
    parent_height: float = 0
    auto_layout: Optional[Dict[str, Any]] = None
    constraints: Optional[Dict[str, Any]] = None
    old_parent_width: Optional[float] = None
    old_parent_height: Optional[float] = None


class LayoutComputeChild(BaseModel):
    preset_id: str = ""
    x: float = 0
    y: float = 0
    width: float = 100
    height: float = 80


class LayoutComputeResponse(BaseModel):
    """Result of layout computation."""
    children: List[LayoutComputeChild] = []
    content_width: float = 0
    content_height: float = 0
    overflow: bool = False


@router.post("/layout/compute", response_model=LayoutComputeResponse)
async def compute_layout(
    data: LayoutComputeRequest = Body(...),
):
    """Compute auto-layout positions for children of a preset."""
    children: List[LayoutComputeChild] = []
    
    if not data.auto_layout or not data.auto_layout.get("enabled"):
        if data.constraints and data.old_parent_width is not None and data.old_parent_height is not None:
            dw = data.parent_width - data.old_parent_width
            dh = data.parent_height - data.old_parent_height
            
            for preset_data in data.presets:
                child = LayoutComputeChild(
                    preset_id=preset_data.get("id", ""),
                    x=preset_data.get("pos_x", preset_data.get("x", 0)),
                    y=preset_data.get("pos_y", preset_data.get("y", 0)),
                    width=preset_data.get("width", 100),
                    height=preset_data.get("height", 80),
                )
                
                h_constraint = data.constraints.get("horizontal", "left")
                v_constraint = data.constraints.get("vertical", "top")
                
                if h_constraint == "right":
                    child.x = child.x + dw
                elif h_constraint == "center":
                    child.x = child.x + dw / 2
                elif h_constraint == "scale" and data.old_parent_width > 0:
                    x_ratio = child.x / data.old_parent_width
                    w_ratio = child.width / data.old_parent_width
                    child.x = data.parent_width * x_ratio
                    child.width = data.parent_width * w_ratio
                elif h_constraint == "stretch":
                    child.x = 0
                    child.width = data.parent_width
                
                if v_constraint == "bottom":
                    child.y = child.y + dh
                elif v_constraint == "center":
                    child.y = child.y + dh / 2
                elif v_constraint == "scale" and data.old_parent_height > 0:
                    y_ratio = child.y / data.old_parent_height
                    h_ratio = child.height / data.old_parent_height
                    child.y = data.parent_height * y_ratio
                    child.height = data.parent_height * h_ratio
                elif v_constraint == "stretch":
                    child.y = 0
                    child.height = data.parent_height
                
                children.append(child)
        else:
            for preset_data in data.presets:
                children.append(LayoutComputeChild(
                    preset_id=preset_data.get("id", ""),
                    x=preset_data.get("pos_x", preset_data.get("x", 0)),
                    y=preset_data.get("pos_y", preset_data.get("y", 0)),
                    width=preset_data.get("width", 100),
                    height=preset_data.get("height", 80),
                ))
        
        return LayoutComputeResponse(
            children=children,
            content_width=data.parent_width,
            content_height=data.parent_height,
            overflow=False,
        )
    
    # Auto-layout computation
    direction = data.auto_layout.get("direction", "vertical")
    padding = data.auto_layout.get("padding", {"top": 0, "right": 0, "bottom": 0, "left": 0})
    gap = data.auto_layout.get("gap", 8)
    alignment = data.auto_layout.get("alignment", "top-left")
    sizing = data.auto_layout.get("sizing", "fixed")
    
    is_horizontal = direction == "horizontal"
    
    content_left = padding.get("left", 0)
    content_top = padding.get("top", 0)
    content_width = data.parent_width - content_left - padding.get("right", 0)
    content_height = data.parent_height - content_top - padding.get("bottom", 0)
    
    total_child_main = sum(
        (p.get("width", 100) if is_horizontal else p.get("height", 80)) + gap
        for p in data.presets
    )
    total_gap = max(0, len(data.presets) - 1) * gap
    total_content = content_width if is_horizontal else content_height
    remaining = total_content - total_child_main + gap
    
    justify_offset = 0
    distribute_spacing = 0
    if alignment in ("center", "center-left", "center-right"):
        justify_offset = max(0, remaining / 2)
    elif alignment in ("bottom-right", "center-right", "top-right"):
        justify_offset = max(0, remaining)
    elif alignment == "space-between" and len(data.presets) > 1:
        distribute_spacing = remaining / (len(data.presets) - 1)
    elif alignment == "space-around" and len(data.presets) > 0:
        distribute_spacing = remaining / len(data.presets)
        justify_offset = distribute_spacing / 2
    
    main_axis = justify_offset
    cross_axis = 0
    max_cross = 0
    overflow = False
    
    for i, preset_data in enumerate(data.presets):
        child_main = preset_data.get("width", 100) if is_horizontal else preset_data.get("height", 80)
        child_cross = preset_data.get("height", 80) if is_horizontal else preset_data.get("width", 100)
        
        if sizing == "fill":
            child_cross = content_height if is_horizontal else content_width
        
        cross_offset = 0
        if is_horizontal:
            if "bottom" in alignment:
                cross_offset = max(0, content_height - child_cross)
            elif "center" in alignment:
                cross_offset = max(0, (content_height - child_cross) / 2)
        else:
            if "right" in alignment:
                cross_offset = max(0, content_width - child_cross)
            elif "center" in alignment:
                cross_offset = max(0, (content_width - child_cross) / 2)
        
        x = (content_left + main_axis) if is_horizontal else (content_left + cross_offset)
        y = (content_top + cross_axis + cross_offset) if is_horizontal else (content_top + main_axis)
        
        children.append(LayoutComputeChild(
            preset_id=preset_data.get("id", ""),
            x=x, y=y,
            width=preset_data.get("width", 100),
            height=preset_data.get("height", 80),
        ))
        
        main_axis += child_main + gap + distribute_spacing
        max_cross = max(max_cross, child_cross)
    
    final_w = main_axis + padding.get("right", 0) if is_horizontal else max_cross + padding.get("left", 0) + padding.get("right", 0)
    final_h = max_cross + padding.get("top", 0) + padding.get("bottom", 0) if is_horizontal else main_axis + padding.get("top", 0)
    
    return LayoutComputeResponse(
        children=children,
        content_width=final_w,
        content_height=final_h,
        overflow=overflow,
    )


# ═══════════════════════════════════════════════════════════════════
# Preset Versions
# ═══════════════════════════════════════════════════════════════════

@router.get("/versions", response_model=PresetVersionListResponse)
async def list_versions(
    app_id: str = Query(...),
    preset_id: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """List preset version history."""
    versions = service.list_versions(db, app_id, preset_id=preset_id)
    return PresetVersionListResponse(
        versions=versions,
        total=len(versions),
        app_id=app_id,
    )


@router.post("/versions", response_model=APIResponse, status_code=201)
async def create_version(
    app_id: str = Query(...),
    data: PresetVersionCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Create a new version snapshot."""
    version = service.create_version(db, app_id, data)
    return APIResponse(
        status="success",
        message=f"Version {version.version_number} created",
        data={"id": version.id, "version_number": version.version_number},
    )


@router.get("/versions/{version_id}", response_model=PresetVersionSchema)
async def get_version(version_id: str, db: Session = Depends(get_session)):
    version = service.get_version(db, version_id)
    if not version:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    return version


@router.delete("/versions/{version_id}", response_model=APIResponse)
async def delete_version(version_id: str, db: Session = Depends(get_session)):
    success = service.delete_version(db, version_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")
    return APIResponse(status="success", message=f"Version {version_id} deleted")


# ═══════════════════════════════════════════════════════════════════
# Comments
# ═══════════════════════════════════════════════════════════════════

@router.get("/comments", response_model=CommentListResponse)
async def list_comments(
    app_id: str = Query(...),
    preset_id: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    db: Session = Depends(get_session),
):
    """List comments for an app."""
    comments = service.list_comments(db, app_id, preset_id=preset_id, resolved=resolved)
    return CommentListResponse(
        comments=comments,
        total=len(comments),
        app_id=app_id,
    )


@router.post("/comments", response_model=APIResponse, status_code=201)
async def create_comment(
    app_id: str = Query(...),
    data: CommentCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Create a new comment on a preset."""
    comment = service.create_comment(db, app_id, data)
    return APIResponse(status="success", message="Comment created", data={"id": comment.id})


@router.put("/comments/{comment_id}", response_model=APIResponse)
async def update_comment(
    comment_id: str,
    data: CommentUpdate = Body(...),
    db: Session = Depends(get_session),
):
    success = service.update_comment(db, comment_id, data)
    if not success:
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")
    return APIResponse(status="success", message="Comment updated")


@router.delete("/comments/{comment_id}", response_model=APIResponse)
async def delete_comment(comment_id: str, db: Session = Depends(get_session)):
    success = service.delete_comment(db, comment_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Comment '{comment_id}' not found")
    return APIResponse(status="success", message="Comment deleted")


# ═══════════════════════════════════════════════════════════════════
# Interactions (Prototyping)
# ═══════════════════════════════════════════════════════════════════

@router.get("/interactions", response_model=InteractionListResponse)
async def list_interactions(
    app_id: str = Query(...),
    source_preset_id: Optional[str] = Query(None),
    trigger_type: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """List interactions for an app."""
    interactions = service.list_interactions(db, app_id, source_preset_id=source_preset_id, trigger_type=trigger_type)
    return InteractionListResponse(
        interactions=interactions,
        total=len(interactions),
        app_id=app_id,
    )


@router.post("/interactions", response_model=APIResponse, status_code=201)
async def create_interaction(
    app_id: str = Query(...),
    data: InteractionCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Create a new interaction."""
    interaction = service.create_interaction(db, app_id, data)
    return APIResponse(status="success", message=f"Interaction '{data.name}' created", data={"id": interaction.id})


@router.put("/interactions/{interaction_id}", response_model=APIResponse)
async def update_interaction(
    interaction_id: str,
    data: InteractionUpdate = Body(...),
    db: Session = Depends(get_session),
):
    success = service.update_interaction(db, interaction_id, data)
    if not success:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")
    return APIResponse(status="success", message="Interaction updated")


@router.delete("/interactions/{interaction_id}", response_model=APIResponse)
async def delete_interaction(interaction_id: str, db: Session = Depends(get_session)):
    success = service.delete_interaction(db, interaction_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Interaction '{interaction_id}' not found")
    return APIResponse(status="success", message="Interaction deleted")


# ═══════════════════════════════════════════════════════════════════
# Assets
# ═══════════════════════════════════════════════════════════════════

@router.get("/assets", response_model=AssetListResponse)
async def list_assets(
    app_id: str = Query(...),
    category: Optional[str] = Query(None),
    mime_type: Optional[str] = Query(None),
    db: Session = Depends(get_session),
):
    """List assets for an app."""
    assets = service.list_assets(db, app_id, category=category, mime_type=mime_type)
    return AssetListResponse(
        assets=assets,
        total=len(assets),
        app_id=app_id,
    )


@router.post("/assets", response_model=APIResponse, status_code=201)
async def create_asset(
    app_id: str = Query(...),
    data: AssetCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Register a new asset (file should be uploaded separately)."""
    asset = service.create_asset(db, app_id, data)
    return APIResponse(status="success", message=f"Asset '{data.name}' registered", data={"id": asset.id})


@router.get("/assets/{asset_id}", response_model=AssetSchema)
async def get_asset(asset_id: str, db: Session = Depends(get_session)):
    asset = service.get_asset(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")
    return asset


@router.delete("/assets/{asset_id}", response_model=APIResponse)
async def delete_asset(asset_id: str, db: Session = Depends(get_session)):
    success = service.delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found")
    return APIResponse(status="success", message="Asset deleted")


# ═══════════════════════════════════════════════════════════════════
# Plugins
# ═══════════════════════════════════════════════════════════════════

@router.get("/plugins", response_model=PluginListResponse)
async def list_plugins(
    app_id: str = Query(...),
    plugin_type: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_session),
):
    """List plugins for an app."""
    plugins = service.list_plugins(db, app_id, plugin_type=plugin_type, enabled=enabled)
    return PluginListResponse(
        plugins=plugins,
        total=len(plugins),
        app_id=app_id,
    )


@router.post("/plugins", response_model=APIResponse, status_code=201)
async def create_plugin(
    app_id: str = Query(...),
    data: PluginCreate = Body(...),
    db: Session = Depends(get_session),
):
    """Register a new plugin."""
    plugin = service.create_plugin(db, app_id, data)
    return APIResponse(status="success", message=f"Plugin '{data.name}' registered", data={"id": plugin.id})


@router.put("/plugins/{plugin_id}", response_model=APIResponse)
async def update_plugin(
    plugin_id: str,
    data: PluginUpdate = Body(...),
    db: Session = Depends(get_session),
):
    success = service.update_plugin(db, plugin_id, data)
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return APIResponse(status="success", message="Plugin updated")


@router.delete("/plugins/{plugin_id}", response_model=APIResponse)
async def delete_plugin(plugin_id: str, db: Session = Depends(get_session)):
    success = service.delete_plugin(db, plugin_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return APIResponse(status="success", message="Plugin deleted")


# ═══════════════════════════════════════════════════════════════════
# Seed Data
# ═══════════════════════════════════════════════════════════════════

from common_lib.modules.app_builder.seed import seed_demo_presets, seed_demo_tokens

@router.post("/seed/{app_id}", response_model=APIResponse)
async def seed_builder_data(
    app_id: str,
    db: Session = Depends(get_session),
):
    """Seed demo presets and design tokens for an app."""
    p_created, p_existing = seed_demo_presets(db, app_id)
    t_created, t_existing = seed_demo_tokens(db, app_id)
    presets_count = p_created or p_existing
    t_count = t_created or t_existing
    
    return APIResponse(
        status="success",
        message=f"Seeded {presets_count} presets and {t_count} tokens for app '{app_id}'",
        data={
            "presets_count": presets_count,
            "tokens_count": t_count,
        },
    )
