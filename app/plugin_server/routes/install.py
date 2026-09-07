"""Plugin Server routes — Install / Uninstall / Discover.

These endpoints are the 3rd-party install path:

  POST /install/zip       - Install from .zip file (multipart upload)
  POST /install/git       - Install from git URL
  POST /install/local      - Install from local directory
  DELETE /installed/{id}  - Uninstall
  POST /installed/{id}/reload - Re-discover and reload a single plugin
  POST /discover           - Force a full re-scan
  GET  /installed          - List installed plugins
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, UploadFile, File, status

logger = logging.getLogger(__name__)
router = APIRouter()


def _plugins_root(request: Request) -> Path:
    """Return the plugins root directory from app.state."""
    return Path(
        getattr(request.app.state, "components", {}).get(
            "plugins_root",
            os.path.join(os.path.dirname(__file__), "..", "plugins"),
        )
    )


# ── Install from .zip ────────────────────────────────────────────


@router.post("/install/zip")
async def install_zip(
    request: Request,
    plugin_id: str = Query(..., description="Unique plugin id"),
    zip_file: UploadFile = File(..., description="The plugin .zip file"),
    display_name: str | None = Query(None),
    category: str = Query("general"),
    author: str = Query("Anonymous"),
    overwrite: bool = Query(False),
) -> dict[str, Any]:
    """Install a 3rd-party plugin from an uploaded .zip.

    The .zip is saved to a temp location, extracted into
    ``plugins/<plugin_id>/cloned_or_extracted _repo/``, and a
    starter ``adapter.py`` and ``__init__.py`` are written.

    Returns:
        {"ok": true, "plugin_id": "...", "plugin_dir": "...", "source_type": "zip"}
    """
    from app.plugin_server.plugins_manager import install_plugin

    if not zip_file.filename or not zip_file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="File must be a .zip")

    plugins_root = _plugins_root(request)

    # Save upload to temp
    import tempfile

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".zip", dir=tempfile.gettempdir()
        ) as tmp:
            content = await zip_file.read()
            tmp.write(content)
            tmp_path = Path(tmp.name)

        result = install_plugin(
            plugin_id,
            source_zip=tmp_path,
            plugins_root=plugins_root,
            overwrite=overwrite,
            display_name=display_name,
            category=category,
            author=author,
        )
        return result.to_dict()
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


# ── Install from git ─────────────────────────────────────────────


@router.post("/install/git")
async def install_git(
    request: Request,
    plugin_id: str = Query(..., description="Unique plugin id"),
    git_url: str = Query(..., description="Git URL to clone"),
    branch: str = Query("main", description="Git branch"),
    display_name: str | None = Query(None),
    category: str = Query("general"),
    author: str = Query("Anonymous"),
    overwrite: bool = Query(False),
) -> dict[str, Any]:
    """Install a 3rd-party plugin by git-cloning a repository."""
    from app.plugin_server.plugins_manager import install_plugin

    plugins_root = _plugins_root(request)
    result = install_plugin(
        plugin_id,
        source_git=git_url,
        source_branch=branch,
        plugins_root=plugins_root,
        overwrite=overwrite,
        display_name=display_name,
        category=category,
        author=author,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.errors)
    return result.to_dict()


# ── Install from local directory ─────────────────────────────────


@router.post("/install/local")
async def install_local(
    request: Request,
    plugin_id: str = Query(..., description="Unique plugin id"),
    source_path: str = Query(..., description="Path to local directory"),
    display_name: str | None = Query(None),
    category: str = Query("general"),
    author: str = Query("Anonymous"),
    overwrite: bool = Query(False),
) -> dict[str, Any]:
    """Install a 3rd-party plugin by copying a local directory."""
    from app.plugin_server.plugins_manager import install_plugin

    plugins_root = _plugins_root(request)
    result = install_plugin(
        plugin_id,
        source_local_dir=source_path,
        plugins_root=plugins_root,
        overwrite=overwrite,
        display_name=display_name,
        category=category,
        author=author,
    )
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.errors)
    return result.to_dict()


# ── Uninstall ──────────────────────────────────────────────────


@router.delete("/installed/{plugin_id}")
async def uninstall(
    request: Request,
    plugin_id: str,
    purge: bool = Query(
        False,
        description=(
            "If true, permanently delete the plugin files. "
            "If false (default), HIDE the plugin (move to .hidden/, "
            "soft delete; reversible with /unhide)."
        ),
    ),
) -> dict[str, Any]:
    """Hide (default) or purge (purge=true) an installed plugin.

    Default: hides the plugin. The files are moved into
    <plugins_root>/.hidden/<plugin_id>/ and a marker file is
    written. The plugin is no longer listed by default but can
    be restored with POST /installed/{id}/unhide.

    Set ?purge=true to permanently delete the files.
    """
    from app.plugin_server.plugins_manager import uninstall_plugin
    from app.plugin_server.plugins_manager.hide import (
        hide_plugin,
        is_hidden,
    )

    plugins_root = _plugins_root(request)
    plugin_dir = plugins_root / plugin_id

    if purge:
        ok = uninstall_plugin(plugin_id, plugins_root=plugins_root)
        if not ok:
            raise HTTPException(
                status_code=404,
                detail=f"Plugin '{plugin_id}' is not installed",
            )
        return {
            "ok": True,
            "plugin_id": plugin_id,
            "action": "purged",
            "message": "Files permanently deleted",
        }

    # Default: hide (soft delete)
    if not plugin_dir.exists() or is_hidden(plugin_dir):
        hidden_path = plugins_root / ".hidden" / plugin_id
        if hidden_path.exists() and is_hidden(hidden_path):
            raise HTTPException(
                status_code=404,
                detail=f"Plugin '{plugin_id}' is already hidden",
            )
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{plugin_id}' is not installed",
        )

    ok = hide_plugin(plugin_dir)
    return {
        "ok": True,
        "plugin_id": plugin_id,
        "action": "hidden",
        "message": "Plugin hidden (files moved to .hidden/). "
        "Restore with POST /installed/{id}/unhide",
    }


@router.post("/installed/{plugin_id}/unhide")
async def unhide(
    request: Request,
    plugin_id: str,
) -> dict[str, Any]:
    """Restore a previously hidden plugin (un-soft-delete)."""
    from app.plugin_server.plugins_manager.hide import (
        unhide_plugin,
        is_hidden,
    )

    plugins_root = _plugins_root(request)
    hidden_dir = plugins_root / ".hidden" / plugin_id

    if not hidden_dir.exists() or not is_hidden(hidden_dir):
        raise HTTPException(
            status_code=404,
            detail=f"No hidden plugin named '{plugin_id}'",
        )

    ok = unhide_plugin(hidden_dir)
    if not ok:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Cannot unhide '{plugin_id}': a visible plugin "
                f"with the same name already exists"
            ),
        )
    return {
        "ok": True,
        "plugin_id": plugin_id,
        "action": "unhidden",
    }


# ── List installed plugins ─────────────────────────────────────


@router.get("/installed")
async def list_installed(
    request: Request,
    include_hidden: bool = Query(
        False,
        description="If true, include hidden (soft-deleted) plugins.",
    ),
) -> dict[str, Any]:
    """List installed plugins.

    By default, hidden plugins are filtered out. Set
    ?include_hidden=true to see them all.
    """
    from app.plugin_server.plugins_manager.hide import is_hidden

    plugins_root = _plugins_root(request)
    if not plugins_root.exists():
        return {"plugins": [], "plugins_root": str(plugins_root), "hidden_count": 0}

    plugins = []
    hidden_count = 0
    for entry in sorted(plugins_root.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name.startswith("_"):
            continue
        if is_hidden(entry):
            hidden_count += 1
            if not include_hidden:
                continue
        # Try to extract metadata
        info: dict[str, Any] = {
            "plugin_id": entry.name,
            "plugin_dir": str(entry),
            "hidden": is_hidden(entry),
            "has_adapter_py": (entry / "adapter.py").exists(),
            "has_init_py": (entry / "__init__.py").exists(),
            "has_cloned_dir": (entry / "cloned_or_extracted_repo").exists(),
        }
        # Try to read PLUGIN_ID and ADAPTER_CLASS
        try:
            import importlib.util
            import sys

            if str(plugins_root) not in sys.path:
                sys.path.insert(0, str(plugins_root))
            if entry.name in sys.modules:
                del sys.modules[entry.name]
            spec = importlib.util.spec_from_file_location(
                entry.name, entry / "__init__.py"
            )
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                info["plugin_id_declared"] = getattr(mod, "PLUGIN_ID", None)
                info["adapter_class"] = (
                    mod.ADAPTER_CLASS.__name__
                    if getattr(mod, "ADAPTER_CLASS", None)
                    else None
                )
        except Exception as e:
            info["error"] = str(e)
        plugins.append(info)

    return {
        "plugins": plugins,
        "plugins_root": str(plugins_root),
        "visible_count": len(plugins),
        "hidden_count": hidden_count,
    }


# ── Discover (force re-scan) ───────────────────────────────────


@router.post("/discover")
async def discover_now(request: Request) -> dict[str, Any]:
    """Force a full re-scan of the plugins/ directory and reload
    all discovered plugins into the engine.
    """
    from app.plugin_server.discovery import PluginDiscovery
    from common_lib.modules.plugins.schemas import PluginType

    plugins_root = _plugins_root(request)
    discovery = PluginDiscovery(plugins_root=plugins_root)
    result = discovery.scan()

    # Register newly discovered plugins with the engine
    components = getattr(request.app.state, "components", {})
    mgr = components.get("tool_manager")
    if mgr is not None:
        for d in result.plugins:
            try:
                if (
                    hasattr(d.plugin_instance, "metadata")
                    and d.plugin_instance.metadata
                ):
                    d.plugin_instance.metadata.plugin_type = PluginType.EXTERNAL
                mgr.engine.plugins[d.plugin_id] = d.plugin_instance
            except Exception as e:
                logger.exception(f"Failed to register {d.plugin_id}: {e}")

    return result.to_dict()


# ── Reload a single installed plugin ────────────────────────────


@router.post("/installed/{plugin_id}/reload")
async def reload_installed(request: Request, plugin_id: str) -> dict[str, Any]:
    """Re-discover and reload a single installed plugin.

    This re-imports the plugin's __init__.py, instantiates a
    fresh adapter, calls discover(), and swaps the engine's
    plugin instance for this id.
    """
    from app.plugin_server.discovery import PluginDiscovery
    from common_lib.modules.plugins.engine.safe_reload import SafeReloadError
    from common_lib.modules.plugins.schemas import PluginType

    plugins_root = _plugins_root(request)
    discovery = PluginDiscovery(plugins_root=plugins_root)
    d = discovery.load_one(plugin_id)
    if d is None:
        raise HTTPException(
            status_code=404, detail=f"Plugin '{plugin_id}' could not be loaded"
        )
    if not d.warm_up_ok:
        return {
            "success": False,
            "plugin_id": plugin_id,
            "warm_up_error": d.warm_up_error,
        }

    components = getattr(request.app.state, "components", {})
    mgr = components.get("tool_manager")
    if mgr is not None:
        try:
            if hasattr(d.plugin_instance, "metadata") and d.plugin_instance.metadata:
                d.plugin_instance.metadata.plugin_type = PluginType.EXTERNAL
            mgr.engine.plugins[d.plugin_id] = d.plugin_instance
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to swap plugin: {e}")
    return {
        "success": True,
        "plugin_id": plugin_id,
        "adapter_class": d.adapter_class_name,
    }


__all__ = [
    "router",
]
