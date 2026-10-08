"""Runtime Health Router — GET /runtime/health

Thin FastAPI router for Level 1/2/3 health checks.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Runtime — Health"])


# ──────────────────────────────────────────────────────────────────
# Service Accessor
# ──────────────────────────────────────────────────────────────────

def _get_runtime_service():
    """Lazy import of RuntimeService."""
    from common_lib.modules.runtime.service import get_runtime_service
    return get_runtime_service()


def _get_lifecycle_manager():
    """Get the lifecycle manager."""
    from common_lib.modules.runtime.lifecycle.manager import LifecycleManager, LifecycleManagerConfig
    return LifecycleManager(LifecycleManagerConfig())


# ──────────────────────────────────────────────────────────────────
# Route Handlers
# ──────────────────────────────────────────────────────────────────

@router.get("", summary="Level 1 Health Check (Liveness)")
async def health_liveness() -> dict[str, Any]:
    """Level 1 health check - basic liveness probe.

    Returns 200 OK if the runtime module is responsive.
    Does not check dependencies.
    """
    return {
        "status": "healthy",
        "level": 1,
        "check": "liveness",
        "timestamp": time.time(),
        "message": "Runtime module is responsive",
    }


@router.get("/ready", summary="Level 2 Health Check (Readiness)")
async def health_readiness() -> dict[str, Any]:
    """Level 2 health check - readiness probe.

    Checks:
    - Hardware discovery works
    - Model registry accessible
    - Runtime registry accessible
    - At least one runtime available
    """
    try:
        service = _get_runtime_service()

        checks = {}
        overall_healthy = True

        # Check hardware discovery
        try:
            hardware = service.discover_hardware()
            checks["hardware_discovery"] = {
                "status": "pass",
                "device_count": len(hardware.devices) if hasattr(hardware, 'devices') else 0,
            }
        except Exception as e:
            checks["hardware_discovery"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        # Check model registry
        try:
            models = service.list_models()
            checks["model_registry"] = {
                "status": "pass",
                "model_count": len(models),
            }
        except Exception as e:
            checks["model_registry"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        # Check runtime registry
        try:
            runtimes = service.list_runtimes()
            checks["runtime_registry"] = {
                "status": "pass" if runtimes else "warn",
                "runtime_count": len(runtimes),
            }
            if not runtimes:
                overall_healthy = False
        except Exception as e:
            checks["runtime_registry"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        # Check backend registry
        try:
            backends = service.list_backends()
            checks["backend_registry"] = {
                "status": "pass" if backends else "warn",
                "backend_count": len(backends),
            }
        except Exception as e:
            checks["backend_registry"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "level": 2,
            "check": "readiness",
            "timestamp": time.time(),
            "checks": checks,
        }

    except Exception as exc:
        logger.error("health_readiness failed: %s", exc, exc_info=True)
        return {
            "status": "unhealthy",
            "level": 2,
            "check": "readiness",
            "timestamp": time.time(),
            "error": str(exc),
        }


@router.get("/live", summary="Level 3 Health Check (Full)")
async def health_full(
    check_models: bool = Query(default=True, description="Verify model health"),
    check_devices: bool = Query(default=True, description="Check device health"),
    check_runtimes: bool = Query(default=True, description="Test runtime availability"),
) -> dict[str, Any]:
    """Level 3 health check - comprehensive health check.

    Performs deep checks:
    - All Level 2 checks
    - Model verification (if check_models)
    - Device health checks (if check_devices)
    - Runtime availability tests (if check_runtimes)
    - Lifecycle manager state
    """
    start_time = time.time()
    try:
        service = _get_runtime_service()
        lifecycle = _get_lifecycle_manager()

        checks = {}
        overall_healthy = True
        warnings = []

        # Hardware
        try:
            hardware = service.discover_hardware()
            checks["hardware"] = {
                "status": "pass",
                "device_count": len(hardware.devices) if hasattr(hardware, 'devices') else 0,
                "total_vram_gb": service.get_total_vram_gb(),
                "free_vram_gb": service.get_free_vram_gb(),
            }
        except Exception as e:
            checks["hardware"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        # Model registry
        try:
            models = service.list_models()
            checks["model_registry"] = {
                "status": "pass",
                "model_count": len(models),
            }
        except Exception as e:
            checks["model_registry"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        # Model health verification
        if check_models:
            try:
                verified_models = service.verify_all_models()
                local_count = sum(1 for m in verified_models if m.is_local)
                checks["model_health"] = {
                    "status": "pass",
                    "total_models": len(verified_models),
                    "local_models": local_count,
                    "remote_models": len(verified_models) - local_count,
                }
            except Exception as e:
                checks["model_health"] = {"status": "fail", "error": str(e)}
                overall_healthy = False

        # Runtime registry
        try:
            runtimes = service.list_runtimes()
            checks["runtime_registry"] = {
                "status": "pass" if runtimes else "warn",
                "runtime_count": len(runtimes),
                "runtimes": [r.name if hasattr(r, 'name') else str(r) for r in runtimes],
            }
            if not runtimes:
                warnings.append("No runtimes registered")
        except Exception as e:
            checks["runtime_registry"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        # Runtime availability test
        if check_runtimes and runtimes:
            runtime_results = []
            for rt in runtimes:
                rt_name = rt.name if hasattr(rt, 'name') else str(rt)
                try:
                    # Test if runtime can load a dummy model
                    from common_lib.modules.runtime.core.plan import ExecutionConfig
                    from common_lib.modules.runtime.core.model import Model
                    test_model = Model(id="test", name="test", provider="test")
                    config = ExecutionConfig()
                    can_load = rt.can_load_model(test_model, config) if hasattr(rt, 'can_load_model') else True
                    runtime_results.append({
                        "name": rt_name,
                        "status": "pass" if can_load else "warn",
                        "can_load_model": can_load,
                    })
                    if not can_load:
                        warnings.append(f"Runtime {rt_name} cannot load models")
                except Exception as e:
                    runtime_results.append({
                        "name": rt_name,
                        "status": "fail",
                        "error": str(e),
                    })
                    overall_healthy = False
            checks["runtime_availability"] = {
                "status": "pass" if all(r["status"] == "pass" for r in runtime_results) else "warn",
                "runtimes": runtime_results,
            }

        # Device health
        if check_devices:
            try:
                pool = _get_device_pool()
                device_health = pool.health_check()
                healthy_devices = sum(1 for d in device_health.values() if d.get("healthy", False))
                total_devices = len(device_health)
                checks["device_health"] = {
                    "status": "pass" if healthy_devices == total_devices else "warn",
                    "total": total_devices,
                    "healthy": healthy_devices,
                    "devices": device_health,
                }
                if healthy_devices < total_devices:
                    warnings.append(f"{total_devices - healthy_devices} devices unhealthy")
            except Exception as e:
                checks["device_health"] = {"status": "fail", "error": str(e)}
                overall_healthy = False

        # Lifecycle manager
        try:
            lifecycles = lifecycle.get_all_lifecycles()
            loaded_models = sum(1 for l in lifecycles if l.state.value in ["loaded", "warm", "executing", "idle"])
            failed_models = sum(1 for l in lifecycles if l.state.value == "failed")
            checks["lifecycle_manager"] = {
                "status": "pass" if failed_models == 0 else "warn",
                "total_tracked": len(lifecycles),
                "loaded": loaded_models,
                "failed": failed_models,
            }
            if failed_models > 0:
                warnings.append(f"{failed_models} models in failed state")
        except Exception as e:
            checks["lifecycle_manager"] = {"status": "fail", "error": str(e)}
            overall_healthy = False

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "level": 3,
            "check": "comprehensive",
            "timestamp": time.time(),
            "duration_ms": elapsed_ms,
            "checks": checks,
            "warnings": warnings,
        }

    except Exception as exc:
        logger.error("health_full failed: %s", exc, exc_info=True)
        return {
            "status": "unhealthy",
            "level": 3,
            "check": "comprehensive",
            "timestamp": time.time(),
            "duration_ms": (time.time() - start_time) * 1000,
            "error": str(exc),
        }


def _get_device_pool():
    """Get the device pool manager."""
    from common_lib.modules.runtime.scheduler.device_pool import DevicePool
    service = _get_runtime_service()
    hardware = service.discover_hardware()
    
    pool = DevicePool("default", "Default Device Pool")
    for device in hardware.devices:
        pool.add_device(device)
    
    return pool