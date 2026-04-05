import asyncio
import json
import queue
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from app.modules.common.types.index import APIResponse
from common_lib.modules.ai_models.container import AIModelsContainer
from common_lib.modules.ai_models.domain.entities import ModelEntity

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency for AIModelsContainer
def get_container():
    # USes singleton AIModelsContainer
    return AIModelsContainer()

@router.get("/", response_model=APIResponse[List[Dict[str, Any]]])
async def list_models(container: AIModelsContainer = Depends(get_container)):
    """
    List all models in the registry with their current status.
    """
    try:
        # Trigger dynamic health check before listing to ensure accuracy
        container.health_monitor.verify_all_models()
        
        models = container.registry_service.list_models()
        
        # Overlay active task status
        result = []
        for model in models:
            m_dict = model.model_dump()
            active_task = container.downloader.get_download_progress(model.id)
            if active_task.get("status") != "not_found":
                m_dict["download_task"] = active_task
            result.append(m_dict)

        return APIResponse(
            data=result,
            message="Models retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def get_model(model_id: str, container: AIModelsContainer = Depends(get_container)):
    """
    Get detailed information for a specific model.
    """
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    return APIResponse(data=model.model_dump(), message="Model details retrieved")

@router.post("/{model_id}/download", response_model=APIResponse[Dict[str, Any]])
async def download_model(
    model_id: str, 
    force: bool = False,
    container: AIModelsContainer = Depends(get_container)
):
    """
    Trigger a background download for the specified model.
    """
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    try:
        task_id = container.downloader.download_model(model, force=force)
        return APIResponse(
            data={"task_id": task_id, "status": "started"},
            message=f"Download started for {model.name}"
        )
    except Exception as e:
        logger.error(f"Failed to start download for {model.id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/tasks/{task_id}", response_model=APIResponse[Dict[str, Any]])
async def get_download_status(task_id: str, container: AIModelsContainer = Depends(get_container)):
    """
    Get the current progress/status of a background download task.
    """
    progress = container.downloader.get_download_progress(task_id)
    if progress.get("status") == "not_found":
         raise HTTPException(status_code=404, detail="Task not found")
    
    # If completed, we should ideally trigger a health check to update DB
    if progress.get("status") == "completed":
        container.health_monitor.verify_all_models()
        
    return APIResponse(data=progress, message="Task status retrieved")

@router.get("/tasks/{task_id}/stream")
async def stream_download_status(task_id: str, container: AIModelsContainer = Depends(get_container)):
    """
    Stream the download progress updates via Server-Sent Events (SSE).
    """
    # 1. Verify task exists
    progress = container.downloader.get_download_progress(task_id)
    if progress.get("status") == "not_found":
         raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        # Subscribe to the event bus for this task
        q = container.downloader.event_bus.subscribe(task_id)
        logger.info(f"SSE: Client subscribed to task {task_id}")
        
        try:
            # Send initial state immediately
            initial_data = container.downloader.get_download_progress(task_id)
            yield f"data: {json.dumps(initial_data)}\n\n"

            while True:
                try:
                    # Non-blocking wait for an event from the bus
                    # We run the blocking Queue.get in a thread pool to avoid blocking the event loop
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=15.0)
                    )
                    
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # If this is a terminal state, the stream can close
                    if event.get("status") in ["completed", "failed", "canceled"]:
                        logger.info(f"SSE: Task {task_id} reached terminal state {event.get('status')}")
                        break
                except queue.Empty:
                    # Periodic heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                except Exception as e:
                    logger.error(f"SSE error for task {task_id}: {e}")
                    break
        finally:
            # Always unsubscribe to prevent memory leaks
            container.downloader.event_bus.unsubscribe(task_id, q)
            logger.info(f"SSE: Client unsubscribed from task {task_id}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/sync", response_model=APIResponse[Dict[str, Any]])
async def sync_registry(container: AIModelsContainer = Depends(get_container)):
    """
    Sync models from YAML registry files to the database.
    """
    try:
        container.registry_sync.sync()
        container.health_monitor.verify_all_models()
        return APIResponse(data={"status": "success"}, message="Registry synchronized and health verified")
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/pause", response_model=APIResponse[Dict[str, Any]])
async def pause_download(task_id: str, container: AIModelsContainer = Depends(get_container)):
    success = container.downloader.pause_download(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to pause download or task not running")
    return APIResponse(data={"status": "paused"}, message="Download pause requested")

@router.post("/tasks/{task_id}/resume", response_model=APIResponse[Dict[str, Any]])
async def resume_download(task_id: str, container: AIModelsContainer = Depends(get_container)):
    success = container.downloader.resume_download(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume download")
    return APIResponse(data={"status": "resumed"}, message="Download resume requested")

@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[Dict[str, Any]])
async def cancel_download(task_id: str, container: AIModelsContainer = Depends(get_container)):
    success = container.downloader.cancel_download(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel download")
    return APIResponse(data={"status": "canceled"}, message="Download cancellation requested")

@router.delete("/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_model(model_id: str, container: AIModelsContainer = Depends(get_container)):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    
    success = container.downloader.delete_local_model(model)
    if success:
        # Update health/status in registry
        container.health_monitor.verify_all_models()
        return APIResponse(data={"status": "deleted"}, message=f"Model {model.name} deleted successfully")
    else:
        raise HTTPException(status_code=500, detail="Failed to delete local model files")

@router.post("/validate", response_model=APIResponse[Dict[str, Any]])
async def validate_hf_model(payload: Dict[str, str], container: AIModelsContainer = Depends(get_container)):
    repo_id = payload.get("repo_id")
    if not repo_id:
        raise HTTPException(status_code=400, detail="repo_id is required")
    
    result = container.hf_validator.validate_repo(repo_id)
    return APIResponse(data=result, message="Validation completed")

@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def register_new_model(model_data: Dict[str, Any], container: AIModelsContainer = Depends(get_container)):
    try:
        # Create ModelEntity from dict
        # Ensure we have required fields
        if "id" not in model_data or "name" not in model_data:
             raise HTTPException(status_code=400, detail="id and name are required")
             
        model = ModelEntity(**model_data)
        container.registry_service.register_model(model)
        
        # Export to registry_user.yaml to persist
        user_reg_path = os.path.join(container.registry_dir, "registry_user.yaml")
        # We temporarily change the exporter's path or create a new one
        from common_lib.modules.ai_models.registry.exporter import RegistryExporter
        # We only want to export user models? For now export all to a safe place
        exporter = RegistryExporter(container.registry_service, user_reg_path)
        exporter.export_to_yaml()
        
        return APIResponse(data=model.model_dump(), message=f"Model {model.name} registered successfully")
    except Exception as e:
        logger.error(f"Failed to register model: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.patch("/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def update_model_metadata(model_id: str, updates: Dict[str, Any], container: AIModelsContainer = Depends(get_container)):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    try:
        # Update fields
        model_dict = model.model_dump()
        model_dict.update(updates)
        updated_model = ModelEntity(**model_dict)
        
        container.registry_service.register_model(updated_model) # register_model handles overwrites
        
        # Sync to YAML
        user_reg_path = os.path.join(container.registry_dir, "registry_user.yaml")
        from common_lib.modules.ai_models.registry.exporter import RegistryExporter
        exporter = RegistryExporter(container.registry_service, user_reg_path)
        exporter.export_to_yaml()
        
        return APIResponse(data=updated_model.model_dump(), message="Model metadata updated")
    except Exception as e:
        logger.error(f"Failed to update model: {e}")
        raise HTTPException(status_code=400, detail=str(e))

