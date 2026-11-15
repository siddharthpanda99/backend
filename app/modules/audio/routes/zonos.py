"""Zonos TTS thin routes — transport ONLY.

Delegates every operation to ``common_lib.modules.audio_processing``
(``ZonosTtsService``). Business logic remains strictly in common_lib.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from pydantic import BaseModel, Field

from common_lib.paths import RESOURCES_ROOT

from common_lib.modules.audio_processing.memory.feature_flags import (
    ZONOS_TTS_ENABLED,
    is_enabled,
)
from common_lib.modules.audio_processing.services.zonos_tts_service import (
    ZonosTtsError,
    ZonosTtsService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/zonos", tags=["Zonos TTS"])

_SAMPLE_COLLECTIONS = frozenset({"zonos-tts", "zonos-chibi-ja", "zonos-singles"})


class ZonosGenerateRequest(BaseModel):
    text: str
    voice: str = "Sakura_en-anime_F_1"
    lang: str = "ja"
    frames: int = Field(220, ge=16, le=400)
    temperature: float | None = None
    filename: str | None = None


def _require_enabled() -> None:
    if not is_enabled(ZONOS_TTS_ENABLED):
        raise HTTPException(
            status_code=503,
            detail="zonos tts is disabled (ZONOS_TTS_ENABLED is off)",
        )


@router.get("/status")
def status() -> dict[str, Any]:
    _require_enabled()
    return ZonosTtsService().status()


@router.get("/voices")
def voices() -> dict[str, Any]:
    _require_enabled()
    service = ZonosTtsService()
    return {"voices": service.list_voices(), "languages": service.languages()}


@router.post("/generate")
def generate(req: ZonosGenerateRequest) -> dict[str, Any]:
    _require_enabled()
    try:
        return ZonosTtsService().generate(**req.model_dump())
    except ZonosTtsError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc


@router.get("/samples")
def samples() -> dict[str, Any]:
    _require_enabled()
    return ZonosTtsService().tts_samples()


@router.get("/file/{collection}/{filename}")
def file(collection: str, filename: str) -> FileResponse:
    _require_enabled()
    if collection not in _SAMPLE_COLLECTIONS:
        raise HTTPException(status_code=404, detail="unknown collection")
    if (
        not filename
        or filename != Path(filename).name
        or ".." in filename
        or "/" in filename
        or "\\" in filename
        or not filename.lower().endswith(".wav")
    ):
        raise HTTPException(status_code=404, detail="invalid filename")
    base = (RESOURCES_ROOT / "generated_content" / collection).resolve()
    path = (base / filename).resolve()
    if path.parent != base or not path.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(path=str(path), filename=filename, media_type="audio/wav")
