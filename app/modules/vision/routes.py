from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import Any, Dict
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
            
        profile_info = {
            "id": d.name,
            "name": d.name,
            "cover": None
        }
        
        # Look for cover image (base64)
        char_assets = d / "assets"
        cover_path = None
        if char_assets.exists():
            cover_files = list(char_assets.glob("cover.*"))
            if cover_files:
                cover_path = cover_files[0]
            else:
                all_imgs = list(char_assets.glob("*.jpg")) + list(char_assets.glob("*.png")) + list(char_assets.glob("*.webp"))
                if all_imgs:
                    cover_path = all_imgs[0]

        if cover_path and cover_path.exists():
            try:
                with open(cover_path, "rb") as image_file:
                    ext = cover_path.suffix.lower().replace(".", "")
                    if ext == "jpg": ext = "jpeg"
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
        all_images = list(char_dir.glob("*.jpg")) + list(char_dir.glob("*.png")) + list(char_dir.glob("*.webp"))
        if not all_images:
            return {"path": None}
        cover_path = f"{name}/assets/{all_images[0].name}"
    else:
        cover_path = f"{name}/assets/{cover_files[0].name}"
        
    return {"path": f"/api/v1/profiles/{cover_path}"} # We will mount this static route soon

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
    return ["flux", "sdxl", "sd15", "zimage", "segmentation", "upscale", "detailing", "facerestore", "facedetection", "insightface", "sam", "face_models", "controlnet"]

@router.get("/models/list")
def list_checkpoints_by_category(category: str = "sd15"):
    """
    Returns an indexed list of checkpoints filtered by category.
    """
    from common_lib.modules.image_processing.core.common.loading.files import get_model_catalog
    models = get_model_catalog(category)
    # Extract just the filenames/ids for UI select box
    return sorted([m.get("model_id") for m in models if m.get("model_id")])
@router.get("/samplers")
def list_samplers():
    """
    Returns a list of available samplers with their 'best for' descriptions.
    """
    from common_lib.modules.ai_models.adapters.constants import SAMPLER_MAP, SAMPLER_DESCRIPTIONS
    
    results = []
    # We want to return unique backend samplers with their friendly descriptions
    # Note: SAMPLER_MAP contains aliases, but we only want to show primary ones in UI usually
    # or we can just return everything that has a description.
    for key in SAMPLER_DESCRIPTIONS.keys():
        label = key.replace("_", " ").title().replace("Dpm", "DPM").replace("Sde", "SDE")
        results.append({
            "id": key,
            "label": label,
            "bestFor": SAMPLER_DESCRIPTIONS.get(key, "")
        })
    return results

@router.get("/schedulers")
def list_schedulers():
    """
    Returns a list of available noise schedulers with descriptions.
    """
    from common_lib.modules.ai_models.adapters.constants import SCHEDULER_DESCRIPTIONS
    
    results = []
    for key, desc in SCHEDULER_DESCRIPTIONS.items():
        results.append({
            "id": key,
            "label": key.title(),
            "bestFor": desc
        })
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
            encoding='utf-8'
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
