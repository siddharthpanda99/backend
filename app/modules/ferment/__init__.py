"""Ferment — Multi-agent iterative improvement engine API module.

Provides REST endpoints for the Ferment project lifecycle:
- ScopingLoop: goal → phased step plan (orient → plan → approve)
- FermentExecutor / role-driven ferment graph: step/phase execution
- GradingJudge: A–F evaluation of step/phase results
- ProjectEngine (Goal Mode): goal-driven project facade + status payload

All logic lives in common_lib.modules.ferment; this module is the thin
HTTP transport layer only.
"""

from app.modules.ferment.routes import router

__all__ = ["router"]
