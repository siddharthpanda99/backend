from pydantic import BaseModel, Field
from typing import Optional, Any, Dict

class VisionGenerateRequest(BaseModel):
    prompt: str = Field(..., description="Positive prompt")
    negative_prompt: Optional[str] = Field("", description="Negative prompt")
    model_name: Optional[str] = Field("stable-diffusion-v1-5", description="Checkpoint name (e.g. dreamshaper_8.safetensors)")
    upscale_by: Optional[float] = Field(1.5, description="Upscale multiplier")
    denoise: Optional[float] = Field(0.45, description="Denoise strength for 2nd pass")
    seed: Optional[int] = Field(None, description="Random seed")

class VisionGenerateResponse(BaseModel):
    status: str
    file_path: Optional[str] = None
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
