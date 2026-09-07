"""Plugin Server — A separate FastAPI process for plugin lifecycle.

This sub-package contains the standalone Plugin Server that runs
on port 8081 (configurable). It owns:

* Tool plugins (BaseToolPlugin subclasses, 266+ files)
* Infrastructure plugins (PluginLoader, 39 services from platform.yml)
* Hot-loadable extensions (ComfyUI, git, pip)
* The SafeReloadGuard + PluginWatcher

The main backend (port 8000) talks to this server over HTTP. The
main backend never imports plugin code directly — that isolation
is what makes safe-reload truly non-disruptive.

Architecture:
    main backend  --HTTP-->  plugin server  --in-process-->  plugins

See PLUGIN_SERVER.md for the full design rationale.
"""
