from fastapi import APIRouter, Depends, HTTPException
from typing import Any
from .schemas import VisionGenerateRequest, VisionGenerateResponse
from .service import vision_service
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()

from fastapi.responses import StreamingResponse
import json

@router.post("/generate-high-res", response_model=APIResponse[VisionGenerateResponse])
def generate_vision_task(
    request_in: VisionGenerateRequest
):
    """
    Triggers a 2-pass SD 1.5 High-Resolution generation.
    """
    result = vision_service.generate_high_res(request_in)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return APIResponse(
        data=VisionGenerateResponse(**result),
        message="Vision generation completed successfully"
    )

@router.post("/generate-high-res-stream")
async def generate_vision_task_stream(request_in: VisionGenerateRequest):
    """
    Triggers a 2-pass SD 1.5 High-Resolution generation with real-time telemetry.
    """
    async def event_generator():
        async for event in vision_service.generate_high_res_stream(request_in):
             yield f"data: {json.dumps(event)}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("/gallery")
def get_vision_gallery():
    """
    Returns a list of all images in the generated_content folder.
    """
    return vision_service.get_gallery()

@router.get("/prompts/configs")
def get_prompt_configs():
    """
    Returns a list of curated prompt configurations for UI populating.
    """
    import os
    import json
    file_path = os.path.join(os.path.dirname(__file__), "prompts_config.json")
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r") as f:
        return json.load(f)
