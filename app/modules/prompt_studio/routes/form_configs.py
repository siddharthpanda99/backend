from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Dict, Any, Optional, List

from common_lib.modules.prompt_studio.services.form_config_service import (
    FormConfigService,
)

router = APIRouter(tags=["Prompt Studio"])


class ConfigCreate(BaseModel):
    name: str
    modality: str = "custom"
    model_target: str = "generic"
    version: str = "1.0.0"
    version_notes: str = ""
    description: str = ""
    usecase: str = ""
    tags: List[str] = []
    metadata_json: Dict[str, Any] = {}
    fields: List[Dict[str, Any]] = []
    is_published: bool = True
    parent_config_id: Optional[str] = None


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    usecase: Optional[str] = None
    version: Optional[str] = None
    version_notes: Optional[str] = None
    fields: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    is_published: Optional[bool] = None


@router.get("/form-configs")
async def list_configs(
    modality: Optional[str] = Query(None),
    model_target: Optional[str] = Query(None),
    include_builtin: bool = Query(True),
    search: Optional[str] = Query(None),
):
    return FormConfigService.list_configs(
        modality, model_target, include_builtin, search
    )


@router.get("/form-configs/{config_id}")
async def get_config(config_id: str):
    config = FormConfigService.get_config(config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    return config


@router.post("/form-configs")
async def create_config(data: ConfigCreate):
    return FormConfigService.create_config(data.dict())


@router.put("/form-configs/{config_id}")
async def update_config(config_id: str, data: ConfigUpdate):
    try:
        result = FormConfigService.update_config(
            config_id, data.dict(exclude_unset=True)
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Config not found")
    return result


@router.delete("/form-configs/{config_id}")
async def delete_config(config_id: str):
    try:
        deleted = FormConfigService.delete_config(config_id)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Config not found")
    return {"success": True}


@router.post("/form-configs/{config_id}/clone")
async def clone_config(config_id: str, name: Optional[str] = Query(None)):
    result = FormConfigService.clone_config(config_id, name)
    if not result:
        raise HTTPException(status_code=404, detail="Config not found")
    return result


@router.get("/form-configs/{config_id}/versions")
async def get_versions(config_id: str):
    return FormConfigService.get_versions(config_id)
