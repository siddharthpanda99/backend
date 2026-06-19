"""Vision Routes — Thin API layer delegating to common_lib services."""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from common_lib.modules.vision.schemas import (
    VisionGenerateRequest,
    VisionGenerateResponse,
    VisionWorkflowRequest,
    VisionWorkflowResponse,
    VisionGalleryResponse,
    VisionPromptPreviewRequest,
    VisionPromptPreviewResponse,
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


__all__ = ["router"]
