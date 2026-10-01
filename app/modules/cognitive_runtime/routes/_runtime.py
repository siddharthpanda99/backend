"""Shared ``CognitiveRuntime`` instance for the cognitive_runtime transport routers.

Every route module previously built its own ``CognitiveRuntime()`` at import
time. ``CognitiveRuntime`` keeps its run records in a per-instance dict
(``self._runs``), so a run created by ``POST /cognitive/execute`` was invisible
to ``GET /cognitive/runs/{run_id}`` — the lookup endpoint 404'd for runs created
microseconds earlier in the same process.

This module owns the single instance so the whole router sees one run store.
Thin transport only: it constructs the common_lib service and does nothing else.
"""

from __future__ import annotations

from common_lib.modules.cognitive_runtime.services.runtime import CognitiveRuntime

_runtime = CognitiveRuntime()


def get_runtime() -> CognitiveRuntime:
    """Return the process-wide ``CognitiveRuntime`` used by the routers."""
    return _runtime


__all__ = ["get_runtime"]
