"""Vision Routes — Thin API layer delegating to common_lib services."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
import io
import shutil
import pytesseract
from PIL import Image

# Auto-detect Tesseract binary on Windows when not on PATH
if not shutil.which("tesseract"):
    for candidate in [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]:
        if os.path.isfile(candidate):
            pytesseract.tesseract_cmd = candidate
            break

from common_lib.modules.vision.schemas import (
    VisionGenerateRequest,
    VisionGenerateResponse,
    VisionWorkflowRequest,
    VisionWorkflowResponse,
    VisionGalleryResponse,
    VisionPromptPreviewRequest,
    VisionPromptPreviewResponse,
    RuntimeLoadRequest,
    RuntimeLoadResponse,
    RuntimeUnloadRequest,
    RuntimeUnloadResponse,
    RuntimeGenerateRequest,
    RuntimeGenerateResponse,
    RuntimeListResponse,
    RuntimeFamiliesResponse,
    RuntimeModelInfo,
    RuntimeFamilyInfo,
)
from common_lib.modules.vision.runtime_service import (
    list_loaded_models,
    list_supported_families,
    load_model,
    unload_model,
    generate_image,
)
from common_lib.modules.image_processing.controllers.vision_task_controller import (
    VisionTaskController,
)
from common_lib.modules.vision.enhanced_service import (
    scan_checkpoints,
    discover_vision_nodes,
    scan_gallery,
    expand_prompt_preview,
    list_samplers_with_metadata,
    list_schedulers_with_metadata,
    list_workflow_presets,
    get_workflow_preset,
    list_models_from_db,
    list_checkpoints_from_db,
    load_prompt_configs,
)
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.paths import GENERATED_CONTENT

logger = logging.getLogger(__name__)
router = APIRouter()
controller = VisionTaskController()


@router.get("/prompts/configs/legacy")
async def get_prompt_configs():
    config_path = os.path.join(os.path.dirname(__file__), "prompts_config.json")
    return load_prompt_configs(config_path)


@router.post("/prompts/preview", response_model=VisionPromptPreviewResponse)
async def preview_prompts(request: VisionPromptPreviewRequest):
    result = expand_prompt_preview(
        template=request.template,
        limit=request.limit or 10,
        combinatorial=request.combinatorial or False,
        seed=request.seed,
    )
    if result["status"] == "error":
        return VisionPromptPreviewResponse(
            status="error", prompts=[], count=0, message=result.get("message")
        )
    return VisionPromptPreviewResponse(
        status="success", prompts=result["prompts"], count=result["count"]
    )


@router.post("/generate", response_model=VisionGenerateResponse)
async def generate(request: VisionGenerateRequest):
    try:
        response = controller.generate_image_via_runtime(
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
    with next(get_session()) as session:
        return list_models_from_db(session)


@router.get("/models/list", response_model=List[Dict[str, Any]])
async def list_models_by_category(category: str = "sd15"):
    with next(get_session()) as session:
        return list_models_from_db(session, category=category)


@router.get("/samplers", response_model=List[Dict[str, Any]])
async def list_samplers(implementation: str = "diffusers"):
    return list_samplers_with_metadata(implementation)


@router.get("/schedulers", response_model=List[Dict[str, Any]])
async def list_schedulers(provider: str = "diffusers"):
    return list_schedulers_with_metadata(provider)


@router.get("/checkpoints", response_model=List[Dict[str, Any]])
async def list_checkpoints(category: str = None):
    with next(get_session()) as session:
        return list_checkpoints_from_db(session, category)


@router.get("/swap-models", response_model=List[str])
async def list_swap_models():
    from common_lib.modules.image_processing.nodes.reactor.base import (
        get_insightface_models,
    )
    return get_insightface_models()


@router.get("/face-restore-models", response_model=List[str])
async def list_face_restore_models():
    from common_lib.modules.image_processing.nodes.reactor.base import (
        get_facerestore_models,
    )
    return get_facerestore_models()


@router.get("/workflow-presets", response_model=List[Dict[str, Any]])
async def list_workflow_presets_endpoint():
    return list_workflow_presets()


@router.get("/workflow-presets/{id}", response_model=Dict[str, Any])
async def get_workflow_preset_endpoint(id: str):
    workflow = get_workflow_preset(id)
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Workflow '{id}' not found")
    return workflow


@router.get("/nodes", response_model=List[Dict[str, Any]])
async def list_nodes():
    from common_lib.modules.image_processing.nodes_registry.discovery import (
        get_all_nodes,
    )
    return get_all_nodes()


@router.post("/execute", response_model=VisionWorkflowResponse)
async def execute_workflow(request: VisionWorkflowRequest):
    try:
        from common_lib.modules.workflows.standard.builder import WorkflowBuilder
        from common_lib.modules.workflows.standard.registry.workflow_registry import (
            get_workflow_registry,
        )
        from common_lib.modules.workflows.standard.executor import WorkflowExecutor
        from common_lib.modules.workflows.standard.state import WorkflowStatus

        builder = WorkflowBuilder()
        registry = get_workflow_registry()

        workflow_id = request.workflow_id
        execution_state = request.state or {}
        if request.parameters:
            execution_state.update(request.parameters)
        if request.config:
            execution_state.update(request.config)

        workflow_def = None
        if workflow_id:
            workflow_def = registry.get_workflow(workflow_id)

        if not workflow_def and request.nodes:
            workflow_def = {
                "id": workflow_id or "adhoc",
                "nodes": request.nodes,
                "edges": request.edges or request.connections or [],
            }

        if not workflow_def:
            raise ValueError(
                f"Workflow '{workflow_id}' not found and no ad-hoc nodes provided."
            )

        workflow_data = {
            "id": workflow_def.get("id"),
            "nodes": workflow_def.get("nodes", []),
            "edges": workflow_def.get("edges", []) or workflow_def.get("connections", []),
        }

        workflow = builder.load_from_dict(workflow_data)
        executor = WorkflowExecutor()
        state = executor.execute(workflow, execution_state)

        result_images = []
        for node_id, node_outputs in state.data.items():
            if isinstance(node_outputs, dict):
                img = (
                    node_outputs.get("image")
                    or node_outputs.get("images")
                    or node_outputs.get("output")
                )
                if img:
                    if isinstance(img, list):
                        result_images.extend(i for i in img if isinstance(i, str))
                    elif isinstance(img, str):
                        result_images.append(img)

        for var_name in ["image", "images", "output"]:
            val = state.state_vars.get(var_name)
            if val:
                if isinstance(val, list):
                    result_images.extend(i for i in val if isinstance(i, str) and i not in result_images)
                elif isinstance(val, str) and val not in result_images:
                    result_images.append(val)

        return VisionWorkflowResponse(
            status="success" if state.status == WorkflowStatus.COMPLETED else "error",
            message=f"Workflow completed with status: {state.status.value}",
            metadata={
                "execution_id": state.execution_id,
                "workflow_id": workflow_id,
                "steps_completed": len(state.steps),
                "nodes_executed": list(state.data.keys()),
            },
            images=result_images,
        )
    except Exception as e:
        logger.exception(f"Error executing vision workflow: {e}")
        return VisionWorkflowResponse(status="error", message=str(e))

@router.post("/ocr")
async def perform_ocr(file: UploadFile = File(...)):
    try:
        content = await file.read()
        image = Image.open(io.BytesIO(content))
        text = pytesseract.image_to_string(image)
        return {"status": "success", "text": text.strip()}
    except Exception as e:
        logger.exception(f"OCR Error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/gallery", response_model=VisionGalleryResponse)
async def list_gallery():
    if not GENERATED_CONTENT.exists():
        return VisionGalleryResponse(folders=[])

    gallery_folders = scan_gallery()
    from common_lib.modules.vision.schemas import VisionGalleryFolder, VisionGalleryItem

    return VisionGalleryResponse(
        folders=[
            VisionGalleryFolder(
                name=f["name"],
                images=[VisionGalleryItem(**img) for img in f["images"]],
            )
            for f in gallery_folders
        ]
    )


# ---------------------------------------------------------------------------
# Diffusers Runtime endpoints
# ---------------------------------------------------------------------------


@router.get("/runtime/models")
async def runtime_list_models():
    """List all currently loaded diffusion models."""
    models = list_loaded_models()
    return RuntimeListResponse(
        models=[RuntimeModelInfo(**m) for m in models]
    )


@router.get("/runtime/families")
async def runtime_list_families():
    """List all supported model families with capabilities."""
    families = list_supported_families()
    return RuntimeFamiliesResponse(
        families=[RuntimeFamilyInfo(**f) for f in families]
    )


@router.post("/runtime/load", response_model=RuntimeLoadResponse)
async def runtime_load_model(request: RuntimeLoadRequest):
    """Load a diffusion model into GPU memory."""
    result = load_model(
        family=request.family,
        model_id=request.model_id,
        torch_dtype=request.torch_dtype,
    )
    if result.get("error"):
        return RuntimeLoadResponse(status="error", error=result["error"])
    return RuntimeLoadResponse(
        status="success",
        family_key=result["family_key"],
        family=result["family"],
        model_id=result["model_id"],
    )


@router.post("/runtime/unload", response_model=RuntimeUnloadResponse)
async def runtime_unload_model(request: RuntimeUnloadRequest):
    """Unload a diffusion model to free GPU memory."""
    result = unload_model(family_key=request.family_key)
    if result.get("error"):
        return RuntimeUnloadResponse(status="error", message=result["error"])
    return RuntimeUnloadResponse(status="success", message=result["message"])


@router.post("/runtime/generate", response_model=RuntimeGenerateResponse)
async def runtime_generate(request: RuntimeGenerateRequest):
    """Generate images using a loaded or auto-selected model."""
    result = generate_image(
        prompt=request.prompt,
        negative_prompt=request.negative_prompt or "",
        width=request.width or 512,
        height=request.height or 512,
        num_inference_steps=request.num_inference_steps or 30,
        guidance_scale=request.guidance_scale or 7.5,
        seed=request.seed,
        family_key=request.family_key,
        family=request.family or "auto",
        num_images=request.num_images or 1,
    )
    if result.get("error"):
        return RuntimeGenerateResponse(status="error", error=result["error"])
    return RuntimeGenerateResponse(
        status="success",
        images=result["images"],
        seed=result["seed"],
        elapsed_seconds=result["elapsed_seconds"],
        model_family=result["model_family"],
    )


__all__ = ["router"]
