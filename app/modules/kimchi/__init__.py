"""Kimchi — Execution pipeline API module.

Provides REST endpoints for the Ferment project execution pipeline:
- ScopingLoop: orient→interview→plan→approve
- FermentExecutor: step-by-step or batch execution with HITL support
- GradingJudge: A–F evaluation of step/phase results

All re-exports are accessible from workflows/ and orchestration/agents/
for import convenience. This module provides the HTTP transport layer.
"""

from app.modules.kimchi.routes import router

__all__ = ["router"]
