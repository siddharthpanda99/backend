import os
import asyncio
import json
import queue
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from app.modules.common.types.index import APIResponse
from common_lib.modules.ai_models.container import AIModelsContainer
from common_lib.modules.ai_models.domain.entities import ModelEntity
from common_lib.modules.ai_models.registry.hf_service import (
    list_repo_files,
    validate_repo,
)
from common_lib.modules.ai_models.registry.file_scanner import scan_directory

logger = logging.getLogger(__name__)

router = APIRouter()


def get_container():
    return AIModelsContainer()


@router.get("/", response_model=APIResponse[List[Dict[str, Any]]])
async def list_models(container: AIModelsContainer = Depends(get_container)):
    try:
        container.health_monitor.verify_all_models()
        models = container.registry_service.list_models()
        result = []
        for model in models:
            m_dict = model.model_dump()
            active_task = container.downloader.get_download_progress(model.id)
            if active_task.get("status") != "not_found":
                m_dict["download_task"] = active_task
            result.append(m_dict)
        return APIResponse(data=result, message="Models retrieved successfully")
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        try:
            container.session.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def get_model(
    model_id: str, container: AIModelsContainer = Depends(get_container)
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    return APIResponse(data=model.model_dump(), message="Model details retrieved")


@router.get("/{model_id}/files", response_model=APIResponse[List[Dict[str, Any]]])
async def list_model_files(
    model_id: str, container: AIModelsContainer = Depends(get_container)
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    if not model.repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model.name}' is not hosted on HuggingFace.",
        )
    try:
        files = list_repo_files(model.repo_id)
        return APIResponse(
            data=files, message=f"Found {len(files)} files in repository"
        )
    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        logger.error(f"Failed to list files for {model_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{model_id}/download-file", response_model=APIResponse[Dict[str, Any]])
async def download_specific_file(
    model_id: str,
    file_path: str,
    force: bool = False,
    container: AIModelsContainer = Depends(get_container),
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    if not model.repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model.name}' is not hosted on HuggingFace.",
        )
    try:
        task_id = container.downloader.download_model_file(
            model, file_path, force=force
        )
        return APIResponse(
            data={"task_id": task_id, "status": "started", "file": file_path},
            message=f"Download started for {file_path}",
        )
    except Exception as e:
        logger.error(f"Failed to start file download for {model_id}/{file_path}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{model_id}/download", response_model=APIResponse[Dict[str, Any]])
async def download_model(
    model_id: str,
    force: bool = False,
    container: AIModelsContainer = Depends(get_container),
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    if not model.repo_id and not getattr(model, "download_url", None):
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model.name}' is a cloud-hosted API model and cannot be downloaded locally.",
        )
    try:
        task_id = container.downloader.download_model(model, force=force)
        return APIResponse(
            data={"task_id": task_id, "status": "started"},
            message=f"Download started for {model.name}",
        )
    except Exception as e:
        logger.error(f"Failed to start download for {model.id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{model_id}/download-files", response_model=APIResponse[Dict[str, Any]])
async def download_model_files(
    model_id: str,
    payload: Dict[str, Any],
    force: bool = False,
    container: AIModelsContainer = Depends(get_container),
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    if not model.repo_id:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model.name}' is not hosted on HuggingFace.",
        )
    file_paths = payload.get("file_paths", [])
    if not file_paths:
        raise HTTPException(status_code=400, detail="file_paths list is required")
    try:
        task_id = container.downloader.download_model_files(
            model, file_paths, force=force
        )
        return APIResponse(
            data={
                "task_id": task_id,
                "status": "started",
                "file_count": len(file_paths),
            },
            message=f"Download started for {len(file_paths)} file(s)",
        )
    except Exception as e:
        logger.error(f"Failed to start multi-file download for {model_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/stream")
async def stream_all_downloads(container: AIModelsContainer = Depends(get_container)):
    async def event_generator():
        q = container.downloader.event_bus.subscribe("__global__")
        try:
            yield ": heartbeat\n\n"
            while True:
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=15.0)
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
                except Exception as e:
                    logger.error(f"SSE global stream error: {e}")
                    break
        finally:
            container.downloader.event_bus.unsubscribe("__global__", q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/tasks/{task_id}", response_model=APIResponse[Dict[str, Any]])
async def get_download_status(
    task_id: str, container: AIModelsContainer = Depends(get_container)
):
    progress = container.downloader.get_download_progress(task_id)
    if progress.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    if progress.get("status") == "completed":
        container.health_monitor.verify_all_models()
    return APIResponse(data=progress, message="Task status retrieved")


@router.get("/tasks/{task_id}/stream")
async def stream_download_status(
    task_id: str, container: AIModelsContainer = Depends(get_container)
):
    progress = container.downloader.get_download_progress(task_id)
    if progress.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Task not found")

    async def event_generator():
        q = container.downloader.event_bus.subscribe(task_id)
        try:
            initial_data = container.downloader.get_download_progress(task_id)
            yield f"data: {json.dumps(initial_data)}\n\n"
            while True:
                try:
                    event = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: q.get(timeout=15.0)
                    )
                    yield f"data: {json.dumps(event)}\n\n"
                    if event.get("status") in ["completed", "failed", "canceled"]:
                        break
                except queue.Empty:
                    yield ": heartbeat\n\n"
                except Exception as e:
                    logger.error(f"SSE error for task {task_id}: {e}")
                    break
        finally:
            container.downloader.event_bus.unsubscribe(task_id, q)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/sync", response_model=APIResponse[Dict[str, Any]])
