from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List
from common_lib.modules.image_processing.controllers.vision_task_controller import (
    VisionTaskController,
)
from common_lib.modules.vision.schemas import (
    VisionGenerateRequest,
    VisionGenerateResponse,
    VisionWorkflowRequest,
    VisionWorkflowResponse,
)

router = APIRouter()
controller = VisionTaskController()


@router.post("/generate", response_model=VisionGenerateResponse)
async def generate(request: VisionGenerateRequest):
    try:
        response = controller.generate_sd15_high_res(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            model_name=request.model_name,
            upscale_by=request.upscale_by,
            denoise=request.denoise,
            seed=request.seed,
        )
        return VisionGenerateResponse(
            status="success",
            file_path=response.file_path,
            metadata=response.metadata,
        )
    except Exception as e:
        return VisionGenerateResponse(status="error", message=str(e))


@router.get("/models", response_model=List[Dict[str, Any]])
async def list_models():
    from app.core.common_lib_integration import common_memory

    models = common_memory.list_model_definitions()
    return [{"id": m.get("id"), "name": m.get("name")} for m in models]


@router.get("/checkpoints", response_model=List[Dict[str, str]])
async def list_checkpoints():
    from common_lib.modules.ai_models.core.download_manager import (
        get_cached_checkpoints,
    )

    return get_cached_checkpoints()


__all__ = ["router"]
