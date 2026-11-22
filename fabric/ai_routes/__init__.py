"""Fabric AI-model-serving routers.

Fabric ports of the AI-specific Backend routes, delegated to the
``common_lib`` services:

- ``models_router``          ← ``Backend/app/modules/models/routes/router.py``
                              (+ ``resolve.py``, ``routing_frontier.py``)
- ``models_external_router`` ← ``Backend/app/modules/models/external_routes.py``
- ``sd_models_router``       ← ``Backend/app/modules/sd_models/routes/router.py``
- ``sam3_router``            ← ``Backend/app/modules/sam3/routes/router.py``
- ``agents_router``          ← ``Backend/app/modules/agents/routes/index.py``
                              (+ registry/runtime/session/pipeline/tracing)

All service imports are lazy so the fabric control-plane venv
(``toolchains/fabric/.venv``) stays importable without sqlmodel/sqlalchemy.
"""

from fabric.ai_routes.models_external_routes import (
    router as models_external_router,
)
from fabric.ai_routes.models_routes import (
    router as models_router,
)
from fabric.ai_routes.sam3_routes import (
    router as sam3_router,
)
from fabric.ai_routes.sd_models_routes import (
    router as sd_models_router,
)

__all__ = [
    "models_external_router",
    "models_router",
    "sam3_router",
    "sd_models_router",
]

# ``agents_router`` is deliberately NOT imported here: ``common_lib.modules.agents``
# pulls the integration stack (observability → secrets → cryptography, …),
# which the fabric control-plane venv does not carry. The fabric app mounts
# it behind a try/except via ``ai_routes.agents.index`` instead.
