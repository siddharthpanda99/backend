"""Effect presets and generation version endpoints."""

import logging
from fastapi import APIRouter, HTTPException
from common_lib.modules.audio_processing.service import get_audio_service
from common_lib.modules.audio_processing.schemas import (
    EffectPresetCreate, EffectPresetUpdate, EffectPresetResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/effects/presets", response_model=list[EffectPresetResponse])
async def list_presets():
    svc = get_audio_service()
    return [EffectPresetResponse(**p) for p in await svc.list_effect_presets()]


@router.get("/effects/presets/{preset_id}", response_model=EffectPresetResponse)
async def get_preset(preset_id: str):
    svc = get_audio_service()
    for p in await svc.list_effect_presets():
        if p.get("id") == preset_id:
            return EffectPresetResponse(**p)
    raise HTTPException(404, "Preset not found")


@router.post("/effects/presets", response_model=EffectPresetResponse)
async def create_preset(data: EffectPresetCreate):
    svc = get_audio_service()
    preset = await svc.create_effect_preset(data.model_dump())
    return EffectPresetResponse(**preset)


@router.delete("/effects/presets/{preset_id}")
async def delete_preset(preset_id: str):
    svc = get_audio_service()
    if not await svc.delete_effect_preset(preset_id):
        raise HTTPException(404, "Preset not found or is built-in")
    return {"message": "Preset deleted"}
