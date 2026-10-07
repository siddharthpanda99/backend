"""Life Cycle Assessment — Backend transport module.

Thin router layer only. All business logic lives in
``common_lib.modules.life_cycle_assessment``.
"""

from app.modules.life_cycle_assessment.routes import router

__all__ = ["router"]