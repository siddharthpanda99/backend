"""Runtime Devices Router — GET /runtime/devices

Thin FastAPI router that delegates to common_lib.modules.runtime for
device pool status queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["Runtime — Devices"])


# ──────────────────────────────────────────────────────────────────
# Service Accessor
# ──────────────────────────────────────────────────────────────────

def _get_runtime_service():
    """Lazy import of RuntimeService."""
    from common_lib.modules.runtime.service import get_runtime_service
    return get_runtime_service()


def _get_device_pool():
    """Get the device pool manager."""
    # In a full implementation, this would be a singleton pool manager
    # For now, we create a pool from discovered hardware
    from common_lib.modules.runtime.scheduler.device_pool import DevicePool
    from common_lib.modules.runtime.core.device import Device, DeviceType, DeviceVendor, DeviceStatus
    
    service = _get_runtime_service()
    hardware = service.discover_hardware()
    
    pool = DevicePool("default", "Default Device Pool")
    for device in hardware.devices:
        pool.add_device(device)
    
    return pool


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.get("", summary="List All Devices")
async def list_devices(
    device_type: Optional[str] = Query(default=None, description="Filter by device type"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    available_only: bool = Query(default=False, description="Only available devices"),
) -> dict[str, Any]:
    """List all devices in the pool with optional filters."""
    try:
        pool = _get_device_pool()

        from common_lib.modules.runtime.core.device import DeviceType, DeviceStatus

        dt = DeviceType(device_type) if device_type else None
        st = DeviceStatus(status) if status else None

        devices = pool.get_devices(device_type=dt, status=st, available_only=available_only)

        return {
            "devices": [d.to_dict() for d in devices],
            "count": len(devices),
            "total_vram_gb": sum(d.total_memory_gb for d in devices if d.is_gpu()),
            "free_vram_gb": sum(d.free_memory_gb for d in devices if d.is_gpu()),
        }

    except Exception as exc:
        logger.error("list_devices failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pools", summary="List Device Pools")
async def list_device_pools() -> dict[str, Any]:
    """List all device pools."""
    try:
        # In a full implementation, we'd have multiple pools
        # For now, return the default pool
        pool = _get_device_pool()

        return {
            "pools": [pool.to_dict()],
            "count": 1,
        }

    except Exception as exc:
        logger.error("list_device_pools failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pools/{pool_id}", summary="Get Device Pool Details")
async def get_device_pool(pool_id: str) -> dict[str, Any]:
    """Get detailed information about a device pool."""
    try:
        pool = _get_device_pool()

        if pool_id != pool.pool_id:
            raise HTTPException(status_code=404, detail=f"Pool not found: {pool_id}")

        return pool.to_dict()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_device_pool failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/pools/{pool_id}/metrics", summary="Get Device Pool Metrics")
async def get_device_pool_metrics(pool_id: str) -> dict[str, Any]:
    """Get real-time metrics for a device pool."""
    try:
        pool = _get_device_pool()

        if pool_id != pool.pool_id:
            raise HTTPException(status_code=404, detail=f"Pool not found: {pool_id}")

        metrics = pool.get_metrics()

        return {
            "pool_id": pool_id,
            "metrics": {
                "total_devices": metrics.total_devices,
                "available_devices": metrics.available_devices,
                "busy_devices": metrics.busy_devices,
                "offline_devices": metrics.offline_devices,
                "error_devices": metrics.error_devices,
                "total_memory_gb": metrics.total_memory_gb,
                "available_memory_gb": metrics.available_memory_gb,
                "used_memory_gb": metrics.used_memory_gb,
                "active_allocations": metrics.active_allocations,
                "avg_utilization_percent": metrics.avg_utilization_percent,
                "peak_utilization_percent": metrics.peak_utilization_percent,
                "last_updated": metrics.last_updated.isoformat() if metrics.last_updated else None,
            },
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_device_pool_metrics failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{device_id}", summary="Get Device Details")
async def get_device(device_id: str) -> dict[str, Any]:
    """Get detailed information about a specific device."""
    try:
        pool = _get_device_pool()
        device = pool.get_device(device_id)

        if not device:
            raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

        return device.to_dict()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_device failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{device_id}/allocations", summary="Get Device Allocations")
async def get_device_allocations(device_id: str) -> dict[str, Any]:
    """Get all resource allocations for a device."""
    try:
        pool = _get_device_pool()
        device = pool.get_device(device_id)

        if not device:
            raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

        allocations = pool.get_allocations_for_device(device_id)

        return {
            "device_id": device_id,
            "allocations": [
                {
                    "allocation_id": a.allocation_id,
                    "model_id": a.model_id,
                    "instance_id": a.instance_id,
                    "memory_allocated_gb": a.memory_allocated_gb,
                    "compute_units_allocated": a.compute_units_allocated,
                    "active": a.active,
                    "started_at": a.started_at.isoformat(),
                    "released_at": a.released_at.isoformat() if a.released_at else None,
                    "metadata": a.metadata,
                }
                for a in allocations
            ],
            "count": len(allocations),
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("get_device_allocations failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/{device_id}/health", summary="Device Health Check")
async def device_health_check(device_id: str) -> dict[str, Any]:
    """Perform a health check on a specific device."""
    try:
        pool = _get_device_pool()
        device = pool.get_device(device_id)

        if not device:
            raise HTTPException(status_code=404, detail=f"Device not found: {device_id}")

        # Perform health check
        is_healthy = device.status != type(device).status.ERROR if hasattr(type(device).status, 'ERROR') else True
        
        health_results = pool.health_check()
        device_health = health_results.get(device_id, {})

        return {
            "device_id": device_id,
            "healthy": device_health.get("healthy", is_healthy),
            "status": device.status.value if hasattr(device.status, 'value') else str(device.status),
            "utilization_percent": device.utilization_percent,
            "temperature_c": device.temperature_c,
            "power_draw_w": device.power_draw_watts if hasattr(device, 'power_draw_watts') else device.power_draw_w,
            "memory_utilization_percent": device.memory_utilization_percent,
            "details": device_health,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("device_health_check failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))