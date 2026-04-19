from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import Any, Dict
from .schemas import (
    VisionGenerateRequest,
    VisionGenerateResponse,
    VisionWorkflowRequest,
    VisionWorkflowResponse,
)
from .service import vision_service
from common_lib.modules.workflows.standard.execution.signals import (
    execution_signals,
    ExecutionSignal,
)
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()

from fastapi.responses import StreamingResponse
import json


@router.post("/generate-high-res", response_model=APIResponse[VisionGenerateResponse])
def generate_vision_task(request_in: VisionGenerateRequest):
    """
    Triggers a 2-pass SD 1.5 High-Resolution generation.
    """
    result = vision_service.generate_high_res(request_in)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return APIResponse(
        data=VisionGenerateResponse(**result),
        message="Vision generation completed successfully",
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


@router.post("/workflow-run", response_model=APIResponse[VisionWorkflowResponse])
def run_workflow_with_config(request_in: VisionWorkflowRequest):
    """
    Run a workflow YAML with a data config YAML overlay.
    Example: workflow_yaml=hires_fix.sd15.dreamshaper, config_yaml=cyberpunk_streetscape
    """
    result = vision_service.run_workflow_with_config(
        workflow_yaml=request_in.workflow_yaml,
        config_yaml=request_in.config_yaml,
        seed=request_in.seed,
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])

    return APIResponse(
        data=VisionWorkflowResponse(**result),
        message="Workflow execution completed successfully",
    )


@router.get("/gallery")
def get_vision_gallery():
    """
    Returns a list of all images in the generated_content folder.
    """
    return vision_service.get_gallery()


@router.post("/upload")
def upload_vision_asset(payload: Dict[str, Any]):
    """
    Uploads an image (as base64) to the local assets store for use in workflows.
    Expects {"image": "base64...", "filename": "name.jpg"}
    """
    result = vision_service.save_upload(payload)
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return APIResponse(data=result, message="Asset uploaded successfully")


@router.get("/characters")
def list_characters():
    """
    Returns a list of all available character profiles with metadata and base64 cover images.
    """
    import base64
    from common_lib.paths import CHARACTER_PROFILES_DIR

    if not CHARACTER_PROFILES_DIR.exists():
        return []

    results = []
    for d in CHARACTER_PROFILES_DIR.iterdir():
        if not d.is_dir():
            continue

        profile_info = {"id": d.name, "name": d.name, "cover": None}

        # Look for cover image (base64)
        char_assets = d / "assets"
        cover_path = None
        if char_assets.exists():
            cover_files = list(char_assets.glob("cover.*"))
            if cover_files:
                cover_path = cover_files[0]
            else:
                all_imgs = (
                    list(char_assets.glob("*.jpg"))
                    + list(char_assets.glob("*.png"))
                    + list(char_assets.glob("*.webp"))
                )
                if all_imgs:
                    cover_path = all_imgs[0]

        if cover_path and cover_path.exists():
            try:
                with open(cover_path, "rb") as image_file:
                    ext = cover_path.suffix.lower().replace(".", "")
                    if ext == "jpg":
                        ext = "jpeg"
                    encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                    profile_info["cover"] = f"data:image/{ext};base64,{encoded_string}"
            except Exception as e:
                print(f"Error encoding cover for {d.name}: {e}")

        results.append(profile_info)

    results.sort(key=lambda x: x["name"])
    return results


@router.get("/characters/{name}/cover")
def get_character_cover(name: str):
    """
    Returns the relative path to the cover image for a specific character.
    Heuristic: looks for cover.png, cover.jpg, or any file starting with 'cover' in assets.
    """
    from common_lib.paths import CHARACTER_PROFILES_DIR

    char_dir = CHARACTER_PROFILES_DIR / name / "assets"

    if not char_dir.exists():
        return {"path": None}

    # Search for cover files
    cover_files = list(char_dir.glob("cover.*"))
    if not cover_files:
        # Fallback: any image in assets if no 'cover' exists
        all_images = (
            list(char_dir.glob("*.jpg"))
            + list(char_dir.glob("*.png"))
            + list(char_dir.glob("*.webp"))
        )
        if not all_images:
            return {"path": None}
        cover_path = f"{name}/assets/{all_images[0].name}"
    else:
        cover_path = f"{name}/assets/{cover_files[0].name}"

    return {
        "path": f"/api/v1/profiles/{cover_path}"
    }  # We will mount this static route soon


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


@router.get("/models/categories")
def list_model_categories():
    """
    Returns the top-level categories of available vision models.
    """
    return [
        "flux",
        "sdxl",
        "sd15",
        "zimage",
        "segmentation",
        "upscale",
        "detailing",
        "facerestore",
        "facedetection",
        "insightface",
        "sam",
        "face_models",
        "controlnet",
    ]


