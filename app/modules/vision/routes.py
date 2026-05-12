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
    VisionGalleryResponse,
    VisionGalleryItem,
    VisionGalleryFolder,
)
from common_lib.modules.image_processing.nodes.sampling.samplers_library import (
    get_all_samplers,
    get_all_schedulers,
)
from common_lib.paths import IMAGE_MODELS_ROOT, GENERATED_CONTENT
import os
import time

router = APIRouter()
controller = VisionTaskController()


def _get_checkpoints_from_filesystem(category: str = None) -> List[Dict[str, str]]:
    """Scan filesystem for checkpoint files."""
    checkpoints_dir = IMAGE_MODELS_ROOT / "checkpoints"
    results = []

    if not checkpoints_dir.exists():
        return results

    if category:
        search_dir = checkpoints_dir / category
        if search_dir.exists():
            if search_dir.is_dir():
                for file in search_dir.iterdir():
                    if file.is_file() and file.suffix in [
                        ".safetensors",
                        ".ckpt",
                        ".pt",
                        ".pth",
                    ]:
                        results.append(
                            {
                                "id": file.stem,
                                "value": file.stem,
                                "name": file.stem,
                                "label": f"{file.stem} [{category}]",
                                "category": category,
                            }
                        )
            elif search_dir.is_file():
                if search_dir.suffix in [".safetensors", ".ckpt", ".pt", ".pth"]:
                    results.append(
                        {
                            "id": search_dir.stem,
                            "value": search_dir.stem,
                            "name": search_dir.stem,
                            "label": f"{search_dir.stem} [{category}]",
                            "category": category,
                        }
                    )
            return results

    for subdir in checkpoints_dir.iterdir():
        if subdir.is_dir():
            for file in subdir.iterdir():
                if file.is_file() and file.suffix in [
                    ".safetensors",
                    ".ckpt",
                    ".pt",
                    ".pth",
                ]:
                    results.append(
                        {
                            "id": file.stem,
                            "value": file.stem,
                            "name": file.stem,
                            "label": f"{file.stem} [{subdir.name}]",
                            "category": subdir.name,
                        }
                    )
        elif subdir.is_file() and subdir.suffix in [
            ".safetensors",
            ".ckpt",
            ".pt",
            ".pth",
        ]:
            results.append(
                {
                    "id": subdir.stem,
                    "value": subdir.stem,
                    "name": subdir.stem,
                    "label": f"{subdir.stem} [checkpoints]",
                    "category": checkpoints_dir.name,
                }
            )

    return results


def get_cached_checkpoints() -> List[Dict[str, str]]:
    """Get all cached checkpoints from filesystem."""
    return _get_checkpoints_from_filesystem()


def _get_discovered_nodes() -> List[Dict[str, Any]]:
    """Get node definitions from auto-discovery via @node decorator."""
    from common_lib.modules.workflows.standard.nodes.comfyui import (
        CLIPTextEncode, CheckpointLoaderSimple, KSampler, EmptyLatentImage,
        VAEDecode, SaveImage, LoadImage, LoraLoader, ControlNetLoader,
        ControlNetApply, LatentUpscale, ImageScale, ImageInvert
    )
    import inspect
    
    node_classes = [
        CLIPTextEncode, CheckpointLoaderSimple, KSampler, EmptyLatentImage,
        VAEDecode, SaveImage, LoadImage, LoraLoader, ControlNetLoader,
        ControlNetApply, LatentUpscale, ImageScale, ImageInvert
    ]
    
    definitions = []
    for cls in node_classes:
        if hasattr(cls, '_is_plugin_node') and getattr(cls, '_is_plugin_node', False):
            node_id = getattr(cls, '_node_metadata', {}).get('name') or cls.__name__
            node_id = "vision." + node_id.lower().replace('_', '_')
            
            sig = inspect.signature(cls.__call__) if callable(cls) else None
            inputs = []
            if sig:
                for param_name, param in sig.parameters.items():
                    if param_name != 'self':
                        inputs.append({
                            "name": param_name,
                            "type": "any",
                            "required": param.default == inspect.Parameter.empty
                        })
            
            definitions.append({
                "type": node_id,
                "label": cls.__name__.replace('_', ' '),
                "category": "vision",
                "description": getattr(cls, '__doc__', '') or cls.__name__ + " node",
                "color": "#6b7280",
                "inputs": inputs,
                "outputs": [{"name": "output", "type": "any"}],
                "properties": []
            })
    
    return definitions


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
    """List all available models/checkpoints."""
    checkpoints = _get_checkpoints_from_filesystem()
    return [
        {"id": c["id"], "name": c["name"], "category": c.get("category", "")}
        for c in checkpoints
    ]


