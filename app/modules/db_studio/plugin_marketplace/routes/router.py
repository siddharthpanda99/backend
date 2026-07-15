"""Thin FastAPI router for Plugin Marketplace & Extension SDK (UDS Module 23)."""

from typing import List, Optional
from fastapi import APIRouter, HTTPException

from common_lib.modules.db_studio.plugin_marketplace import (
    PluginMarketplaceService,
    PluginCreate, PluginUpdate, PluginOut,
    PluginVersionCreate, PluginVersionOut,
    PluginPermissionOut,
    ReviewCreate, ReviewOut, PluginDependencyOut,
    MarketplaceCatalogUpdate, MarketplaceCatalogOut,
    InstallRequest, InstallOut,
    PluginMarketplaceDashboardOut,
)

router = APIRouter(prefix="/api/v1/plugins", tags=["Plugin Marketplace & Extension SDK"])
svc = PluginMarketplaceService()


# ── Plugins ────────────────────────────────────────────────────────────

@router.post("", response_model=PluginOut)
def create_plugin(req: PluginCreate):
    return svc.create_plugin(req)


@router.get("", response_model=List[PluginOut])
def list_plugins(
    plugin_type: Optional[str] = None,
    is_installed: Optional[bool] = None,
    is_enabled: Optional[bool] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_plugins(plugin_type, is_installed, is_enabled, workspace_id, limit)


@router.get("/{plugin_id}", response_model=PluginOut)
def get_plugin(plugin_id: str):
    p = svc.get_plugin(plugin_id)
    if not p:
        raise HTTPException(404, "Plugin not found")
    return p


@router.put("/{plugin_id}", response_model=PluginOut)
def update_plugin(plugin_id: str, req: PluginUpdate):
    p = svc.update_plugin(plugin_id, req)
    if not p:
        raise HTTPException(404, "Plugin not found")
    return p


@router.delete("/{plugin_id}")
def delete_plugin(plugin_id: str):
    if not svc.delete_plugin(plugin_id):
        raise HTTPException(404, "Plugin not found")
    return {"ok": True}


@router.post("/{plugin_id}/enable", response_model=PluginOut)
def enable_plugin(plugin_id: str):
    p = svc.enable_plugin(plugin_id)
    if not p:
        raise HTTPException(404, "Plugin not found")
    return p


@router.post("/{plugin_id}/disable", response_model=PluginOut)
def disable_plugin(plugin_id: str):
    p = svc.disable_plugin(plugin_id)
    if not p:
        raise HTTPException(404, "Plugin not found")
    return p


# ── Versions ───────────────────────────────────────────────────────────

@router.post("/{plugin_id}/versions", response_model=PluginVersionOut)
def create_version(plugin_id: str, req: PluginVersionCreate):
    v = svc.create_version(plugin_id, req)
    if not v:
        raise HTTPException(404, "Plugin not found")
    return v


@router.get("/{plugin_id}/versions", response_model=List[PluginVersionOut])
def list_versions(plugin_id: str, limit: int = 50):
    return svc.list_versions(plugin_id, limit)


# ── Permissions ────────────────────────────────────────────────────────

@router.post("/{plugin_id}/permissions", response_model=PluginPermissionOut)
def add_permission(plugin_id: str, permission: str, description: Optional[str] = None):
    return svc.add_permission(plugin_id, permission, description)


@router.get("/{plugin_id}/permissions", response_model=List[PluginPermissionOut])
def list_permissions(plugin_id: str):
    return svc.list_permissions(plugin_id)


# ── Reviews ────────────────────────────────────────────────────────────

@router.post("/{plugin_id}/reviews", response_model=ReviewOut)
def create_review(plugin_id: str, user_id: str, req: ReviewCreate):
    return svc.create_review(plugin_id, user_id, req)


@router.get("/{plugin_id}/reviews", response_model=List[ReviewOut])
def list_reviews(plugin_id: str, limit: int = 50):
    return svc.list_reviews(plugin_id, limit)


# ── Dependencies ───────────────────────────────────────────────────────

@router.post("/{plugin_id}/dependencies", response_model=PluginDependencyOut)
def add_dependency(plugin_id: str, dependency_plugin_id: str, version_spec: Optional[str] = None):
    return svc.add_dependency(plugin_id, dependency_plugin_id, version_spec)


@router.get("/{plugin_id}/dependencies", response_model=List[PluginDependencyOut])
def list_dependencies(plugin_id: str):
    return svc.list_dependencies(plugin_id)


# ── Marketplace ────────────────────────────────────────────────────────

@router.put("/marketplace/{plugin_id}", response_model=MarketplaceCatalogOut)
def update_marketplace(plugin_id: str, req: MarketplaceCatalogUpdate):
    c = svc.update_marketplace(plugin_id, req)
    if not c:
        raise HTTPException(404, "Marketplace listing not found")
    return c


@router.get("/marketplace", response_model=List[MarketplaceCatalogOut])
def list_marketplace(
    category: Optional[str] = None,
    is_featured: Optional[bool] = None,
    query: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_marketplace(category, is_featured, query, limit)


# ── Install / Uninstall ────────────────────────────────────────────────

@router.post("/{plugin_id}/install", response_model=InstallOut)
def install_plugin(plugin_id: str, req: Optional[InstallRequest] = None):
    inst = svc.install_plugin(plugin_id, req or InstallRequest())
    if not inst:
        raise HTTPException(404, "Plugin not found")
    return inst


@router.post("/{plugin_id}/uninstall")
def uninstall_plugin(plugin_id: str):
    if not svc.uninstall_plugin(plugin_id):
        raise HTTPException(404, "Plugin not found")
    return {"ok": True}


@router.get("/installations", response_model=List[InstallOut])
def list_installations(
    plugin_id: Optional[str] = None,
    workspace_id: Optional[str] = None,
    limit: int = 50,
):
    return svc.list_installations(plugin_id, workspace_id, limit)


# ── Dashboard ──────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=PluginMarketplaceDashboardOut)
def plugin_dashboard():
    return svc.get_dashboard()