@router.get("/models/list")
def list_checkpoints_by_category(category: str = "sd15"):
    """
    Returns an indexed list of checkpoints filtered by category.
    """
    from common_lib.modules.image_processing.core.common.loading.files import (
        get_model_catalog,
    )

    models = get_model_catalog(category)
    # Extract just the filenames/ids for UI select box
    # Return full objects to allow UI to show descriptions/tooltips
    return models


@router.get("/samplers")
def list_samplers():
    """
    Returns a list of available samplers with their 'best for' descriptions.
    """
    from common_lib.modules.ai_models.adapters.constants import SAMPLER_DESCRIPTIONS

    results = []
    # We want to return unique backend samplers with their friendly descriptions
    # Note: SAMPLER_MAP contains aliases, but we only want to show primary ones in UI usually
    # or we can just return everything that has a description.
    for key in SAMPLER_DESCRIPTIONS.keys():
        label = (
            key.replace("_", " ").title().replace("Dpm", "DPM").replace("Sde", "SDE")
        )
        results.append(
            {"id": key, "label": label, "bestFor": SAMPLER_DESCRIPTIONS.get(key, "")}
        )
    return results


@router.get("/schedulers")
def list_schedulers():
    """
    Returns a list of available noise schedulers with descriptions.
    """
    from common_lib.modules.ai_models.adapters.constants import SCHEDULER_DESCRIPTIONS

    results = []
    for key, desc in SCHEDULER_DESCRIPTIONS.items():
        results.append({"id": key, "label": key.title(), "bestFor": desc})
    return results


