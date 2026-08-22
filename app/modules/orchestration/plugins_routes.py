"""Plugin System API — List, inspect, and manage loaded plugins.

Endpoints:
    GET  /api/v1/plugins                — List all loaded plugins
    GET  /api/v1/plugins/{plugin_id}    — Get details for one plugin
    GET  /api/v1/plugins/services       — List all registered services
    GET  /api/v1/plugins/stats          — Plugin system statistics
    POST /api/v1/plugins/{plugin_id}/reload — Hot-reload a plugin
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_ctx():
    """Get the global PluginContext from app.state or fallback."""
    try:
        from common_lib.modules.orchestration.plugin import get_context
        return get_context()
    except Exception:
        return None


def _get_loader():
    """Get the PluginLoader from app.state."""
    try:
        from starlette.requests import Request
        # This won't work outside a request — use global fallback
        pass
    except Exception:
        pass
    return None


# =========================================================================
# Schemas
# =========================================================================

class PluginInfo(BaseModel):
    id: str
    plugin_path: str
    inject: List[str] = []
    provides: List[str] = []
    config: Dict[str, Any] = {}
    services_registered: List[str] = []
    enabled: bool = True
    priority: int = 100


class PluginDetail(BaseModel):
    id: str
    plugin_path: str
    inject: List[str] = []
    provides: List[str] = []
    config: Dict[str, Any] = {}
    services_registered: List[str] = []
    disposers_count: int = 0
    enabled: bool = True
    priority: int = 100
    class_name: str = ""
    module_name: str = ""


class ServiceInfo(BaseModel):
    key: str
    type: str
    plugin_id: Optional[str] = None


class PluginStats(BaseModel):
    total_plugins: int
    total_services: int
    loaded_plugins: List[str]
    service_keys: List[str]


class SignatureStatus(BaseModel):
    plugin_id: str
    status: str  # "signed" | "unsigned" | "tampered" | "error"
    files_checked: int = 0
    tampered_files: List[str] = []
    added_files: List[str] = []
    removed_files: List[str] = []


# =========================================================================
# Endpoints
# =========================================================================

@router.get("")
async def list_plugins():
    """List all loaded plugins with their metadata."""
    ctx = _get_ctx()
    if ctx is None:
        return {"plugins": [], "total": 0, "error": "PluginContext not initialized"}

    plugins = []
    # Access the loader's internal registry if available
    try:
        from common_lib.modules.orchestration.plugin.loader import PluginLoader
        # Try to get loader from global state
        import common_lib.modules.orchestration.plugin as _pkg
        loader = getattr(_pkg, '_global_loader', None)
    except Exception:
        loader = None

    # Build plugin list from context services
    services = ctx.keys()
    for service_key in services:
        service = ctx.get(service_key)
        plugins.append({
            "id": service_key,
            "type": type(service).__name__ if service else "unknown",
            "module": type(service).__module__ if service else "",
            "doc": (type(service).__doc__ or "")[:120] if service else "",
        })

    return {
        "plugins": plugins,
        "total": len(plugins),
        "context_name": ctx.name,
    }


@router.get("/stats")
async def plugin_stats():
    """Get plugin system statistics."""
    ctx = _get_ctx()
    if ctx is None:
        return {"total_plugins": 0, "total_services": 0, "error": "Not initialized"}

    services = ctx.keys()
    return {
        "total_plugins": len(services),
        "total_services": len(services),
        "loaded_plugins": services,
        "service_keys": services,
        "context_name": ctx.name,
    }


@router.get("/services")
async def list_services():
    """List all registered services with their types."""
    ctx = _get_ctx()
    if ctx is None:
        return {"services": [], "total": 0}

    services = []
    for key in ctx.keys():
        service = ctx.get(key)
        services.append({
            "key": key,
            "type": type(service).__name__ if service else "unknown",
            "module": type(service).__module__ if service else "",
            "doc": (type(service).__doc__ or "")[:200] if service else "",
        })

    return {"services": services, "total": len(services)}


@router.get("/{plugin_id}")
async def get_plugin(plugin_id: str):
    """Get details for a specific plugin/service."""
    ctx = _get_ctx()
    if ctx is None:
        raise HTTPException(status_code=503, detail="PluginContext not initialized")

    if not ctx.has(plugin_id):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    service = ctx.get(plugin_id)
    return {
        "id": plugin_id,
        "type": type(service).__name__ if service else "unknown",
        "module": type(service).__module__ if service else "",
        "doc": (type(service).__doc__ or "")[:500] if service else "",
        "methods": [
            m for m in dir(service)
            if not m.startswith("_") and callable(getattr(service, m, None))
        ] if service else [],
    }


@router.post("/{plugin_id}/reload")
async def reload_plugin(plugin_id: str):
    """Hot-reload a plugin (unload then reload with same config)."""
    ctx = _get_ctx()
    if ctx is None:
        raise HTTPException(status_code=503, detail="PluginContext not initialized")

    try:
        import common_lib.modules.orchestration.plugin as _pkg
        loader = getattr(_pkg, '_global_loader', None)
        if loader is None:
            raise HTTPException(
                status_code=503,
                detail="PluginLoader not available — cannot hot-reload"
            )

        if plugin_id not in loader._plugins:
            raise HTTPException(
                status_code=404,
                detail=f"Plugin '{plugin_id}' not found in loader registry"
            )

        loader.reload_plugin(plugin_id)
        return {"status": "reloaded", "plugin_id": plugin_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reload failed: {e}")


@router.get("/signatures/status")
async def signature_status_all():
    """Get signature status for all loaded plugins."""
    ctx = _get_ctx()
    if ctx is None:
        return {"signatures": [], "total": 0}

    try:
        from common_lib.modules.orchestration.plugin.loader import PluginLoader
        import common_lib.modules.orchestration.plugin as _pkg
        loader = getattr(_pkg, '_global_loader', None)
    except Exception:
        loader = None

    results = []
    for key in ctx.keys():
        # Default: unsigned
        sig = {"plugin_id": key, "status": "unsigned", "files_checked": 0}

        # If we have a loader with signing key, try to verify
        if loader and loader._signing_key:
            try:
                from common_lib.modules.orchestration.plugin.code_signing import PluginVerifier
                verifier = PluginVerifier(master_key=loader._signing_key)

                # Try to find plugin directory
                defn = loader._definitions.get(key)
                if defn:
                    resolved_dir = loader._resolve_plugin_dir(defn.plugin_path)
                    if resolved_dir and verifier.has_manifest(resolved_dir):
                        result = verifier.verify_plugin(resolved_dir)
                        sig = {
                            "plugin_id": key,
                            "status": "valid" if result.valid else "tampered",
                            "files_checked": len(result.tampered_files) + len(result.added_files) + len(result.removed_files),
                            "tampered_files": result.tampered_files,
                            "added_files": result.added_files,
                            "removed_files": result.removed_files,
                        }
            except Exception as e:
                sig = {"plugin_id": key, "status": "error", "error": str(e)}

        results.append(sig)

    return {"signatures": results, "total": len(results)}


@router.get("/signatures/{plugin_id}")
async def signature_status_one(plugin_id: str):
    """Get signature status for a specific plugin."""
    ctx = _get_ctx()
    if ctx is None:
        raise HTTPException(status_code=503, detail="PluginContext not initialized")

    if not ctx.has(plugin_id):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")

    try:
        import common_lib.modules.orchestration.plugin as _pkg
        loader = getattr(_pkg, '_global_loader', None)

        if loader and loader._signing_key:
            from common_lib.modules.orchestration.plugin.code_signing import PluginVerifier
            verifier = PluginVerifier(master_key=loader._signing_key)

            defn = loader._definitions.get(plugin_id)
            if defn:
                resolved_dir = loader._resolve_plugin_dir(defn.plugin_path)
                if resolved_dir and verifier.has_manifest(resolved_dir):
                    result = verifier.verify_plugin(resolved_dir)
                    return {
                        "plugin_id": plugin_id,
                        "status": "valid" if result.valid else "tampered",
                        "files_checked": len(result.tampered_files) + len(result.added_files) + len(result.removed_files),
                        "tampered_files": result.tampered_files,
                        "added_files": result.added_files,
                        "removed_files": result.removed_files,
                    }
    except Exception as e:
        return {"plugin_id": plugin_id, "status": "error", "error": str(e)}

    return {"plugin_id": plugin_id, "status": "unsigned"}
