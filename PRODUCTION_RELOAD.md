# Production Multi-Worker Startup

This document explains how to run the backend with a uvicorn worker
pool for **zero-downtime plugin reloads**.

## Quick start

### Single worker (default — for development)

```bash
uv run python main.py
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

In this mode:
- One process serves everything.
- Hot-reload is opt-in via `PLUGIN_RELOAD_MODE=poll|watch` env var.
- A reload of a plugin is **cooperative** (drains in-flight, max
  `drain_timeout_sec` per plugin) but **the process is not restarted**.
- A reload is therefore **not zero-downtime**; it's "short blip".

### Multiple workers (production)

```bash
UVICORN_WORKERS=4 uv run python main.py
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

In this mode:
- N processes serve the same FastAPI app.
- Each process has its own `PluginManager` and `ReloadGuard` singleton.
- A reload of a plugin only affects the **process that received the
  reload request** (typically a single worker behind a load balancer).
- Other workers keep serving traffic.

For **true zero-downtime**, run a process supervisor that does
rolling restarts:

### Rolling restarts with a process supervisor

The pattern is the same as Kubernetes rolling updates or Docker
Swarm update config:

```
┌────────────────────────────────────────────┐
│          nginx / HAProxy / K8s ingress     │
│  (load-balances across the worker pool)     │
└───────┬────────┬────────┬────────┬─────────┘
        ▼        ▼        ▼        ▼
    worker-1 worker-2 worker-3 worker-4
```

**Reload sequence (assumes `--reload` is OFF, workers are managed by supervisor):**

1. Send `SIGHUP` to worker-1 only.
2. worker-1 receives SIGHUP → starts drain → finishes in-flight
   requests → exits cleanly.
3. Supervisor starts a fresh worker-1 with the new code.
4. After worker-1 is healthy, repeat for worker-2, then 3, then 4.
5. At no point is the load balancer unable to find a healthy
   backend.

## Plugin reload semantics across workers

When `POST /api/v1/plugins/{id}/safe-reload` is called:

- The **nginx upstream** (round-robin) routes to worker-2.
- worker-2 drains → swaps the plugin class → returns 200.
- workers 1, 3, 4 still have the **old** plugin class in memory.

If the plugin's behaviour is supposed to be consistent across
workers (e.g. a new @tool method that should be available
everywhere immediately), you must **either**:

1. **Reload all workers individually** (loop over each port).
2. **Use a SIGHUP-rolling-restart pattern** to restart each worker
   in turn.

For consistency, the recommended pattern is option 2: rolling
restarts via supervisor. Option 1 is for ad-hoc emergency hot-fixes.

## Reload APIs (all safe)

| Endpoint | Effect |
|---|---|
| `POST /api/v1/plugins/{id}/safe-reload` | Drain + atomic swap + warm. Single worker only. |
| `POST /api/v1/plugins/reload` | Naive reload (clears all slots in this worker). |
| `POST /api/v1/agents/reload` (via orchestration plugin) | Re-loads infrastructure plugins from `platform.yml`. |
| `MCP: safe_reload_plugin(id)` | Same as the REST endpoint. |
| `MCP: safe_reload_all_plugins()` | Same as `POST /api/v1/plugins/reload`. |
| `uv run sdk-reload <plugin-id>` | Same as the REST endpoint (uses the SDK). |
| File-system watcher (`PLUGIN_RELOAD_MODE=poll|watch`) | Auto-reload on save. Per-worker; you'd need one watcher per process. |

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `UVICORN_WORKERS` | `1` | Number of worker processes. Set to N for zero-downtime pool. |
| `UVICORN_HOST` | `0.0.0.0` | Bind address. |
| `UVICORN_PORT` | `8000` | Bind port. |
| `UVICORN_RELOAD` | `1` (single-worker) | Use uvicorn's `--reload` (file watcher on `*.py`). Auto-disabled when workers > 1. |
| `PLUGIN_RELOAD_MODE` | `manual` | `manual` \| `poll` \| `watch`. Watcher mode for the SDK's own watcher. |
| `PLUGIN_RELOAD_INTERVAL` | `2.0` | Poll interval in seconds. |
| `PLUGIN_RELOAD_DEBOUNCE_MS` | `300` | Watch-mode debounce. |
| `PLUGIN_RELOAD_DRAIN_TIMEOUT` | `30` | Max seconds to wait for in-flight calls during a swap. |
| `PLUGIN_WATCH_DIRS` | _auto_ | Comma-separated extra dirs to watch. |
| `PLUGIN_WATCH_EXTENSIONS` | `1` | Set to `0` to skip the extensions cache dir. |

## Recommended production setup

```bash
# 4 workers, manual reload only (rolling restarts for new releases)
UVICORN_WORKERS=4 \
PLUGIN_RELOAD_MODE=manual \
PLUGIN_RELOAD_DRAIN_TIMEOUT=30 \
  uv run python main.py
```

```bash
# Development: 1 worker with hot-reload + file-watcher
UVICORN_RELOAD=0 \
PLUGIN_RELOAD_MODE=poll \
PLUGIN_RELOAD_INTERVAL=1.0 \
  uv run python main.py
```

## Why this is "safe but not zero-downtime" in single-worker mode

The `SafeReload` protocol (see `safe_reload.py`):

- **Drains** new calls to a plugin (returns 503)
- **Waits** for in-flight calls to finish (up to `drain_timeout_sec`)
- **Swaps** the plugin class atomically
- **Warms** the new instance (user-supplied hook)
- **Resumes** serving

This means:

- A tool call that started 100ms before the reload will finish
  on the old instance.
- A tool call that starts 100ms after the reload will run on
  the new instance.
- A tool call that started 1ms before but is in a long synchronous
  LLM call will be cut off at `drain_timeout_sec` with a 503 (and
  the user can retry).

**In single-worker mode, between the drain and the resume, the
plugin is unavailable.** That's the "short blip" mentioned above.

**In multi-worker mode with rolling restarts, no blip is visible
to the user** because at least one worker is always healthy.

## The truly zero-downtime alternative: hot-swap via shared cache

The most advanced approach (not implemented; future work) is:

1. Plugins are loaded into a **shared memory cache** (Redis, NFS, etc.)
2. Each worker process has a `mtime` watcher on the cache.
3. When a new plugin appears in the cache, the worker loads it
   in a separate process via `multiprocessing.Process`.
4. The new process does the `safe_invoke` and returns the result
   via IPC.
5. When all workers have confirmed the new plugin works, the old
   process is killed.

This is the model used by Envoy hot-restart, Apache mod_proxy,
and some FaaS runtimes. It's complex; recommend the rolling-restart
approach for now.