@router.get("/models/list", response_model=List[Dict[str, Any]])
async def list_models_by_category(category: str = "sd15"):
    """List models filtered by category (sd15, sdxl, etc.)"""
    checkpoints = _get_checkpoints_from_filesystem(category)
    return [
        {"id": c["id"], "name": c["name"], "category": category} for c in checkpoints
    ]


@router.get("/samplers", response_model=List[Dict[str, str]])
async def list_samplers(implementation: str = "diffusers"):
    """List available samplers."""
    samplers = get_all_samplers(implementation)
    return [{"id": s, "label": s.replace("_", " ").title(), "backend": implementation} for s in samplers]


@router.get("/schedulers", response_model=List[Dict[str, str]])
async def list_schedulers(provider: str = "diffusers"):
    """List available schedulers."""
    schedulers = get_all_schedulers(provider)
    return [{"id": s, "label": s.replace("_", " ").title(), "backend": provider} for s in schedulers]


@router.get("/checkpoints", response_model=List[Dict[str, str]])
async def list_checkpoints(category: str = None):
    """List checkpoints from filesystem."""
    return _get_checkpoints_from_filesystem(category)


@router.get("/swap-models", response_model=List[str])
async def list_swap_models():
    """List available face swap models (InSwapper, etc)."""
    from common_lib.modules.image_processing.nodes.reactor.base import get_insightface_models
    return get_insightface_models()


@router.get("/face-restore-models", response_model=List[str])
async def list_face_restore_models():
    """List available face restoration models (CodeFormer, GFPGAN, etc)."""
    from common_lib.modules.image_processing.nodes.reactor.base import get_facerestore_models
    return get_facerestore_models()


@router.get("/workflow-presets", response_model=List[Dict[str, Any]])
async def list_workflow_presets():
    """
    Returns a list of available vision workflow presets from central registry.
    Reads from YAML files in templates/workflows/executable - single source of truth.
    """
    try:
        from common_lib.modules.workflows.standard.registry.workflow_registry import get_workflow_registry
        registry = get_workflow_registry()
        return registry.list_workflows()
    except Exception as e:
        logger.error(f"Error loading workflows: {e}")
        return []


@router.get("/workflow-presets/{id}", response_model=Dict[str, Any])
async def get_workflow_preset(id: str):
    """
    Returns the full workflow definition for a specific preset from central registry.
    """
    try:
        from common_lib.modules.workflows.standard.registry.workflow_registry import get_workflow_registry
        registry = get_workflow_registry()
        workflow = registry.get_workflow_preset(id)

        if workflow:
            return workflow
    except Exception as e:
        logger.error(f"Error loading workflow {id}: {e}")

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Workflow '{id}' not found")


@router.get("/nodes", response_model=List[Dict[str, Any]])
async def list_nodes():
    """
    Returns node definitions from auto-discovery via @node decorator.
    Nodes are registered at startup, synced from backend to frontend.
    Workflows include node references - execution is fully backend.
    """
    return _get_discovered_nodes()


