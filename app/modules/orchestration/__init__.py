"""Orchestration API module.

Exposes REST endpoints for the orchestration system:
- Multi-Agent Coordination (PlannerAgent → ExecutorAgent → CriticAgent)
- Role Routing (RoleClassifier + ModelSelector)
- Hook engine status
- Context management
- Inference engine
"""

from app.modules.orchestration.routes import router

__all__ = ["router"]
