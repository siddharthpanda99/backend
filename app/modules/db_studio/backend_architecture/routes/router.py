"""Module 29 — Backend Architecture & Folder Structure routes (thin wrappers)."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.backend_architecture.service import ArchitectureService
from common_lib.modules.db_studio.backend_architecture.schemas import (
    SystemSettingCreate, SystemSettingOut,
    FeatureFlagCreate, FeatureFlagOut,
    AuditEventOut,
    BackgroundJobCreate, BackgroundJobOut,
    ModuleRegistryCreate, ModuleRegistryOut,
    ArchitectureDashboardOut,
)

router = APIRouter(tags=["UDS — Backend Architecture & Infrastructure"])
svc = ArchitectureService()


# ── System Settings ────────────────────────────────────────────

@router.post("/settings", response_model=SystemSettingOut)
def create_setting(body: SystemSettingCreate):
    return svc.create_setting(body)

@router.get("/settings/{key}", response_model=Optional[SystemSettingOut])
def get_setting(key: str):
    result = svc.get_setting(key)
    if not result:
        raise HTTPException(404, "Setting not found")
    return result

@router.get("/settings", response_model=Dict[str, Any])
def list_settings(category: Optional[str] = None, limit: int = 100):
    items, total = svc.list_settings(category=category, limit=limit)
    return {"total": total, "items": items}

@router.put("/settings/{key}", response_model=Optional[SystemSettingOut])
def update_setting(key: str, value: str):
    result = svc.update_setting(key, value)
    if not result:
        raise HTTPException(404, "Setting not found")
    return result

@router.delete("/settings/{key}")
def delete_setting(key: str):
    if not svc.delete_setting(key):
        raise HTTPException(404, "Setting not found")
    return {"ok": True}


# ── Feature Flags ──────────────────────────────────────────────

@router.post("/feature-flags", response_model=FeatureFlagOut)
def create_feature_flag(body: FeatureFlagCreate):
    return svc.create_feature_flag(body)

@router.get("/feature-flags", response_model=List[FeatureFlagOut])
def list_feature_flags(module: Optional[str] = None, is_enabled: Optional[bool] = None):
    return svc.list_feature_flags(module=module, is_enabled=is_enabled)

@router.put("/feature-flags/{flag_id}/toggle", response_model=Optional[FeatureFlagOut])
def toggle_feature_flag(flag_id: str, enabled: bool = True):
    result = svc.toggle_feature_flag(flag_id, enabled)
    if not result:
        raise HTTPException(404, "Feature flag not found")
    return result

@router.delete("/feature-flags/{flag_id}")
def delete_feature_flag(flag_id: str):
    if not svc.delete_feature_flag(flag_id):
        raise HTTPException(404, "Feature flag not found")
    return {"ok": True}


# ── Audit Events ───────────────────────────────────────────────

@router.post("/audit-events", response_model=AuditEventOut)
def record_audit_event(
    event_type: str, source: str,
    actor_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    severity: str = "info",
):
    return svc.record_audit_event(
        event_type, source, actor_id, resource_type, resource_id, severity,
    )

@router.get("/audit-events", response_model=List[AuditEventOut])
def list_audit_events(
    event_type: Optional[str] = None,
    source: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 100,
):
    return svc.list_audit_events(
        event_type=event_type, source=source, severity=severity, limit=limit,
    )


# ── Background Jobs ────────────────────────────────────────────

@router.post("/background-jobs", response_model=BackgroundJobOut)
def create_job(body: BackgroundJobCreate):
    return svc.create_job(body)

@router.get("/background-jobs", response_model=List[BackgroundJobOut])
def list_jobs(status: Optional[str] = None, job_type: Optional[str] = None, limit: int = 50):
    return svc.list_jobs(status=status, job_type=job_type, limit=limit)

@router.put("/background-jobs/{job_id}", response_model=Optional[BackgroundJobOut])
def update_job_status(
    job_id: str, status: str,
    progress: Optional[float] = None,
    error_message: Optional[str] = None,
):
    result = svc.update_job_status(job_id, status, progress, error_message)
    if not result:
        raise HTTPException(404, "Job not found")
    return result


# ── Module Registry ────────────────────────────────────────────

@router.post("/modules", response_model=ModuleRegistryOut)
def register_module(body: ModuleRegistryCreate):
    return svc.register_module(body)

@router.get("/modules", response_model=List[ModuleRegistryOut])
def list_modules(category: Optional[str] = None, status: Optional[str] = None):
    return svc.list_modules(category=category, status=status)

@router.put("/modules/{module_id}/load", response_model=Optional[ModuleRegistryOut])
def set_module_loaded(module_id: str, loaded: bool = True):
    result = svc.set_module_loaded(module_id, loaded)
    if not result:
        raise HTTPException(404, "Module not found")
    return result

@router.delete("/modules/{module_id}")
def delete_module(module_id: str):
    if not svc.delete_module(module_id):
        raise HTTPException(404, "Module not found")
    return {"ok": True}


# ── Dashboard ──────────────────────────────────────────────────

@router.get("/dashboard", response_model=ArchitectureDashboardOut)
def architecture_dashboard():
    return svc.get_dashboard()


# ── Seed ───────────────────────────────────────────────────────

@router.post("/seed")
def seed_architecture():
    count = svc.seed_defaults()
    return {"seeded": count}
