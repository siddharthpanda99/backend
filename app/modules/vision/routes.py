from fastapi import APIRouter, HTTPException
from typing import Any, Dict, List, Optional
from common_lib.modules.image_processing.controllers.vision_task_controller import (
    VisionTaskController,
)
from common_lib.modules.image_processing.functions.text.dynamic_engine.models import WildcardRecord
from common_lib.modules.image_processing.functions.text.dynamic_engine.sync import WildcardSyncManager
from common_lib.modules.data_storage.database.connection import get_session
from sqlalchemy import or_, func
from sqlmodel import select
from common_lib.modules.vision.schemas import (
    VisionGenerateRequest,
    VisionGenerateResponse,
    VisionWorkflowRequest,
    VisionWorkflowResponse,
    VisionGalleryResponse,
    VisionGalleryItem,
    VisionGalleryFolder,
    VisionPromptPreviewRequest,
    VisionPromptPreviewResponse,
    WildcardRecordSchema,
    WildcardCreateRequest,
    WildcardUpdateRequest,
    WildcardListResponse,
    VisionPresetSchema,
    VisionPresetCreateRequest,
    VisionPresetUpdateRequest,
)
from common_lib.modules.orchestration.infrastructure.sd.models import SdPresetRecord, SdModelRecord

from common_lib.modules.image_processing.functions.text.dynamic_engine import PromptEngine, WildcardManager as WManager
from common_lib.modules.image_processing.nodes.sampling.samplers_library import (
    get_all_samplers,
    get_all_schedulers,
)
from common_lib.modules.image_processing.constants import SAMPLER_METADATA, SCHEDULER_METADATA
from common_lib.paths import IMAGE_MODELS_ROOT, GENERATED_CONTENT, get_repo_root
import os
import time
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
controller = VisionTaskController()


@router.get("/prompts/configs/legacy")
async def get_prompt_configs():
    """
    Get default prompt configurations from JSON file.
    """
    import json
    try:
        config_path = os.path.join(os.path.dirname(__file__), "prompts_config.json")
        if not os.path.exists(config_path):
            return []
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load prompt configs: {e}")
        return []


@router.post("/prompts/preview", response_model=VisionPromptPreviewResponse)
async def preview_prompts(request: VisionPromptPreviewRequest):
    """
    Preview dynamic prompt expansion.
    """
    try:
        repo_root = get_repo_root()
        wildcard_path = os.path.join(repo_root, "resources", "wildcards")
        if not os.path.exists(wildcard_path):
            wildcard_path = os.path.join(repo_root, "Resources", "wildcards")
            
        if not os.path.exists(wildcard_path):
            os.makedirs(wildcard_path, exist_ok=True)
            
        wm = WManager(wildcard_path)
        engine = PromptEngine(wm)
        
        if request.combinatorial:
            prompts = engine.expand_combinatorial(request.template, limit=request.limit or 10)
        else:
            prompts = engine.expand_random(
                request.template, 
                num_prompts=request.limit or 10, 
                seed=request.seed
            )
            
        return VisionPromptPreviewResponse(
            status="success",
            prompts=prompts,
            count=len(prompts)
        )
    except Exception as e:
        return VisionPromptPreviewResponse(
            status="error",
            prompts=[],
            count=0,
            message=str(e)
        )


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
    """List all available models/checkpoints from database."""
    with next(get_session()) as session:
        # Query only checkpoints for the generic models list
        stmt = select(SdModelRecord).where(SdModelRecord.type == "checkpoint")
        models = session.execute(stmt).scalars().all()
        
        # If DB is empty, fallback to filesystem scan once
        if not models:
            logger.info("DB models empty, falling back to filesystem scan")
            checkpoints = _get_checkpoints_from_filesystem()
            return [
                {"id": c["id"], "name": c["name"], "category": c.get("category", "")}
                for c in checkpoints
            ]
            
        return [
            {
                "id": m.id, 
                "name": m.name, 
                "category": m.metadata_json.get("category", ""),
                "is_active": m.is_active,
                "trigger_words": m.trigger_words
            }
            for m in models
        ]


@router.get("/models/list", response_model=List[Dict[str, Any]])
async def list_models_by_category(category: str = "sd15"):
    """List models filtered by category (sd15, sdxl, etc.) using database."""
    with next(get_session()) as session:
        stmt = select(SdModelRecord).where(SdModelRecord.type == "checkpoint")
        models = session.execute(stmt).scalars().all()
        
        # Filter by category in metadata_json
        results = [
            {"id": m.id, "name": m.name, "category": category} 
            for m in models 
            if m.metadata_json.get("category") == category
        ]
        
        # Fallback to filesystem if no results
        if not results:
            checkpoints = _get_checkpoints_from_filesystem(category)
            return [
                {"id": c["id"], "name": c["name"], "category": category} for c in checkpoints
            ]
            
        return results


@router.get("/samplers", response_model=List[Dict[str, Any]])
async def list_samplers(implementation: str = "diffusers"):
    """List available samplers with metadata."""
    samplers = get_all_samplers(implementation)
    results = []
    for s in samplers:
        # Normalize key for metadata lookup (strip _comfy etc)
        meta_key = s.replace("_comfy", "").replace("_ancestral", "_a").replace("ancestral", "a")
        if meta_key == "euler_a": meta_key = "euler_ancestral" # Match our constants
        
        meta = SAMPLER_METADATA.get(meta_key, SAMPLER_METADATA.get(s, {}))
        
        results.append({
            "id": s,
            "label": s.replace("_", " ").title(),
            "backend": implementation,
            "description": meta.get("description", "A sampling algorithm for noise reduction."),
            "bestFor": meta.get("best_for", "General purpose generation."),
            "type": meta.get("type", "Standard"),
            "recommendedSteps": meta.get("steps", "20-30"),
            "compatibleSchedulers": meta.get("compatible_schedulers", ["normal"])
        })
    return results


@router.get("/schedulers", response_model=List[Dict[str, Any]])
async def list_schedulers(provider: str = "diffusers"):
    """List available schedulers with metadata."""
    schedulers = get_all_schedulers(provider)
    results = []
    for s in schedulers:
        meta_key = s.replace("_comfy", "")
        meta = SCHEDULER_METADATA.get(meta_key, SCHEDULER_METADATA.get(s, {}))
        
        results.append({
            "id": s,
            "label": s.replace("_", " ").title(),
            "backend": provider,
            "description": meta.get("description", "A schedule for noise levels across steps."),
            "bestFor": meta.get("best_for", "Standard models."),
            "behavior": meta.get("behavior", "Linear"),
            "gotchas": meta.get("gotchas", {"default": ""})
        })
    return results


@router.get("/checkpoints", response_model=List[Dict[str, Any]])
async def list_checkpoints(category: str = None):
    """List checkpoints from database with filesystem fallback."""
    with next(get_session()) as session:
        stmt = select(SdModelRecord).where(SdModelRecord.type == "checkpoint")
        models = session.execute(stmt).scalars().all()
        
        if category:
            results = [
                {
                    "id": m.id, 
                    "value": m.id,
                    "name": m.name, 
                    "label": f"{m.name} [{category}]",
                    "category": category
                } 
                for m in models 
                if m.metadata_json.get("category") == category
            ]
        else:
            results = [
                {
                    "id": m.id, 
                    "value": m.id,
                    "name": m.name, 
                    "label": f"{m.name} [{m.metadata_json.get('category', 'default')}]",
                    "category": m.metadata_json.get('category', 'default')
                } 
                for m in models
            ]
            
        if not results:
            return _get_checkpoints_from_filesystem(category)
            
        return results


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


