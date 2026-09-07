# Plugin Server — Architecture

## The Problem

The platform currently has **3 plugin systems** all running **inside the main backend process**:

| System | Module | What it loads | Cardinality |
|---|---|---|---|
| Tool plugins | `common_lib.modules.plugins` | 266+ `BaseToolPlugin` subclasses in `modules/plugins/native/` | 1 plugin = N tools |
| Infrastructure plugins | `common_lib.modules.orchestration.plugin` | 39 services from `platform.yml` (settings, secrets, DB, RBAC) | 1 service = 1 instance |
| Hot-loadable extensions | `common_lib.modules.extensions` | ComfyUI custom nodes, git repos, pip packages | 1 extension = N nodes |

All three run **inside the main backend's Python process** (`python main.py`). This means:

- A plugin reload blocks the asyncio event loop.
- An in-flight LLM call gets killed when a plugin's DB pool is disposed.
- A new plugin import can break unrelated code (top-level side effects).
- The main backend has no way to recover from a misbehaving plugin without a full restart.

## The Solution: Separate Process

Move **all 3 plugin systems** into a **separate FastAPI process** — the **Plugin Server** — that runs on a different port. The main backend talks to it over HTTP. Now:

- A plugin reload only affects the plugin server's event loop; the main backend keeps serving LLM traffic.
- A misbehaving plugin can be killed (`kill -9`) without taking down the main backend.
- The plugin server can be restarted independently for upgrades.
- The main backend never has to import plugin code, so plugins can't break it.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Main Backend (port 8000)                      │
│                                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐            │
│  │ LLM     │   │ Chat    │   │Memory    │   │ Agentic  │            │
│  │ API     │   │ History │   │          │   │ Loop     │            │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘            │
│       │              │              │              │                │
│       └──────────────┴──────────────┴──────────────┘                │
│                          │                                         │
│                          ▼                                         │
│            ┌──────────────────────────┐                            │
│            │   PluginServerClient      │  ← NEW: HTTP client        │
│            │   (proxy to Plugin Server)│                            │
│            └──────────┬───────────────┘                            │
│                       │                                            │
└───────────────────────┼────────────────────────────────────────────┘
                        │ HTTP
                        │ (GET/POST /plugins, /extensions, /infra)
                        ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Plugin Server (port 8081)                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  SafeReloadGuard (single process)                          │      │
│  │  PluginWatcher (poll | watch modes)                        │      │
│  └──────────────────────────────────────────────────────────┘      │
│       │                  │                  │                       │
│       ▼                  ▼                  ▼                       │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                         │
│  │  Tool    │   │  Infra   │   │ Extension│                         │
│  │  Plugin  │   │  Plugin  │   │ Registry │                         │
│  │  Manager │   │  Loader  │   │          │                         │
│  └──────────┘   └──────────┘   └──────────┘                         │
│       │              │                  │                            │
│       ▼              ▼                  ▼                            │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐                         │
│  │  266     │   │  39      │   │  git /   │                         │
│  │  native  │   │  from    │   │  pip /   │                         │
│  │  tools   │   │  YAML    │   │  ComfyUI │                         │
│  └──────────┘   └──────────┘   └──────────┘                         │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  REST API (port 8081)                                      │      │
│  │  /health, /plugins, /extensions, /infra, /tools/{id}     │      │
│  └──────────────────────────────────────────────────────────┘      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐      │
│  │  MCP Server (port 8081, /mcp endpoint)                     │      │
│  │  Exposes the same tools to AI agents                       │      │
│  └──────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
```

## What runs where

### Main Backend (port 8000) — the "frontend"

- LLM API (`POST /chat`)
- Chat history
- Memory service
- Agentic loop
- Marketplace (CRUD over `MarketplaceMetadata`)
- Anything that's NOT a plugin

### Plugin Server (port 8081) — the "plugin host"

- All `BaseToolPlugin` subclasses (266+)
- All `PluginLoader` infrastructure services (39)
- All hot-loadable extensions (git/pip/ComfyUI)
- The `PluginWatcher` and `SafeReloadGuard`
- Its own REST + MCP API

### Extensions Server (port 8082) — pre-existing

- Originally a separate server for ComfyUI custom nodes
- Now subsumed into the Plugin Server (kept for backward compat)
- Plugin Server can proxy to it if needed

## The HTTP Contract

The main backend makes these calls to the Plugin Server:

```http
GET  /health                     # Is the plugin server alive?
GET  /plugins                    # List all loaded tool plugins
GET  /plugins/{id}              # Get one tool plugin's metadata
POST /plugins/{id}/safe-reload  # Drain + atomic swap
POST /plugins/reload            # Naive reload all

POST /tools/execute              # Execute a tool (this is the hot path)
      Request:  {"plugin_id": "github", "tool_name": "create_issue", "params": {...}}
      Response: {"success": true, "result": {...}, "duration_ms": 142}
      On reload: 503 with Retry-After header

GET  /infra/plugins              # List infrastructure services
GET  /infra/plugins/{id}         # Get one infrastructure service

GET  /extensions                  # List hot-loadable extensions
GET  /extensions/{id}            # Get one extension
POST /extensions/{id}/load
POST /extensions/{id}/unload
POST /extensions/{id}/reload
POST /extensions/{id}/sync

