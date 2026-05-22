from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List
from app.modules.common.types.index import APIResponse
from common_lib.modules.system.service import SystemService

router = APIRouter()


def get_system_service():
    return SystemService()


@router.get("/config/raw", response_model=APIResponse[str])
async def get_raw_config(service: SystemService = Depends(get_system_service)):
    """Retrieve the raw content of config.ini."""
    try:
        content = service.get_raw_config()
        return APIResponse(data=content, message="Raw config retrieved")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/raw", response_model=APIResponse[bool])
async def update_raw_config(
    content: str = Body(..., embed=True),
    service: SystemService = Depends(get_system_service),
):
    """Overwrite config.ini with raw text and sync to environment."""
    try:
        service.update_raw_config(content)
        return APIResponse(data=True, message="Config updated and synced successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/structured", response_model=APIResponse[Dict[str, Dict[str, str]]])
async def get_structured_config(service: SystemService = Depends(get_system_service)):
    """Retrieve config.ini as a structured object."""
    try:
        config = service.get_structured_config()
        return APIResponse(data=config, message="Structured config retrieved")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/structured", response_model=APIResponse[bool])
async def update_structured_config(
    data: Dict[str, Dict[str, str]] = Body(...),
    service: SystemService = Depends(get_system_service),
):
    """Update config.ini sections and sync to environment."""
    try:
        service.update_structured_config(data)
        return APIResponse(data=True, message="Config updated and synced successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", response_model=APIResponse[List[Dict[str, Any]]])
async def list_services(service: SystemService = Depends(get_system_service)):
    """List status of all infrastructure services."""
    try:
        services = service.get_services()
        return APIResponse(data=services, message="Services status retrieved")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/services/{service_id}/{action}", response_model=APIResponse[bool])
async def toggle_service(
    service_id: str, action: str, service: SystemService = Depends(get_system_service)
):
    """Start or stop an infrastructure service (up/down)."""
    if action not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Action must be 'up' or 'down'")

    try:
        success = service.toggle_service(service_id, action)
        if not success:
            raise HTTPException(
                status_code=500, detail=f"Failed to {action} service {service_id}"
            )
        return APIResponse(
            data=True, message=f"Service {service_id} {action} successful"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/host-stats", response_model=APIResponse[Dict[str, Any]])
async def get_host_stats(service: SystemService = Depends(get_system_service)):
    """Retrieve host telemetry (CPU, RAM, GPU VRAM usage)."""
    try:
        stats = service.get_host_stats()
        return APIResponse(data=stats, message="Host stats retrieved successfully")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

