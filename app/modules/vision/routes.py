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


@router.get("/workflow-presets", response_model=List[Dict[str, Any]])
async def list_workflow_presets():
    """Returns a list of available vision workflow presets."""
    # Mocking for now as requested for stabilized UI
    return [
        {"id": "default_demo", "name": "Standard Inference", "category": "General"},
        {"id": "simple_sd", "name": "Basic Stable Diffusion", "category": "Stable Diffusion"},
        {"id": "sdxl", "name": "SDXL High-Res", "category": "Stable Diffusion"},
        {"id": "hires_fix", "name": "Hires. Fix Workflow", "category": "Upscaling"}
    ]


@router.get("/workflow-presets/{id}", response_model=Dict[str, Any])
async def get_workflow_preset(id: str):
    """Returns the full workflow definition for a specific preset."""
    # In a real app, this would fetch from a presets library or DB.
    # Returning mock data aligned with UI expectation.
    if id == "default_demo":
        return {
            "nodes": [
                { "id": "load", "type": "vision.load_checkpoint", "title": "Model Loader", "initialX": 50, "initialY": 50 },
                { "id": "latent", "type": "vision.empty_latent", "title": "Canvas Setup", "initialX": 50, "initialY": 250 },
                { "id": "sampler", "type": "vision.ksampler", "title": "Process Engine", "initialX": 350, "initialY": 50 },
                { "id": "save", "type": "vision.save_image", "title": "Commit Assets", "initialX": 650, "initialY": 50 }
            ],
            "edges": [
                { "id": "e1", "from": "load", "to": "sampler", "fromPort": "model", "toPort": "model" },
                { "id": "e2", "from": "latent", "to": "sampler", "fromPort": "latent", "toPort": "latent_image" },
                { "id": "e3", "from": "sampler", "to": "save", "fromPort": "images", "toPort": "images" }
            ]
        }
    
    # Default fallback for other IDs to avoid 404
    return { "nodes": [], "edges": [] }


__all__ = ["router"]