@router.get("/filesystem/pick")
def pick_directory():
    """
    Triggers a native OS folder picker via PowerShell, starting at GENERATED_CONTENT.
    Returns the absolute path selected.
    """
    from common_lib.paths import GENERATED_CONTENT
    import subprocess
    import json

    start_path = str(GENERATED_CONTENT.resolve()).replace("/", "\\")

    # PowerShell script to open a folder browser dialog
    # We use -WindowStyle Hidden to hide the console window, but it doesn't always work perfectly for the GUI child.
    # However, this is the most robust way without extra pip packages.
    ps_cmd = rf"""
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object System.Windows.Forms.FolderBrowserDialog
$f.Description = 'Select Output Directory'
$f.RootFolder = 'Desktop'
$f.SelectedPath = '{start_path}'
$res = $f.ShowDialog((New-Object System.Windows.Forms.Form -Property @{{TopMost=$true}}))
if ($res -eq 'OK') {{
    Write-Output $f.SelectedPath
}}
"""
    try:
        # Run PowerShell and capture output
        res = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        selected_path = res.stdout.strip()

        if selected_path:
            # Standardize for frontend
            standard_path = selected_path.replace("\\", "/")
            return {"path": standard_path}
        else:
            return {"path": None}

    except Exception as e:
        logger.error(f"Native picker failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────────
# YAML-Driven Node & Workflow Definitions — Option B Runtime Loader
# ─────────────────────────────────────────────────────────────────

import yaml
import logging

logger = logging.getLogger(__name__)


def _load_all_node_definitions() -> Dict[str, dict]:
    """Internal helper to load and index all node definitions."""
    from common_lib.paths import REPO_ROOT

    nodes_dir = REPO_ROOT / "resources" / "nodes"
    registry = {}
    if not nodes_dir.exists():
        return registry

    for yaml_file in sorted(nodes_dir.glob("*.yaml")):
        try:
            with open(yaml_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if data and isinstance(data.get("nodes"), list):
                for node in data["nodes"]:
                    remapped = _remap_node(node)
                    registry[remapped["type"]] = remapped
        except Exception as e:
            logger.error(f"[NodeDefinitions] Failed to load {yaml_file}: {e}")
    return registry


@router.get("/node-definitions")
def get_node_definitions():
    """
    Returns all node definitions as a flat list.
    """
    registry = _load_all_node_definitions()
    return list(registry.values())


def _remap_node(node: dict) -> dict:
    """Converts snake_case YAML keys to camelCase NodeDefinition fields."""
    # If this is a nested node instance, it already has a 'type'.
    # If it's a top-level definition, the 'id' is the 'type'.
    node_type = node.get("type", node.get("id"))

    result = {
        "type": node_type,
        "label": node.get("label", node.get("title")),
        "category": node.get("category", "subflow_internal"),
        "inputs": [_remap_port(p) for p in node.get("inputs", [])],
        "outputs": [_remap_port(p) for p in node.get("outputs", [])],
    }

    # Standard metadata remapping
    for opt_key, ts_key in [
        ("id", "id"),  # Preserve instance ID for nested nodes
        ("title", "title"),
        ("version", "version"),
        ("description", "description"),
        ("color", "color"),
        ("tags", "tags"),
        ("shape", "shape"),
        ("initialX", "initialX"),
        ("initialY", "initialY"),
        ("initial_x", "initialX"),
        ("initial_y", "initialY"),
        ("allow_multiple_edges", "allowMultipleEdges"),
        ("isSubflow", "isSubflow"),
    ]:
        if opt_key in node:
            result[ts_key] = node[opt_key]

    if "nodes" in node:
        # Recursively remap internal nodes
        result["nodes"] = [_remap_node(n) for n in node["nodes"]]

    if "edges" in node:
        result["edges"] = node["edges"]

    if "default_properties" in node:
        result["defaultProperties"] = node["default_properties"]
    if "properties" in node:
        # For definitions, these are property declarations.
        # For instances, these are actual values.
        if isinstance(node["properties"], list):
            result["propertyDefinitions"] = [
                _remap_property(p) for p in node["properties"]
            ]
        else:
            result["properties"] = node["properties"]

    if "dynamic_options" in node:
        result["dynamicOptions"] = node["dynamic_options"]
    return result


def _remap_port(port: dict) -> dict:
    result = {
        "id": port.get("id"),
        "label": port.get("label"),
        "type": port.get("type", "any"),
    }
    for k in ("required", "color", "description"):
        if k in port:
            result[k] = port[k]
    return result


def _remap_property(prop: dict) -> dict:
    result = {
        "name": prop.get("name"),
        "label": prop.get("label"),
        "type": prop.get("type", "text"),
    }
    for k in ("options", "required", "description", "placeholder"):
        if k in prop:
            result[k] = prop[k]
    for snake, camel in [
        ("default", "defaultValue"),
        ("min", "min"),
        ("max", "max"),
        ("step", "step"),
    ]:
        if snake in prop:
            result[camel] = prop[snake]
    return result


@router.get("/workflow-presets")
def get_workflow_presets():
    """
    Returns a list of workflow preset metadata (id, name, description),
    loaded from root resources/workflows/templates/*.yaml.
    """
    from common_lib.modules.image_processing.core.common.loading.templates import (
        list_workflow_templates,
        load_workflow_template,
    )

    results = []
    for name in list_workflow_templates():
        # Load metadata first (non-recursive)
        data = load_workflow_template(name, recursive=False)
        if data is not None:
            results.append(
                {
                    "id": name,
                    "name": data.get("page_title") or data.get("name") or name,
                    "description": data.get("description", ""),
                    "category": data.get("category", "General"),
                    "icon": data.get("icon"),
                }
            )

    return results


@router.get("/workflow-presets/{id}")
def get_workflow_preset(id: str):
    """
    Returns a single full workflow preset by ID, hydrated with node definitions.
    """
    from common_lib.modules.image_processing.core.common.loading.templates import (
        load_workflow_template,
    )

    data = load_workflow_template(id, recursive=True)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Workflow preset '{id}' not found")

    # HYDRATION: Merge node definitions into the response
    registry = _load_all_node_definitions()
    if "nodes" in data:
        hydrated_nodes = []
        for node in data["nodes"]:
            node_type = node.get("type")
            definition = registry.get(node_type, {})

            # Merge: Registry provides defaults, Workflow provides overrides
            hydrated = {
                **definition,
                **node,
                "id": str(node.get("id")),  # Ensure ID is string
                "properties": {
                    **(definition.get("defaultProperties") or {}),
                    **(node.get("properties") or {}),
                },
            }
            hydrated_nodes.append(hydrated)
        data["nodes"] = hydrated_nodes

    return data


@router.get("/model-registry/loras")
def get_lora_registry():
    """
    Returns the LoRA model registry loaded from
    root resources/image_models/registry/loras.yaml.
    """
    from common_lib.paths import REPO_ROOT
    import yaml

    yaml_path = REPO_ROOT / "resources" / "image_models" / "registry" / "loras.yaml"
    if not yaml_path.exists():
        return {"models": []}

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data if data else {"models": []}
    except Exception as e:
        logger.error(f"[LoraRegistry] Failed to load {yaml_path}: {e}")
        return {"models": []}


@router.post("/control")
def control_execution(payload: Dict[str, Any]):
    """
    Sends a signal (stop, skip, pause) to a running workflow by trace_id.
    """
    trace_id = payload.get("trace_id")
    action = payload.get("action")

    if not trace_id or not action:
        raise HTTPException(status_code=400, detail="Missing trace_id or action")

    try:
        signal = ExecutionSignal(action.lower())
        execution_signals.set_signal(trace_id, signal)
        return {"status": "success", "message": f"Signal {action} sent to {trace_id}"}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")
