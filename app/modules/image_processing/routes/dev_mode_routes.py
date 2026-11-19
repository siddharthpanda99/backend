"""Dev mode routes for direct host CLI image generation.

Provides a lightweight endpoint that bypasses the fabric container
and calls the host CLI directly for development/testing.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from common_lib.modules.image_processing.dev_mode import DevModeProvider

router = APIRouter(prefix="/dev-mode", tags=["Dev Mode Image Generation"])


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Positive prompt for image generation")
    negative_prompt: str = Field("", description="Negative prompt")
    width: int = Field(512, ge=64, le=2048, multiple_of=16)
    height: int = Field(512, ge=64, le=2048, multiple_of=16)
    steps: int = Field(4, ge=1, le=100)
    cfg: float = Field(3.0, ge=0.1, le=20.0)
    seed: int = Field(42, ge=0)
    model_id: str = Field("MOSS-Image-SFT-UD-Q4_K_XL", description="Model identifier")
    negative_prompt_file: Optional[str] = Field(None, description="Path to negative prompt file")
    extra_args: Optional[List[str]] = Field(None, description="Extra arguments to pass to sd-cli")


class GenerateResponse(BaseModel):
    ok: bool
    image_path: Optional[str] = None
    seed: Optional[int] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    duration_s: Optional[float] = None
    engine: Optional[str] = None
    adapter: Optional[str] = None
    backend_id: Optional[str] = None
    model: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None


@router.post("/generate", response_model=GenerateResponse)
async def generate_image(request: GenerateRequest):
    """Generate an image using dev mode (direct host CLI call).
    
    This endpoint bypasses the fabric container and calls the host CLI directly.
    Only works when dev mode is enabled (IMAGE_PROCESSING_DEV_MODE=1 or
    feature flag image_processing.dev_mode.enabled).
    """
    try:
        from common_lib.modules.image_processing.dev_mode import DevModeProvider
        
        result = DevModeProvider.generate_image(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            width=request.width,
            height=request.height,
            steps=request.steps,
            cfg=request.cfg,
            seed=request.seed,
            model_id=request.model_id,
        )
        
        return GenerateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.get("/status")
async def dev_mode_status():
    """Check if dev mode is enabled and sd-cli is available."""
    from common_lib.modules.image_processing.dev_mode import DevModeProvider
    from pathlib import Path
    
    config = DevModeProvider.get_config()
    sd_cli_exists = Path(config.sd_cli_path).exists() if hasattr(config, 'sd_cli_path') else False
    
    return {
        "dev_mode_enabled": config.enabled,
        "sd_cli_path": config.sd_cli_path,
        "sd_cli_exists": Path(config.sd_cli_path).exists(),
        "message": "Dev mode is ready" if config.enabled and Path(config.sd_cli_path).exists() else "Dev mode not ready"
    }
