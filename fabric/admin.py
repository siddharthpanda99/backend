"""Admin endpoints for the Nexus Runtime Execution Fabric.

Mounted under /admin/runtime in the standalone control plane and re-exported
by the Backend thin gateway (app/modules/runtime_fabric). All logic stays in
common_lib - Backend only re-hosts this router.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from fabric.discovery import discover_all_models
from fabric.jobs import job_store
from fabric.profiles import ProfileRegistry, RuntimeProfile
from fabric.scheduler import gpu_admission
from fabric.supervisor import supervisor

logger = logging.getLogger(__name__)

router = APIRouter(tags=["runtime-fabric-admin"])


def _profile_payload(p: RuntimeProfile) -> Dict[str, Any]:
    return {
        "profile_id": p.profile_id,
        "toolchain": p.toolchain,
        "environment": p.environment,
        "python": p.python,
        "adapter": p.adapter,
        "protocol": p.protocol,
        "startup_timeout_seconds": p.startup_timeout_seconds,
        "idle_timeout_seconds": p.idle_timeout_seconds,
        "max_workers": p.max_workers,
        "device": p.device,
        "capabilities": p.capabilities,
        "resource_class": p.resource_class,
        "vram_mb": p.vram_mb,
        "enabled": p.enabled,
        "state": p.state.value if hasattr(p.state, "value") else str(p.state),
        "working_directory": p.working_directory,
        "python_exists": Path(p.python).is_file(),
        "environment_exists": Path(p.environment).exists(),
        "working_directory_exists": Path(p.working_directory).exists(),
    }


@router.get("/profiles")
async def list_profiles() -> Dict[str, Any]:
    profiles = ProfileRegistry.get_all_profiles()
    return {"count": len(profiles), "profiles": [_profile_payload(p) for p in profiles]}


@router.get("/models")
async def list_models() -> Dict[str, Any]:
    """List all available models with their profile mappings and best configs."""
    from fabric.profiles import ProfileRegistry
    from fabric.discovery import discover_all_models

    # Ensure profiles are loaded
    ProfileRegistry._load_profiles()

    models = []
    model_map = ProfileRegistry.MODEL_PROFILE_MAP

    # Get all models from discovery
    discovered = discover_all_models()

    for model_data in discovered:
        model_id = model_data["model_id"]
        profile_id = model_map.get(model_id)
        profile = ProfileRegistry.get_profile(profile_id) if profile_id else None

        # Get best config from profile's backend config
        best_config = None
        if profile and profile.backend_config:
            for family, backend in profile.backend_config.items():
                best_configs = backend.get("best_configs", [])
                if best_configs:
                    best_config = best_configs[0]  # default config
                    break

        models.append(
            {
                "model_id": model_id,
                "name": model_data.get("name", model_id),
                "family": model_data.get("family", ""),
                "folder": model_data.get("folder", ""),
                "adapter_alias": model_data.get("adapter_alias", ""),
                "dit_path": model_data.get("dit_path", ""),
                "components": model_data.get("components", {}),
                "is_multi_part": model_data.get("is_multi_part", False),
                "default_steps": model_data.get("default_steps", 20),
                "default_cfg": model_data.get("default_cfg", 1.0),
                "vram_mb": model_data.get("vram_mb", 0),
                "profile_id": profile_id,
                "profile_name": profile.profile_id if profile else None,
                "best_config": best_config,
                "capabilities": model_data.get("features", ["txt2img"]),
                "default_steps": model_data.get("default_steps", 20),
                "default_cfg": model_data.get("default_cfg", 1.0),
                "vram_mb": model_data.get("vram_mb", 0),
                "supported_modes": model_data.get("modes", ["t2i"]),
            }
        )

    return {
        "count": len(models),
        "models": models,
    }


@router.get("/profiles")
async def list_profiles() -> Dict[str, Any]:
    profiles = ProfileRegistry.get_all_profiles()
    return {"count": len(profiles), "profiles": [_profile_payload(p) for p in profiles]}


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str) -> Dict[str, Any]:
    p = ProfileRegistry.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}")
    return _profile_payload(p)


@router.post("/profiles/{profile_id}/validate")
async def validate_profile(profile_id: str) -> Dict[str, Any]:
    p = ProfileRegistry.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}")
    checks = [
        {"check": "python_exists", "ok": Path(p.python).is_file(), "path": p.python},
        {"check": "environment_exists", "ok": Path(p.environment).exists(), "path": p.environment},
        {
            "check": "working_directory_exists",
            "ok": Path(p.working_directory).exists(),
            "path": p.working_directory,
        },
    ]
    all_ok = all(c["ok"] for c in checks)
    return {"profile_id": profile_id, "valid": all_ok, "checks": checks}


@router.get("/workers")
async def list_workers() -> Dict[str, Any]:
    workers = supervisor.get_all_worker_info()
    return {"count": len(workers), "workers": workers}


@router.get("/workers/{profile_id}")
async def get_worker(profile_id: str) -> Dict[str, Any]:
    info = supervisor.get_worker_info(profile_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"worker not running for profile: {profile_id}")
    return info


@router.post("/workers/{profile_id}/start")
async def start_worker(profile_id: str) -> Dict[str, Any]:
    p = ProfileRegistry.get_profile(profile_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"profile not found: {profile_id}")
    worker = await supervisor.acquire_worker(profile_id)
    if worker is None:
        raise HTTPException(
            status_code=503,
            detail=f"worker for profile '{profile_id}' failed to start - see control-plane logs",
        )
    await supervisor.release_worker(profile_id)
    return {"status": "started", "worker": supervisor.get_worker_info(profile_id)}


@router.post("/workers/{profile_id}/stop")
async def stop_worker(profile_id: str) -> Dict[str, Any]:
    stopped = await supervisor.stop_worker(profile_id)
    return {"status": "stopped" if stopped else "not_running", "profile_id": profile_id}


@router.post("/workers/{profile_id}/drain")
async def drain_worker(profile_id: str) -> Dict[str, Any]:
    # Graceful stop: terminate after current jobs finish. For now this stops
    # the worker; jobs running long-term should be drained via the job system.
    info = supervisor.get_worker_info(profile_id)
    stopped = await supervisor.stop_worker(profile_id)
    return {
        "status": "drained" if stopped else "not_running",
        "profile_id": profile_id,
        "worker": info,
    }


@router.get("/resources/gpu")
async def gpu_status() -> Dict[str, Any]:
    if shutil.which("nvidia-smi"):
        try:
            out = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if out.returncode == 0 and out.stdout.strip():
                name, total, used, free, util = [x.strip() for x in out.stdout.strip().split(",")]
                return {
                    "gpu_available": True,
                    "name": name,
                    "memory_total_mb": int(total),
                    "memory_used_mb": int(used),
                    "memory_free_mb": int(free),
                    "utilization_percent": float(util),
                    "source": "nvidia-smi",
                    "admission": gpu_admission.status(),
                }
        except Exception as e:
            logger.warning("nvidia-smi query failed: %s", e)
    return {"gpu_available": False, "source": "unavailable", "admission": gpu_admission.status()}


@router.get("/resources/queue")
async def queue_status() -> Dict[str, Any]:
    return {"jobs": job_store.stats()}


@router.get("/jobs")
async def list_jobs_admin(status: str | None = None, limit: int = 100) -> Dict[str, Any]:
    jobs = job_store.list(status=status, limit=limit)
    return {"count": len(jobs), "jobs": [j.to_dict() for j in jobs]}
