"""Wire all memory sub-routers into the main memory router."""

from app.modules.memory.routes import router
from app.modules.memory.core_routes import router as core_router
from app.modules.memory.context_routes import router as context_router
from app.modules.memory.storage_routes import router as storage_router
from app.modules.memory.retrieval_routes import router as retrieval_router
from app.modules.memory.semantics_routes import router as semantics_router
from app.modules.memory.forecasting_routes import router as forecasting_router
from app.modules.memory.strategy_routes import router as strategy_router
from app.modules.memory.adaptation_routes import router as adaptation_router
from app.modules.memory.execution_routes import router as execution_router
from app.modules.memory.security_routes import router as security_router
from app.modules.memory.observability_routes import router as observability_router
from app.modules.memory.federation_routes import router as federation_router
from app.modules.memory.testing_routes import router as testing_router
from app.modules.memory.versioning_routes import router as versioning_router
from app.modules.memory.working_routes import router as working_router
from app.modules.memory.mql_routes import router as mql_router
from app.modules.memory.multimodal_routes import router as multimodal_router
from app.modules.memory.economics_routes import router as economics_router
from app.modules.memory.persona_routes import router as persona_router
from app.modules.memory.causal_routes import router as causal_router
from app.modules.memory.marketplace_routes import router as marketplace_router
from app.modules.memory.driver_routes import router as driver_router
from app.modules.memory.stores_routes import router as stores_router
from app.modules.memory.blueprints_routes import router as blueprints_router
from app.modules.memory.blocks_routes import router as blocks_router
from app.modules.memory.docs_routes import router as docs_router

# Include all sub-routers under the main router
# All sub-routers have their own prefixes (e.g., /core, /context)
# so they nest under /api/v1/memory/
router.include_router(blueprints_router)
router.include_router(blocks_router)
router.include_router(docs_router)
router.include_router(core_router)
router.include_router(context_router)
router.include_router(storage_router)
router.include_router(retrieval_router)
router.include_router(semantics_router)
router.include_router(forecasting_router)
router.include_router(strategy_router)
router.include_router(adaptation_router)
router.include_router(execution_router)
router.include_router(security_router)
router.include_router(observability_router)
router.include_router(federation_router)
router.include_router(testing_router)
router.include_router(versioning_router)
router.include_router(working_router)
router.include_router(mql_router)
router.include_router(multimodal_router)
router.include_router(economics_router)
router.include_router(persona_router)
router.include_router(causal_router)
router.include_router(marketplace_router)
router.include_router(driver_router)
router.include_router(stores_router)

# Reorder routes so that wildcard/parameterized routes at the root level (like /{memory_id})
# are evaluated last, preventing them from hijacking static sub-router paths (like /blocks).
wildcard_routes = []
static_routes = []
for r in router.routes:
    if r.path == "/{memory_id}":
        wildcard_routes.append(r)
    else:
        static_routes.append(r)
router.routes = static_routes + wildcard_routes

