"""Sound Design Studio API routes."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from common_lib.modules.audio_processing.services.sound_design_service import (
    SoundDesignService,
)

router = APIRouter(prefix="/studio/sound-design", tags=["Sound Design Studio"])

_service = SoundDesignService()


# ── Pydantic Models ────────────────────────────────────────────────────────────


class NeuralSFXRequest(BaseModel):
    prompt: str = Field(..., description="Text description of the sound")
    duration: float = Field(2.0, ge=0.1, le=30.0)
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/neural_sfx.wav")
    model_name: str = Field("audioldm2")


class ProceduralSFXRequest(BaseModel):
    prompt: str = Field(..., description="Text description of the sound")
    duration: float = Field(2.0, ge=0.1, le=30.0)
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/procedural_sfx.wav")


class ImpactRequest(BaseModel):
    material: str = Field("metal", pattern="^(metal|glass|wood|plastic)$")
    force: float = Field(0.8, ge=0.0, le=1.0)
    base_freq: float = Field(440.0, ge=50.0, le=2000.0)
    duration: float = Field(1.5, ge=0.1, le=10.0)
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/impact.wav")


class WindRequest(BaseModel):
    speed: float = Field(0.5, ge=0.0, le=1.0)
    duration: float = Field(3.0, ge=0.1, le=30.0)
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/wind.wav")


class ExplosionRequest(BaseModel):
    size: float = Field(0.7, ge=0.0, le=1.0)
    duration: float = Field(2.5, ge=0.1, le=10.0)
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/explosion.wav")


class StableAudioRequest(BaseModel):
    prompt: str = Field(..., description="Text prompt for generation")
    duration: int = Field(15, ge=1, le=600)
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/stable_audio.wav")
    model_name: str = Field("small-sfx", pattern="^(small-sfx|small-music|medium)$")


class PresetRequest(BaseModel):
    preset_name: str = Field(..., description="Name of the preset")
    output_path: str = Field("GENERATED_CONTENT/audio/sfx/preset.wav")


# ── Routes ─────────────────────────────────────────────────────────────────────


@router.get("/presets")
async def get_presets():
    """Get built-in sound design presets."""
    return _service.get_presets()


@router.post("/generate/neural")
async def generate_neural(req: NeuralSFXRequest):
    """Generate SFX using neural model (AudioLDM2) with procedural fallback."""
    try:
        return _service.generate_sfx_neural(
            req.prompt, req.duration, req.output_path, req.model_name
        )
    except Exception as e:
        raise HTTPException(500, f"Neural SFX generation failed: {e}")


@router.post("/generate/procedural")
async def generate_procedural(req: ProceduralSFXRequest):
    """Generate SFX using physics-based procedural synthesis."""
    try:
        return _service.generate_sfx_procedural(
            req.prompt, req.duration, req.output_path
        )
    except Exception as e:
        raise HTTPException(500, f"Procedural SFX generation failed: {e}")


@router.post("/generate/impact")
async def generate_impact(req: ImpactRequest):
    """Generate impact strike using modal resonance synthesis."""
    try:
        return _service.generate_impact(
            req.material, req.force, req.base_freq, req.duration, req.output_path
        )
    except Exception as e:
        raise HTTPException(500, f"Impact generation failed: {e}")


@router.post("/generate/wind")
async def generate_wind(req: WindRequest):
    """Generate wind gust using LFO-modulated bandpass synthesis."""
    try:
        return _service.generate_wind(req.speed, req.duration, req.output_path)
    except Exception as e:
        raise HTTPException(500, f"Wind generation failed: {e}")


@router.post("/generate/explosion")
async def generate_explosion(req: ExplosionRequest):
    """Generate explosion using multi-layer composite synthesis."""
    try:
        return _service.generate_explosion(req.size, req.duration, req.output_path)
    except Exception as e:
        raise HTTPException(500, f"Explosion generation failed: {e}")


@router.post("/generate/stable-audio")
async def generate_stable_audio(req: StableAudioRequest):
    """Generate SFX using Stable Audio Open small-sfx variant."""
    try:
        return _service.generate_stable_audio(
            req.prompt, req.duration, req.output_path, req.model_name
        )
    except Exception as e:
        raise HTTPException(500, f"Stable Audio generation failed: {e}")


@router.post("/generate/preset")
async def generate_from_preset(req: PresetRequest):
    """Generate SFX from a built-in preset."""
    try:
        return _service.generate_from_preset(req.preset_name, req.output_path)
    except Exception as e:
        raise HTTPException(500, f"Preset generation failed: {e}")


@router.get("/engines")
async def list_engines():
    """List available sound design engines and their status."""
    from common_lib.modules.audio_processing.pipeline import caps

    sfx_engines = {
        k: v
        for k, v in caps.engines.items()
        if "sfx" in k.lower()
        or "procedural" in k.lower()
        or "audioldm" in k.lower()
        or "stable_audio" in k.lower()
    }
    return {"engines": sfx_engines}