@router.post("/execute", response_model=VisionWorkflowResponse)
async def execute_workflow(request: VisionWorkflowRequest):
    """
    Execute a workflow with the provided configuration.
    All node execution happens on backend - UI only sends config.
    """
    try:
        from common_lib.modules.workflows.standard.registry.workflow_registry import get_workflow_registry
        registry = get_workflow_registry()
        
        workflow_def = registry.get_workflow(request.workflow_id)
        if not workflow_def:
            return VisionWorkflowResponse(
                status="error",
                message=f"Workflow '{request.workflow_id}' not found"
            )
        
        config = request.config or {}
        config.update(request.parameters or {})
        
        from common_lib.modules.workflows.standard.builder import WorkflowBuilder
        
        builder = WorkflowBuilder()
        
        workflow_data = {
            'id': workflow_def.get('id'),
            'name': workflow_def.get('name', ''),
            'description': workflow_def.get('description', ''),
            'category': workflow_def.get('category', 'vision'),
            'nodes': workflow_def.get('nodes', []),
            'connections': workflow_def.get('edges', [])
        }
        
        workflow = builder.load_from_dict(workflow_data)
        
        from common_lib.modules.workflows.standard.executor import WorkflowExecutor
        
        executor = WorkflowExecutor()
        state = executor.execute(workflow, config)
        
        result_images = []
        for node_id, output in state.data.get("outputs", {}).items():
            if isinstance(output, dict) and "image" in str(output):
                result_images.append(output.get("image", ""))
        
        return VisionWorkflowResponse(
            status="success" if state.status.value == "completed" else "error",
            message=f"Workflow completed with status: {state.status.value}",
            metadata={
                "execution_id": state.execution_id,
                "steps_completed": len(state.steps),
                "nodes_executed": list(state.data.keys())
            },
            images=result_images
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return VisionWorkflowResponse(
            status="error",
            message=str(e)
        )


@router.get("/gallery", response_model=VisionGalleryResponse)
async def list_gallery():
    """List images from the generated_content directory, grouped by folder."""
    if not GENERATED_CONTENT.exists():
        return VisionGalleryResponse(folders=[])

    from PIL import Image
    import json

    folders_dict: Dict[str, List[VisionGalleryItem]] = {}

    def scan_recursive(base_path: Any, current_path: Any):
        # Calculate relative folder name for grouping
        try:
            rel_path = current_path.relative_to(base_path)
            folder_name = str(rel_path) if str(rel_path) != "." else "root"
        except Exception:
            folder_name = "root"

        if folder_name not in folders_dict:
            folders_dict[folder_name] = []
        
        try:
            for item in current_path.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    scan_recursive(base_path, item)
                elif item.is_file() and item.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
                    metadata = {}
                    stats = item.stat()
                    metadata["timestamp"] = stats.st_mtime
                    metadata["size"] = stats.st_size
                    
                    # Try to extract metadata for PNGs
                    if item.suffix.lower() == ".png":
                        try:
                            with Image.open(item) as img:
                                if img.info:
                                    for key, val in img.info.items():
                                        if isinstance(val, (str, int, float, bool)):
                                            # Special handling for our platform's parameters JSON
                                            if key == "parameters" and isinstance(val, str):
                                                try:
                                                    params = json.loads(val)
                                                    if isinstance(params, dict):
                                                        metadata.update(params)
                                                except Exception:
                                                    metadata[key] = val
                                            else:
                                                metadata[key] = val
                                metadata["width"] = img.width
                                metadata["height"] = img.height
                                metadata["format"] = img.format
                        except Exception:
                            pass
                    
                    # Calculate relative URL for static mounting
                    # The static mount point is /generated/ mapping to GENERATED_CONTENT
                    rel_to_root = item.relative_to(base_path)
                    url_path = str(rel_to_root).replace("\\", "/")
                    
                    folders_dict[folder_name].append(
                        VisionGalleryItem(
                            filename=item.name,
                            url=f"/generated/{url_path}",
                            metadata=metadata,
                            folder=folder_name
                        )
                    )
        except Exception as e:
            print(f"Error scanning {current_path}: {e}")

    # Start recursive scan
    scan_recursive(GENERATED_CONTENT, GENERATED_CONTENT)

    # Convert to Response schema
    gallery_folders = []
    
    # Priority order for folders if we want to show them in a specific order
    # root, upscale, others
    sorted_folder_names = sorted(
        folders_dict.keys(), 
        key=lambda n: (0 if n == "root" else 1, 0 if n == "upscale" else 1, n.lower())
    )

    for name in sorted_folder_names:
        images = folders_dict[name]
        # Sort images by timestamp descending
        images.sort(key=lambda x: (x.metadata or {}).get("timestamp", 0), reverse=True)
        if images:
            gallery_folders.append(VisionGalleryFolder(name=name, images=images))

    return VisionGalleryResponse(folders=gallery_folders)


__all__ = ["router"]
