"""Fabric port of the Backend agents module routers.

The combined router lives in ``index.py``; the individual sub-routers
live alongside it (``registry``, ``runtime_routes``, ``session_routes``,
``pipeline_routes``, ``tracing_routes``). The package ``__init__`` is
deliberately light so the fabric app can mount individual modules even
when the full ``common_lib.modules.agents`` package stack is unavailable
in the fabric venv.
"""

__all__ = ["router"]
