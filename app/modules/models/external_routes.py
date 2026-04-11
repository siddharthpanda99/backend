from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict, Any, Optional
from common_lib.modules.external_platforms.civitai.client import CivitAIClient
from common_lib.modules.external_platforms.civitai.downloader import CivitAIDownloader
from common_lib.modules.ai_models.container import AIModelsContainer
from common_lib.modules.ai_models.domain.entities import ModelEntity
from app.modules.common.types.index import APIResponse
from app.modules.models.routes import get_container
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/civitai/search", response_model=APIResponse[Dict[str, Any]])
async def search_civitai(
    query: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    limit: int = Query(20),
    page: int = Query(1),
    sort: Optional[str] = Query("Highest Rated"),
    period: Optional[str] = Query("AllTime")
):
    """
    Search Civitai for models.
    """
    try:
        client = CivitAIClient()
        results = client.search_models(
            query=query,
            tag=tag,
            model_type=model_type,
            limit=limit,
            page=page,
            sort=sort,
            period=period
        )
        return APIResponse(data=results, message="Civitai search results")
    except Exception as e:
        logger.error(f"Civitai search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/civitai/models/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def get_civitai_model_details(model_id: int):
    """
    Get detailed information for a specific Civitai model.
    """
    try:
        client = CivitAIClient()
        details = client.get_model_details(model_id)
        return APIResponse(data=details, message="Civitai model details")
    except Exception as e:
        logger.error(f"Failed to get Civitai model details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/civitai/register", response_model=APIResponse[Dict[str, Any]])
async def register_civitai_model(
    model_data: Dict[str, Any],
    container: AIModelsContainer = Depends(get_container)
):
    """
    Registers a Civitai model in the local registry.
    """
    try:
        if "id" not in model_data or "name" not in model_data:
            raise HTTPException(status_code=400, detail="id and name are required")

        # Map Civitai type to ModelTask
        civit_type = model_data.get("display_group", "Checkpoint")
        tasks = model_data.get("tasks", [])
        
        if not tasks:
            if civit_type == "Checkpoint":
                tasks = ["image_generation"]
            elif civit_type in ["LORA", "LoCon"]:
                tasks = ["lora"]
            elif civit_type == "Controlnet":
                tasks = ["controlnet_canny"] # default
            elif civit_type == "VAE":
                tasks = ["vae_decode"]
            else:
                tasks = ["image_generation"]
        
        model_data["tasks"] = tasks
        model_data["modality"] = "image" # Always image for Civitai models

        # Create ModelEntity
        model = ModelEntity(**model_data)
        
        container.registry_service.register_model(model)

        # Persist to registry_user.yaml
        user_reg_path = os.path.join(container.registry_dir, "registry_user.yaml")
        from common_lib.modules.ai_models.registry.exporter import RegistryExporter
        exporter = RegistryExporter(container.registry_service, user_reg_path)
        exporter.export_to_yaml()

        return APIResponse(
            data=model.model_dump(),
            message=f"Model {model.name} registered to {user_reg_path}"
        )
    except Exception as e:
        logger.error(f"Failed to register Civitai model: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/civitai/download", response_model=APIResponse[Dict[str, Any]])
async def download_civitai_model(
    payload: Dict[str, Any],
    container: AIModelsContainer = Depends(get_container)
):
    """
    Triggers the download of a Civitai model version.
    """
    model_id = payload.get("model_id")
    version_id = payload.get("version_id")
    file_id = payload.get("file_id")
    destination_subfolder = payload.get("destination", "image_models/checkpoints")

    if not model_id or not version_id:
        raise HTTPException(status_code=400, detail="model_id and version_id are required")

    try:
        # We use the MirrorService injected in AIModelsContainer (downloader)
        # Note: CivitAIDownloader is part of external_platforms, 
        # but it uses path mapping from MirrorService.
        
        downloader = CivitAIDownloader(mirror_service=container.mirror_service)
        
        # Fire and forget download/mirror task?
        # For now, we'll run it synchronously or starting a background task
        # But our SSE downloader system is preferred.
        
        # Let's check how the ModelDownloaderAdapter handles other downloads.
        # For now, we'll just trigger it.
        
        import threading
        def run_download():
            try:
                downloader.download_model(
                    model_id=model_id,
                    version_id=version_id,
                    file_id=file_id,
                    destination_subfolder=destination_subfolder
                )
            except Exception as e:
                logger.error(f"Background download failed: {e}")

        thread = threading.Thread(target=run_download)
        thread.start()

        return APIResponse(
            data={"status": "downloading", "model_id": model_id, "version_id": version_id},
            message="Civitai download started in background"
        )
    except Exception as e:
        logger.error(f"Failed to trigger Civitai download: {e}")
        raise HTTPException(status_code=500, detail=str(e))
