from app.modules.memory.routes import router
import app.modules.memory.wire_routes  # noqa: F401 — side-effect: attaches sub-routers

__all__ = ["router"]
