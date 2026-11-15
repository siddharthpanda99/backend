"""Voice Conversion Studio routes — thin transport layer.

Endpoints:
- POST /voice-conversion/rvc/convert — RVC voice conversion
- POST /voice-conversion/rvc/models — list RVC models
- POST /voice-conversion/sovits/convert — So-VITS-SVC voice conversion
- POST /voice-conversion/sovits/models — list So-VITS-SVC models
- POST /voice-conversion/omnivoice/clone — OmniVoice zero-shot cloning
- POST /voice-conversion/singing/convert — Singing voice conversion
- POST /voice-conversion/models — list all available models

All endpoints gated behind VOICE_CONVERSION_ENABLED flag (default-OFF).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from app.modules.audio.runtime.actor import capture_job_actor

from common_lib.modules.audio_processing.memory.feature_flags import (
    VOICE_CONVERSION_ENABLED,
    is_enabled,
)
from common_lib.modules.audio_processing.services.voice_conversion import (
    VoiceConversionService,
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    dependencies=[Depends(capture_job_actor)],
    prefix="/voice-conversion",
    tags=["Voice Conversion Studio"],
)

_service = VoiceConversionService()


# ── Pydantic Models ────────────────────────────────────────────────────────────


class RVCConvertRequest(BaseModel):
    input_audio_path: str = Field(..., description="Path to input audio file")
    model_name: str = Field(..., description="RVC model name")
    output_path: str = Field(..., description="Output file path")
    pitch_shift: int = Field(0, description="Pitch shift in semitones", ge=-24, le=24)
    f0_method: str = Field(
        "pm", description="F0 extraction method (pm, harvest, crepe)"
    )
    filter_radius: int = Field(
        3, description="Filter radius for median filtering", ge=0, le=10
    )
    envelope_mix: float = Field(0.25, description="Envelope mix ratio", ge=0.0, le=1.0)


class SOVITSConvertRequest(BaseModel):
    input_audio_path: str = Field(..., description="Path to input audio file")
    model_name: str = Field(..., description="So-VITS-SVC model name")
    output_path: str = Field(..., description="Output file path")
    transpose: int = Field(0, description="Transpose in semitones", ge=-24, le=24)
    spk_id: int = Field(0, description="Speaker ID", ge=0)
    output_format: str = Field("wav", description="Output format (wav, flac, mp3)")


class OmniVoiceCloneRequest(BaseModel):
    input_audio_path: str = Field(..., description="Path to reference audio")
    reference_text: str = Field(..., description="Text content of reference audio")
    target_text: str = Field(..., description="Text to synthesize in cloned voice")
    output_path: str = Field(..., description="Output file path")
    language: str = Field("en", description="Language code")


class SingingConvertRequest(BaseModel):
    input_audio_path: str = Field(..., description="Path to input singing audio")
    model_name: str = Field(..., description="Singing conversion model")
    output_path: str = Field(..., description="Output file path")
    transpose: int = Field(0, description="Transpose in semitones", ge=-24, le=24)
    target_singer: Optional[str] = Field(None, description="Target singer ID")


class RVCModelInfo(BaseModel):
    name: str
    path: str
    has_pth: bool
    has_index: bool


class SOVITSModelInfo(BaseModel):
    name: str
    path: str
    has_pth: bool
    has_config: bool


class ModelsResponse(BaseModel):
    rvc: List[RVCModelInfo] = []
    sovits: List[SOVITSModelInfo] = []


# ── Routes ────────────────────────────────────────────────────────────────────


@router.get(
    "/models",
    summary="List all available voice conversion models",
)
async def list_models() -> ModelsResponse:
    """List all available voice conversion models (RVC and So-VITS-SVC)."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404,
            detail="Voice conversion features disabled (VOICE_CONVERSION_ENABLED flag is OFF)",
        )

    rvc_models = _service.list_rvc_models()
    sovits_models = _service.list_sovits_models()

    return ModelsResponse(
        rvc=rvc_models.get("models", []), sovits=sovits_models.get("models", [])
    )


@router.post(
    "/rvc/convert",
    summary="Convert voice using RVC (Retrieval-based Voice Conversion)",
)
async def rvc_convert(req: RVCConvertRequest) -> Dict[str, Any]:
    """Convert voice using RVC model."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404,
            detail="Voice conversion features disabled (VOICE_CONVERSION_ENABLED flag is OFF)",
        )

    try:
        result = _service.rvc_convert(
            input_audio_path=req.input_audio_path,
            model_name=req.model_name,
            output_path=req.output_path,
            pitch_shift=req.pitch_shift,
            f0_method=req.f0_method,
            filter_radius=req.filter_radius,
            envelope_mix=req.envelope_mix,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/rvc/models",
    summary="List available RVC models",
)
async def list_rvc_models() -> Dict[str, Any]:
    """List available RVC models."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404, detail="Voice conversion features disabled"
        )

    return _service.list_rvc_models()


@router.post(
    "/sovits/convert",
    summary="Convert voice using So-VITS-SVC",
)
async def sovits_convert(req: SOVITSConvertRequest) -> Dict[str, Any]:
    """Convert voice using So-VITS-SVC model."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404, detail="Voice conversion features disabled"
        )

    try:
        result = _service.sovits_convert(
            input_audio_path=req.input_audio_path,
            model_name=req.model_name,
            output_path=req.output_path,
            transpose=req.transpose,
            spk_id=req.spk_id,
            output_format=req.output_format,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/sovits/models",
    summary="List available So-VITS-SVC models",
)
async def list_sovits_models() -> Dict[str, Any]:
    """List available So-VITS-SVC models."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404, detail="Voice conversion features disabled"
        )

    return _service.list_sovits_models()


@router.post(
    "/omnivoice/clone",
    summary="Clone voice using OmniVoice (zero-shot)",
)
async def omnivoice_clone(req: OmniVoiceCloneRequest) -> Dict[str, Any]:
    """Clone voice using OmniVoice (zero-shot expressive TTS)."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404, detail="Voice conversion features disabled"
        )

    try:
        result = _service.omnivoice_clone(
            input_audio_path=req.input_audio_path,
            reference_text=req.reference_text,
            target_text=req.target_text,
            output_path=req.output_path,
            language=req.language,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/singing/convert",
    summary="Convert singing voice",
)
async def singing_convert(req: SingingConvertRequest) -> Dict[str, Any]:
    """Convert singing voice using diffusion-based model."""
    if not is_enabled(VOICE_CONVERSION_ENABLED):
        raise HTTPException(
            status_code=404, detail="Voice conversion features disabled"
        )

    try:
        result = _service.singing_convert(
            input_audio_path=req.input_audio_path,
            model_name=req.model_name,
            output_path=req.output_path,
            transpose=req.transpose,
            target_singer=req.target_singer,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Service instance
_service = VoiceConversionService()
