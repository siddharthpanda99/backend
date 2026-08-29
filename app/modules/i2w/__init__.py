"""``app.modules.i2w`` — thin FastAPI surface for the I2W framework.

The I2W package in ``common_lib`` owns the business logic (stages 1-4, training,
search, end-to-end generator). The router layer in this module is **stateless**:
every handler is a one-line delegate to a ``i2w_*`` @node wrapper registered by
the platform's node scanner. No DB queries, no orchestration, no validation
beyond what FastAPI does at the request edge.

Phase 7 wiring (per ``docs/08_api_contract.md``):

* REST  — 40+ endpoints, mounted at ``/api/v1/i2w``
* WS    — ``/api/v1/i2w/ws`` (bidirectional)
* SSE   — ``/api/v1/i2w/generate/stream`` (one-way)
* MCP   — registered in ``app/mcp/tools/i2w.py`` via
  ``register_i2w_tools(mcp)`` from ``app/mcp/server.py``

The whole module is **feature-flag gated** by
``instruction_to_workflow``. When the flag is off, every endpoint returns
``404 Not Found`` (so the route is invisible to clients — not 200/501).
"""

from __future__ import annotations

from app.modules.i2w.routes.router import router

__all__ = ["router"]
