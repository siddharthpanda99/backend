"""Decision Fabric transport module (DF-030/DF-056) — thin router only."""

from app.modules.decision.routes import router  # noqa: F401

__all__ = ["router"]