async def sync_registry(
    force_sync: bool = False,
    force_reindex: bool = False,
    container: AIModelsContainer = Depends(get_container),
):
    try:
        sync_results = container.registry_sync.sync(force=force_sync)
        if force_reindex:
            container.health_monitor.verify_all_models()
        return APIResponse(
            data=sync_results,
            message=f"Registry synchronized ({sync_results['total']} models) and health verified",
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/pause", response_model=APIResponse[Dict[str, Any]])
async def pause_download(
    task_id: str, container: AIModelsContainer = Depends(get_container)
):
    success = container.downloader.pause_download(task_id)
    if not success:
        raise HTTPException(
            status_code=400, detail="Failed to pause download or task not running"
        )
    return APIResponse(data={"status": "paused"}, message="Download pause requested")


@router.post("/tasks/{task_id}/resume", response_model=APIResponse[Dict[str, Any]])
async def resume_download(
    task_id: str, container: AIModelsContainer = Depends(get_container)
):
    success = container.downloader.resume_download(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to resume download")
    return APIResponse(data={"status": "resumed"}, message="Download resume requested")


@router.post("/tasks/{task_id}/cancel", response_model=APIResponse[Dict[str, Any]])
async def cancel_download(
    task_id: str, container: AIModelsContainer = Depends(get_container)
):
    success = container.downloader.cancel_download(task_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel download")
    return APIResponse(
        data={"status": "canceled"}, message="Download cancellation requested"
    )


@router.delete("/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def delete_model(
    model_id: str,
    permanent: bool = False,
    container: AIModelsContainer = Depends(get_container),
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
    success = container.downloader.delete_local_model(model, permanent=permanent)
    if success:
        container.health_monitor.verify_all_models()
        return APIResponse(
            data={"status": "deleted", "permanent": permanent},
            message=f"Model {model.name} deleted successfully ({'Permanent' if permanent else 'Cache cleared'})",
        )
    else:
        raise HTTPException(
            status_code=500, detail="Failed to delete local model files"
        )


@router.post("/validate", response_model=APIResponse[Dict[str, Any]])
async def validate_hf_model(
    payload: Dict[str, str], container: AIModelsContainer = Depends(get_container)
):
    repo_id = payload.get("repo_id")
    if not repo_id:
        raise HTTPException(status_code=400, detail="repo_id is required")
    result = validate_repo(repo_id)
    return APIResponse(data=result, message="Validation completed")


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def register_new_model(
    model_data: Dict[str, Any], container: AIModelsContainer = Depends(get_container)
):
    try:
        if "id" not in model_data or "name" not in model_data:
            raise HTTPException(status_code=400, detail="id and name are required")
        model = ModelEntity(**model_data)
        container.registry_service.register_model(model)
        user_reg_path = os.path.join(container.registry_dir, "registry_user.yaml")
        from common_lib.modules.ai_models.registry.exporter import RegistryExporter

        exporter = RegistryExporter(container.registry_service, user_reg_path)
        exporter.export_to_yaml()
        return APIResponse(
            data=model.model_dump(),
            message=f"Model {model.name} registered successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to register model: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{model_id}", response_model=APIResponse[Dict[str, Any]])
async def update_model_metadata(
    model_id: str,
    updates: Dict[str, Any],
    container: AIModelsContainer = Depends(get_container),
):
    model = container.registry_service.get_model(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    try:
        model_dict = model.model_dump()
        model_dict.update(updates)
        updated_model = ModelEntity(**model_dict)
        container.registry_service.register_model(updated_model)
        user_reg_path = os.path.join(container.registry_dir, "registry_user.yaml")
        from common_lib.modules.ai_models.registry.exporter import RegistryExporter

        exporter = RegistryExporter(container.registry_service, user_reg_path)
        exporter.export_to_yaml()
        return APIResponse(
            data=updated_model.model_dump(), message="Model metadata updated"
        )
    except Exception as e:
        logger.error(f"Failed to update model: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scan-directory", response_model=APIResponse[List[Dict[str, Any]]])
async def scan_directory_endpoint(path: str = Query(...), extension: str = Query(None)):
    try:
        files = scan_directory(path, extension=extension)
        return APIResponse(data=files, message=f"Found {len(files)} files")
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NotADirectoryError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to scan directory {path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
