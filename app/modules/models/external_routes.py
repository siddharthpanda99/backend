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
import re

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_civitai_url(url: str) -> Dict[str, Any]:
    """
    Parse a Civitai URL to extract model_id and version_id.
    Examples:
    - https://civitai.com/models/4384/dreamshaper -> {model_id: 4384}
    - https://civitai.com/models/4384/dreamshaper?modelVersionId=128713 -> {model_id: 4384, version_id: 128713}
    - /models/4384/dreamshaper?modelVersionId=128713 -> {model_id: 4384, version_id: 128713}
    """
    # Remove trailing slashes and normalize
    url = url.strip().rstrip("/")

    # Extract model_id from /models/<id>/...
    model_match = re.search(r"/models/(\d+)", url)
    if not model_match:
        raise HTTPException(
            status_code=400, detail="Invalid Civitai URL - could not find model ID"
        )

    model_id = int(model_match.group(1))

    # Extract version_id from ?modelVersionId=<id>
    version_match = re.search(r"[?&]modelVersionId=(\d+)", url)
    version_id = int(version_match.group(1)) if version_match else None

    return {"model_id": model_id, "version_id": version_id}


@router.get("/civitai/parse-url", response_model=APIResponse[Dict[str, Any]])
async def parse_civitai_url_endpoint(
    url: str = Query(..., description="Civitai model URL"),
):
    """
    Parse a Civitai URL and return model_id and version_id.
    """
    try:
        result = parse_civitai_url(url)
        return APIResponse(data=result, message="URL parsed successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to parse URL: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/civitai/versions/{model_id}", response_model=APIResponse[List[Dict[str, Any]]]
)
async def get_civitai_model_versions(model_id: int):
    """
    Get all versions for a specific Civitai model.
    """
    try:
        client = CivitAIClient()
        details = client.get_model_details(model_id)

        versions = []
        for version in details.get("modelVersions", []):
            versions.append(
                {
                    "id": version.get("id"),
                    "name": version.get("name"),
                    "created_at": version.get("createdAt"),
                    "download_url": f"/api/v1/models/civitai/download",
                    "files": [
                        {
                            "id": f.get("id"),
                            "name": f.get("name"),
                            "size": f.get("size"),
                            "format": f.get("format"),
                            "resolution": f.get("resolution"),
                        }
                        for f in version.get("files", [])
                    ],
                }
            )

        return APIResponse(data=versions, message=f"Found {len(versions)} versions")
    except Exception as e:
        logger.error(f"Failed to get model versions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/civitai/search", response_model=APIResponse[Dict[str, Any]])
async def search_civitai(
    query: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    limit: int = Query(20),
    page: int = Query(1),
    sort: Optional[str] = Query("Highest Rated"),
    period: Optional[str] = Query("AllTime"),
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
            period=period,
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
    model_data: Dict[str, Any], container: AIModelsContainer = Depends(get_container)
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
                tasks = ["controlnet_canny"]  # default
            elif civit_type == "VAE":
                tasks = ["vae_decode"]
            else:
                tasks = ["image_generation"]

        model_data["tasks"] = tasks
        model_data["modality"] = "image"  # Always image for Civitai models

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
            message=f"Model {model.name} registered to {user_reg_path}",
        )
    except Exception as e:
        logger.error(f"Failed to register Civitai model: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/civitai/download", response_model=APIResponse[Dict[str, Any]])
