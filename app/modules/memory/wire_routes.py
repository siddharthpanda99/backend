"""Wire all memory sub-routers into the main memory router."""

from app.modules.memory.routes import router
from app.modules.memory.routes.core_routes import router as core_router
from app.modules.memory.routes.context_routes import router as context_router
from app.modules.memory.routes.storage_routes import router as storage_router
from app.modules.memory.routes.retrieval_routes import router as retrieval_router
from app.modules.memory.routes.semantics_routes import router as semantics_router
from app.modules.memory.routes.forecasting_routes import router as forecasting_router
from app.modules.memory.routes.strategy_routes import router as strategy_router
from app.modules.memory.routes.adaptation_routes import router as adaptation_router
from app.modules.memory.routes.execution_routes import router as execution_router
from app.modules.memory.routes.security_routes import router as security_router
from app.modules.memory.routes.observability_routes import (
    router as observability_router,
)
from app.modules.memory.routes.federation_routes import router as federation_router
from app.modules.memory.routes.testing_routes import router as testing_router
from app.modules.memory.routes.versioning_routes import router as versioning_router
from app.modules.memory.routes.working_routes import router as working_router
from app.modules.memory.routes.mql_routes import router as mql_router
from app.modules.memory.routes.multimodal_routes import router as multimodal_router
from app.modules.memory.routes.economics_routes import router as economics_router
from app.modules.memory.routes.persona_routes import router as persona_router
from app.modules.memory.routes.causal_routes import router as causal_router
from app.modules.memory.routes.marketplace_routes import router as marketplace_router
from app.modules.memory.routes.driver_routes import router as driver_router
from app.modules.memory.routes.stores_routes import router as stores_router
from app.modules.memory.routes.blueprints_routes import router as blueprints_router
from app.modules.memory.routes.blocks_routes import router as blocks_router
from app.modules.memory.routes.docs_routes import router as docs_router
from app.modules.memory.routes.compaction_routes import router as compaction_router
from app.modules.memory.routes.conflict_routes import router as conflict_router
from app.modules.memory.routes.instances_routes import router as instances_router
from app.modules.memory.routes.summaries_routes import router as summaries_router
from app.modules.memory.routes.knowledge_routes import router as knowledge_router
from app.modules.memory.routes.enrichment_routes import router as enrichment_router

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
router.include_router(compaction_router)
router.include_router(conflict_router)
router.include_router(instances_router)
router.include_router(summaries_router)
router.include_router(knowledge_router)
router.include_router(enrichment_router)

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