GET  /nodes                       # All discoverable @node tools
GET  /nodes/{name}                # One @node tool
POST /nodes/{name}/execute        # Execute a @node tool
```

## Safety: How Reloads Become Truly Zero-Downtime

The Plugin Server process is **independent** of the main backend. This means:

1. **Reload the Plugin Server** — main backend keeps serving LLM calls.
2. **Reload a plugin** — only the Plugin Server's event loop is affected; main backend's HTTP call gets a 503 (or waits if the request has a longer timeout).
3. **Crash the Plugin Server** — main backend returns 503 for tool calls but LLM traffic keeps flowing. The watchdog (process supervisor) restarts the Plugin Server automatically.

This is the **Kubernetes / Envoy / HAProxy pattern**: a hot-reload that doesn't take down the load balancer.

## Startup Order

```bash
# 1. Start the plugin server FIRST
uvicorn app.plugin_server.main:app --host 0.0.0.0 --port 8081 &

# 2. Wait for it to be healthy
curl -f http://localhost:8081/health || (echo "Plugin server failed to start"; exit 1)

# 3. Then start the main backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

If the Plugin Server is down when the main backend starts, the main backend will:
- Boot normally (no plugin loading blocks startup)
- Return 503 for tool calls until the Plugin Server is back
- Log warnings so ops knows the plugin host is missing

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `PLUGIN_SERVER_URL` | `http://localhost:8081` | Main backend's connection target |
| `PLUGIN_SERVER_HOST` | `0.0.0.0` | Bind address for the plugin server |
| `PLUGIN_SERVER_PORT` | `8081` | Bind port for the plugin server |
| `PLUGIN_SERVER_HEALTH_TIMEOUT_SEC` | `2.0` | Per-request timeout for health checks |
| `PLUGIN_SERVER_TOOL_TIMEOUT_SEC` | `60.0` | Per-tool-call timeout |
| `PLUGIN_SERVER_ENABLED` | `1` | Set to `0` to disable the integration (plugins run in-process) |
| `PLUGIN_RELOAD_MODE` | `manual` | See common_lib/plugins/engine/watcher.py |

## The `PluginServerClient` (proxy)

The main backend doesn't talk to the Plugin Server directly. It uses a single `PluginServerClient` class that:

- Caches the plugin list (with TTL, default 30s)
- Translates HTTP errors to typed exceptions
- Falls back to a local in-process plugin manager if the server is unreachable (with a warning log)
- Tracks circuit-breaker state: if the server fails 3 times in a row, stop calling it for 60s and serve everything 503.

```python
from app.plugin_server.client import PluginServerClient, PluginServerUnreachable

client = PluginServerClient(base_url=os.environ.get("PLUGIN_SERVER_URL", "http://localhost:8081"))

# List plugins
plugins = client.list_plugins()  # returns List[dict] or raises

# Execute a tool
try:
    result = client.execute_tool("github", "create_issue", {"title": "...", "body": "..."})
except PluginServerUnreachable:
    return 503
except PluginServerError as e:
    return 502
```

## Migration Path

**Phase 1 (this commit):** Plugin Server runs alongside main backend. Main backend **still** has its own `PluginManager` and `PluginLoader` — they're used as a **fallback** when the Plugin Server is unreachable. A new env var `PLUGIN_SERVER_ENABLED=1` (default) routes through the Plugin Server; `PLUGIN_SERVER_ENABLED=0` keeps the in-process behaviour.

**Phase 2 (future):** Deprecate the in-process plugin systems. Force `PLUGIN_SERVER_ENABLED=1`. Remove the import of `common_lib.modules.plugins.manager` from the main backend.

**Phase 3 (future):** Move the agentic loop to call the Plugin Server directly. Today the loop imports plugin code; tomorrow it makes HTTP calls.

## Files in this commit

```
Backend Monorepo/Backend/app/plugin_server/
├── __init__.py
├── main.py                  # FastAPI app, lifespan, signal handlers
├── routes/
│   ├── __init__.py
│   ├── health.py            # /health, /version
│   ├── plugins.py           # /plugins/* (tool plugins)
│   ├── infra.py             # /infra/* (infrastructure plugins)
│   ├── extensions.py        # /extensions/* (hot-loadable)
│   └── tools.py             # /tools/execute, /nodes/* (the hot path)
├── client.py                # PluginServerClient (proxy in main backend)
├── signal_handlers.py       # SIGHUP = safe-reload, SIGTERM = graceful shutdown
└── tests/
    ├── __init__.py
    ├── test_client.py       # Mock the server, test the client
    ├── test_routes.py       # Test the server's REST API
    └── test_signal.py       # Test signal handling
```

## Running

```bash
# Start the Plugin Server
uvicorn app.plugin_server.main:app --host 0.0.0.0 --port 8081

# Or with hot-reload (dev only)
uvicorn app.plugin_server.main:app --host 0.0.0.0 --port 8081 --reload

# Start the main backend
PLUGIN_SERVER_URL=http://localhost:8081 uv run python main.py

# Or with the in-process fallback (legacy)
PLUGIN_SERVER_ENABLED=0 uv run python main.py
```