async def download_civitai_model(
    payload: Dict[str, Any], container: AIModelsContainer = Depends(get_container)
):
    """
    Triggers the download of a Civitai model version.

    Supports:
    - Direct: {model_id, version_id, file_id}
    - URL: {url: "https://civitai.com/models/4384/dreamshaper?modelVersionId=128713"}
    - Hierarchy: destination subfolder based on model type
    """
    url = payload.get("url")
    model_id = payload.get("model_id")
    version_id = payload.get("version_id")
    file_id = payload.get("file_id")
    model_type = payload.get("model_type", "Checkpoint")

    # Parse URL if provided
    if url and not (model_id and version_id):
        parsed = parse_civitai_url(url)
        model_id = parsed.get("model_id")
        version_id = parsed.get("version_id")

    if not model_id or not version_id:
        raise HTTPException(
            status_code=400,
            detail="model_id and version_id are required (provide directly or via url)",
        )

    # Map model type to hierarchy path
    hierarchy_map = {
        "Checkpoint": "checkpoints",
        "LORA": "loras",
        "LoCon": "loras",
        "VAE": "vae",
        "Controlnet": "controlnet",
        "TextualInversion": "embeddings",
        "Hypernetwork": "hypernetworks",
        "Upscaler": "upscale",
    }
    subfolder = hierarchy_map.get(model_type, "checkpoints")

    # Allow custom override (use directly if provided), otherwise construct from hierarchy
    custom_dest = payload.get("destination")
    if custom_dest:
        # Custom destination is used as-is (e.g., "checkpoints/sd15")
        destination_subfolder = custom_dest
    else:
        # Use hierarchy path directly
        destination_subfolder = subfolder

    try:
        from common_lib.modules.ai_models.event_bus import EventBus
        from common_lib.modules.external_platforms.civitai.client import CivitAIClient
        import threading
        import os
        import json
        from pathlib import Path

        # Create a unique task ID
        task_id = f"civitai-{model_id}-{version_id}"

        # Get the event bus from the container's downloader
        event_bus = container.downloader.event_bus

        # Create CivitAI client for API calls
        client = CivitAIClient()

        # Persist task to a queue file for restart resilience
        # Using a simple file-based queue that can be reloaded on startup
        queue_dir = Path(os.environ.get("MODEL_QUEUE_DIR", "/tmp/model_downloads"))
        queue_dir.mkdir(exist_ok=True)

        # Get expected file size from API upfront for persistence
        expected_size = None
        try:
            version_details = client.get_version_details(version_id)
            if version_details and file_id:
                for f in version_details.get("files", []):
                    if str(f.get("id")) == str(file_id):
                        expected_size = f.get("size")
                        break
            elif version_details and version_details.get("files"):
                expected_size = version_details["files"][0].get("size")
        except Exception as e:
            logger.warning(f"Could not get expected size from API: {e}")

        task_data = {
            "task_id": task_id,
            "model_id": model_id,
            "version_id": version_id,
            "file_id": file_id,
            "destination_subfolder": destination_subfolder,
            "model_type": model_type,
            "expected_size": expected_size,
            "created_at": str(Path(__file__).parent),
            "status": "pending",
        }

        # Save to queue file (survives server restart)
        queue_file = queue_dir / f"{task_id}.json"
        with open(queue_file, "w") as f:
            json.dump(task_data, f)

        logger.info(f"Download task saved to queue: {queue_file}")

        def run_download():
            try:
                # Emit started event
                event_bus.publish(
                    task_id,
                    {
                        "task_id": task_id,
                        "status": "started",
                        "progress": 0,
                        "model_id": model_id,
                        "version_id": version_id,
                        "destination": destination_subfolder,
                        "expected_size": expected_size,
                    },
                )

                downloader = CivitAIDownloader(mirror_service=container.mirror_service)

                # Track disk-based progress while download runs
                import time

                last_disk_size = 0
                disk_check_interval = 2  # seconds

                def disk_progress_check():
                    nonlocal last_disk_size
                    while True:
                        if target_path.exists():
                            current_size = target_path.stat().st_size
                            if current_size != last_disk_size:
                                last_disk_size = current_size
                                if expected_size and expected_size > 0:
                                    disk_progress = int(
                                        (current_size / expected_size) * 100
                                    )
                                    event_bus.publish(
                                        task_id,
                                        {
                                            "task_id": task_id,
                                            "status": "downloading",
                                            "progress": disk_progress,
                                            "downloaded": current_size,
                                            "total": expected_size,
                                            "expected_size": expected_size,
                                            "source": "disk",
                                        },
                                    )
                        time.sleep(disk_check_interval)

                disk_thread = threading.Thread(target=disk_progress_check, daemon=True)
                disk_thread.start()

                target_path = downloader.download_model(
                    model_id=model_id,
                    version_id=version_id,
                    file_id=file_id,
                    destination_subfolder=destination_subfolder,
                    model_type=model_type,
                    progress_callback=lambda d, t: event_bus.publish(
                        task_id,
                        {
                            "task_id": task_id,
                            "status": "downloading",
                            "progress": int((d / t * 100)) if t > 0 else 0,
                            "downloaded": d,
                            "total": t,
                            "expected_size": expected_size,
                        },
                    ),
                )
                logger.info(f"Downloaded to {target_path}")

                # Verify download completed successfully
                if not target_path.exists():
                    raise Exception(f"Downloaded file not found at {target_path}")

                file_size = target_path.stat().st_size
                if file_size < 1024:  # Less than 1KB is suspicious
                    raise Exception(
                        f"Downloaded file is too small ({file_size} bytes) - possibly corrupted"
                    )

                # Compare with expected size from API
                if (
                    expected_size and abs(file_size - expected_size) > 1024
                ):  # Allow 1KB tolerance
                    raise Exception(
                        f"Downloaded file size ({file_size} bytes) does not match expected ({expected_size} bytes) - possibly incomplete"
                    )

                logger.info(f"Verified download: {target_path} ({file_size} bytes)")

                # Emit completion event
                event_bus.publish(
                    task_id,
                    {
                        "task_id": task_id,
                        "status": "completed",
                        "progress": 100,
                        "file_path": str(target_path),
                        "model_id": model_id,
                        "version_id": version_id,
                    },
                )

                event_bus.publish(
                    "__global__",
                    {
                        "task_id": task_id,
                        "status": "completed",
                        "progress": 100,
                        "file_path": str(target_path),
                    },
                )

                # Register in local registry (registry_user.yaml)
                try:
                    from common_lib.modules.ai_models.registry.exporter import (
                        RegistryExporter,
                    )
                    from common_lib.modules.ai_models.domain.entities import ModelEntity

                    # Get model info from Civitai
                    client = CivitAIClient()
                    model_info = client.get_model_details(model_id)

                    # Extract version info
                    version_info = None
                    for v in model_info.get("modelVersions", []):
                        if v.get("id") == version_id:
                            version_info = v
                            break

                    # Build model entity for registry
                    model_data = {
                        "id": f"civitai-{model_id}",
                        "name": model_info.get("name", f"civitai_{model_id}"),
                        "display_group": f"Image - {model_type} Checkpoints",
                        "model_type": model_type.lower()
                        .replace("checkpoint", "sd15")
                        .replace("lora", "sd15"),
                        "hierarchy": f"{destination_subfolder}",
                        "modality": "image",
                        "tasks": ["text_to_image"],
                        "repo_id": f"civitai:{model_id}",
                        "file_path": str(target_path),
                        "description": f"Downloaded from Civitai: {version_info.get('name') if version_info else 'N/A'}",
                        "version": str(version_id) if version_info else "1.0",
                        "provider": "civitai",
                    }

                    model = ModelEntity(**model_data)

                    # Register to container
                    container.registry_service.register_model(model)

                    # Export to user registry
                    user_reg_path = os.path.join(
                        container.registry_dir, "registry_user.yaml"
                    )
                    exporter = RegistryExporter(
                        container.registry_service, user_reg_path
                    )
                    exporter.export_to_yaml()

                    logger.info(f"Registered model to {user_reg_path}")

                except Exception as reg_err:
                    logger.warning(f"Could not auto-register: {reg_err}")

                finally:
                    # Remove from queue on completion (success or failure)
                    try:
                        queue_file.unlink(missing_ok=True)
                    except:
                        pass

            except Exception as e:
                logger.error(f"Background download failed: {e}")
                # Emit failed event
                try:
                    event_bus.publish(
                        task_id,
                        {
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(e),
                        },
                    )
                    event_bus.publish(
                        "__global__",
                        {
                            "task_id": task_id,
                            "status": "failed",
                            "error": str(e),
                        },
                    )
                except:
                    pass
                # Remove from queue on failure too
                try:
                    queue_file.unlink(missing_ok=True)
                except:
                    pass

        thread = threading.Thread(target=run_download, daemon=True)
        thread.start()

        return APIResponse(
            data={
                "status": "downloading",
                "model_id": model_id,
                "version_id": version_id,
                "destination": destination_subfolder,
            },
            message="Civitai download started - progress via /api/v1/models/tasks/stream",
        )
    except Exception as e:
        logger.error(f"Failed to trigger Civitai download: {e}")
        # Emit error event
        try:
            event_bus.publish(
                task_id,
                {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                    "model_id": model_id,
                    "version_id": version_id,
                },
            )
            event_bus.publish(
                "__global__",
                {
                    "task_id": task_id,
                    "status": "failed",
                    "error": str(e),
                },
            )
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))
