"""Plugin Server — FastAPI application.

Run:
    uvicorn app.plugin_server.main:app --host 0.0.0.0 --port 8081

Or with hot-reload (dev only):
    uvicorn app.plugin_server.main:app --host 0.0.0.0 --port 8081 --reload

This is a STANDALONE process. It does NOT share Python state with
the main backend. The two communicate over HTTP only.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from contextlib import asynccontextmanager
from typing import Any

# Bootstrap: ensure common_lib src is on sys.path
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..")
)
_COMMON_LIB_SRC = os.path.join(
    _REPO_ROOT, "Backend Monorepo", "Python Libs", "common_lib", "src"
)
if _COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, _COMMON_LIB_SRC)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle.

    Startup:
      1. Initialize logging
      2. Load the 39 infrastructure plugins from platform.yml
      3. Discover the 266+ tool plugins
      4. Start the PluginWatcher (if PLUGIN_RELOAD_MODE != manual)
      5. Register signal handlers (SIGHUP = safe-reload, SIGTERM = shutdown)

    Shutdown:
      1. Stop the watcher
      2. Dispose all plugins (close DB pools, file handles, etc.)
      3. Flush logs
    """
    try:
        from common_lib.modules.observability import initialize_logging

        initialize_logging()
    except Exception as e:
        # Fall back to basic logging if observability module unavailable
        logging.basicConfig(
            level=os.environ.get("LOG_LEVEL", "INFO"),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
        logging.debug(f"initialize_logging unavailable: {e}")

    logger.info("=" * 60)
    logger.info("Plugin Server starting up")
    logger.info("=" * 60)

    started_at = time.time()
    components = await _startup_components(app)
    app.state.components = components
    app.state.started_at = started_at
    app.state.ready = True

    logger.info(
        f"Plugin Server ready: "
        f"{components.get('tool_plugins_loaded', 0)} tool plugins, "
        f"{components.get('infra_plugins_loaded', 0)} infra plugins, "
        f"{components.get('extensions_loaded', 0)} extensions"
    )

    yield  # ── service runs here ──

    # Shutdown
    logger.info("Plugin Server shutting down")
    app.state.ready = False
    await _shutdown_components(components)
    logger.info("Plugin Server stopped cleanly")


async def _startup_components(app: FastAPI) -> dict[str, Any]:
    """Load plugins and start the watcher. Returns a status dict."""
    components: dict[str, Any] = {}

    # 1. Tool plugins (BaseToolPlugin subclasses)
    try:
        from common_lib.modules.plugins.manager import get_plugin_manager

        mgr = get_plugin_manager()  # singleton, lazy-starts
        components["tool_manager"] = mgr
        components["tool_plugins_loaded"] = len(mgr.engine.list_plugins())
    except Exception as e:
        logger.exception(f"Failed to load tool plugins: {e}")
        components["tool_plugins_loaded"] = 0
        components["tool_error"] = str(e)

    # 2. Infrastructure plugins (PluginLoader from platform.yml)
    try:
        from common_lib.modules.orchestration.plugin import PluginContext, PluginLoader

        ctx = PluginContext(name="plugin-server")
        loader = PluginLoader(ctx)
        platform_yml = os.path.join(
            _COMMON_LIB_SRC, "common_lib", "configs", "plugins", "platform.yml"
        )
        if os.path.exists(platform_yml):
            loader.load_from_yaml(platform_yml)
        components["infra_ctx"] = ctx
        components["infra_loader"] = loader
        components["infra_plugins_loaded"] = len(loader._plugins)
    except Exception as e:
        logger.exception(f"Failed to load infrastructure plugins: {e}")
        components["infra_plugins_loaded"] = 0
        components["infra_error"] = str(e)

    # 3. Extensions (ComfyUI, git, pip)
    try:
        from common_lib.modules.extensions import get_extension_registry
        from common_lib.modules.extensions.models import ExtensionStatus

        reg = get_extension_registry()
        # Auto-discover ComfyUI custom nodes from Extras/
        await _auto_discover_comfyui(reg)
        active = reg.list(status=ExtensionStatus.ACTIVE)
        components["extensions_registry"] = reg
        components["extensions_loaded"] = len(active)
    except Exception as e:
        logger.exception(f"Failed to load extensions: {e}")
        components["extensions_loaded"] = 0
        components["extensions_error"] = str(e)

    # 4. Hot-reload watcher
    try:
        from common_lib.modules.plugins.engine.watcher import (
            PluginWatcher,
            WatcherConfig,
            get_plugin_watcher,
        )

        wcfg = WatcherConfig.from_env()
        watcher = get_plugin_watcher(config=wcfg)
        loop = asyncio.get_running_loop()
        watcher.start(loop)
        components["watcher"] = watcher
        components["watcher_mode"] = wcfg.mode
        if wcfg.mode == "manual":
            logger.info("PluginWatcher: MANUAL mode")
        else:
            logger.info(
                f"PluginWatcher: active (mode={wcfg.mode}, interval={wcfg.interval_sec}s)"
            )
    except Exception as e:
        logger.exception(f"Failed to start PluginWatcher: {e}")
        components["watcher_error"] = str(e)

    # 5. Signal handlers (Unix only; on Windows, signal.SIGHUP is missing)
    _register_signal_handlers()

    return components


async def _auto_discover_comfyui(reg) -> None:
    """Auto-discover ComfyUI custom nodes from Extras/ComfyUI/custom_nodes/."""
    comfyui_dir = os.path.join(_REPO_ROOT, "Extras", "ComfyUI", "custom_nodes")
    if not os.path.isdir(comfyui_dir):
        return
    # Best-effort: just log. The ExtensionRegistry does the actual
    # scanning; we just want to be explicit.
    try:
        reg.scan_dir_for_extensions(comfyui_dir)
    except Exception as e:
        logger.debug(f"ComfyUI scan failed: {e}")


def _register_signal_handlers() -> None:
    """SIGHUP = safe-reload, SIGTERM = graceful shutdown."""
    if sys.platform == "win32":
        return  # Unix-only

    def on_sighup(signum, frame):
        logger.info("Received SIGHUP — triggering safe-reload-all")
        try:
            from common_lib.modules.plugins.manager import get_plugin_manager

            get_plugin_manager().reload()
        except Exception as e:
            logger.exception(f"SIGHUP reload failed: {e}")

    def on_sigterm(signum, frame):
        logger.info("Received SIGTERM — initiating graceful shutdown")
        # The lifespan will handle the actual cleanup on the next
        # event loop iteration. Signal handler just sets a flag.
        try:
            import threading

            threading.Thread(target=lambda: sys.exit(0), daemon=True).start()
        except Exception:
            pass

    try:
        signal.signal(signal.SIGHUP, on_sighup)
        signal.signal(signal.SIGTERM, on_sigterm)
    except (AttributeError, ValueError):
        pass  # Not on main thread / not supported


async def _shutdown_components(components: dict[str, Any]) -> None:
    """Dispose all plugin systems cleanly."""
    # Stop watcher first
    if "watcher" in components:
        try:
            components["watcher"].stop()
        except Exception as e:
            logger.warning(f"Watcher stop failed: {e}")

    # Dispose tool plugins
    if "tool_manager" in components:
        try:
            mgr = components["tool_manager"]
            for plugin in mgr.engine.list_plugins():
                if hasattr(plugin, "dispose"):
                    try:
                        plugin.dispose()
                    except Exception as e:
                        logger.warning(f"Plugin {plugin.id} dispose failed: {e}")
        except Exception as e:
            logger.warning(f"Tool manager dispose failed: {e}")

    # Dispose infrastructure plugins
    if "infra_loader" in components:
        try:
            loader = components["infra_loader"]
            for plugin_id in list(loader._plugins.keys()):
                try:
                    loader.unload_plugin(plugin_id)
                except Exception as e:
                    logger.warning(f"Infra plugin {plugin_id} unload failed: {e}")
        except Exception as e:
            logger.warning(f"Infra loader dispose failed: {e}")


# ── FastAPI app ────────────────────────────────────────────────

app = FastAPI(
    title="Antigravity Plugin Server",
    version="1.0.0",
    description=(
        "Standalone process that owns plugin lifecycle. The main "
        "backend (port 8000) talks to this server over HTTP. All "
        "plugin reloads happen HERE, isolated from the main backend."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Permissive CORS for the dev environment. The plugin server is
# only called by the main backend, but CORS helps when developers
# poke the REST API from their browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
from app.plugin_server.routes.health import router as health_router
from app.plugin_server.routes.plugins import router as plugins_router
from app.plugin_server.routes.infra import router as infra_router
from app.plugin_server.routes.extensions import router as extensions_router
from app.plugin_server.routes.tools import router as tools_router

app.include_router(health_router, prefix="/health", tags=["health"])
app.include_router(plugins_router, prefix="/plugins", tags=["plugins"])
app.include_router(infra_router, prefix="/infra", tags=["infrastructure"])
app.include_router(extensions_router, prefix="/extensions", tags=["extensions"])
app.include_router(tools_router, prefix="/tools", tags=["tools"])


# ── Entry point ────────────────────────────────────────────────


def run() -> None:
    """Console-script entry point: `uv run plugin-server`."""
    import uvicorn

    uvicorn.run(
        "app.plugin_server.main:app",
        host=os.environ.get("PLUGIN_SERVER_HOST", "0.0.0.0"),
        port=int(os.environ.get("PLUGIN_SERVER_PORT", "8081")),
        reload=os.environ.get("PLUGIN_SERVER_RELOAD", "0") == "1",
        workers=1,  # single worker — the plugin server is its own pool
        log_level=os.environ.get("LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    run()
