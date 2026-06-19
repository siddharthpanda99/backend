import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.configs.service import ConfigsService, record_to_schema
from common_lib.modules.vision.schemas import (
    VisionPresetSchema,
    VisionPresetCreateRequest,
    VisionPresetUpdateRequest,
)
from common_lib.paths import get_repo_root

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/configs", tags=["Configs"])
_svc = ConfigsService(get_session)


@router.get("/", response_model=List[VisionPresetSchema])
async def list_configs(
    search: Optional[str] = Query(None),
    offset: int = Query(0),
    limit: int = Query(100),
):
    """List generation configs (presets)."""
    return _svc.list_configs(search=search, offset=offset, limit=limit)


@router.get("/{config_id}", response_model=VisionPresetSchema)
async def get_config(config_id: str):
    """Get a single config by ID."""
    result = _svc.get_config(config_id)
    if not result:
        raise HTTPException(status_code=404, detail="Config not found")
    return result


@router.post("/", response_model=VisionPresetSchema)
async def create_config(request: VisionPresetCreateRequest):
    """Create a new config."""
    try:
        return _svc.create_config(request)
    except Exception as e:
        if "already exists" in str(e).lower():
            raise HTTPException(status_code=400, detail=str(e))
        raise


class BatchConfigUpdateItem(BaseModel):
    id: str
    updates: Dict[str, Any]

class BatchConfigUpdateRequest(BaseModel):
    items: List[BatchConfigUpdateItem]

class BatchConfigUpdateResponse(BaseModel):
    status: str
    updated_count: int
    updated_ids: List[str]


@router.patch("/batch", response_model=BatchConfigUpdateResponse)
async def update_configs_batch(request: BatchConfigUpdateRequest):
    """Update multiple configs in a single transaction."""
    result = _svc.update_configs_batch([item.dict() for item in request.items])
    return BatchConfigUpdateResponse(**result)


@router.patch("/{config_id}", response_model=VisionPresetSchema)
async def update_config(config_id: str, request: VisionPresetUpdateRequest):
    """Update an existing config."""
    result = _svc.update_config(config_id, request)
    if not result:
        raise HTTPException(status_code=404, detail="Config not found")
    return result


@router.delete("/{config_id}")
async def delete_config(config_id: str):
    """Delete a config."""
    success = _svc.delete_config(config_id)
    if not success:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"status": "success", "message": f"Config {config_id} deleted"}


@router.post("/init")
async def init_configs():
    """Initialize configs from legacy JSON file if table is empty."""
    config_path = str(get_repo_root() / "Backend" / "app" / "modules" / "vision" / "prompts_config.json")
    return _svc.init_from_legacy_json(config_path)
