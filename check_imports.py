"""
Comprehensive import check — simulates all module loads from main.py and
app/core/routers.py without starting the server or connecting to the database.

Usage:
    cd "Backend Monorepo/Backend"
    uv run python check_imports.py
"""

import os
import sys
from pathlib import Path

# ── BOOTSTRAP: replicate the path injection from main.py ──
REPO_ROOT = Path(__file__).parent.parent.resolve()
COMMON_LIB_SRC = str(REPO_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)

# Silence triton warning
os.environ["XFORMERS_FORCE_DISABLE_TRITON"] = "1"

failed = []
ok = []

def try_import(name, source=""):
    """Try an import, record success/failure."""
    try:
        __import__(name)
        ok.append((name, source))
        return True
    except ImportError as e:
        failed.append((name, str(e), source))
        return False
    except Exception as e:
        # Non-ImportError exceptions are still interesting
        failed.append((name, f"{type(e).__name__}: {e}", source))
        return False


print("=" * 70)
print("  COMPREHENSIVE IMPORT CHECK — BACKEND MODULES")
print("=" * 70)

# ── 1. Top-level imports from app/__init__.py ──
print("\n--- Level 1: top-level app imports ---")
try_import("app")

# ── 2. Core imports from main.py top-level ──
print("\n--- Level 2: main.py top-level imports ---")

# From common_lib
try_import("common_lib")
try_import("common_lib.modules.observability", "main.py")
try_import("common_lib.modules.observability.constants", "main.py")
try_import("common_lib.modules.observability.middleware", "main.py")
try_import("common_lib.modules.observability.events", "main.py")
try_import("common_lib.modules.observability.wiring", "main.py")
try_import("common_lib.modules.observability.slos", "main.py")
try_import("common_lib.modules.data_storage.database.connection", "main.py")
try_import("common_lib.modules.ai_models.container", "main.py")
try_import("common_lib.modules.ai_models.domain.exceptions", "main.py")
try_import("common_lib.modules.exceptions", "main.py")
try_import("common_lib.paths", "main.py")

# FastAPI / starlette
try_import("fastapi", "main.py")
try_import("fastapi.staticfiles", "main.py")
try_import("fastapi.middleware.cors", "main.py")
try_import("fastapi.exceptions", "main.py")
try_import("starlette.exceptions", "main.py")

# SQLAlchemy
try_import("sqlalchemy", "main.py")
try_import("sqlalchemy.exc", "main.py")

# Pydantic
try_import("pydantic", "main.py")

# Prometheus
try_import("prometheus_fastapi_instrumentator", "main.py optional")

# ── 3. App core modules ──
print("\n--- Level 3: app.core modules ---")
try_import("app.core.settings", "main.py")
try_import("app.core.openapi", "main.py")
try_import("app.core.exceptions", "main.py")
try_import("app.core.routers", "main.py (register_routers)")
try_import("app.core.common_lib_integration", "main.py")

# ── 4. App middleware ──
print("\n--- Level 4: app.middleware ---")
try_import("app.middleware.rate_limit", "main.py")
try_import("app.middleware.response_cache", "main.py (optional)")
try_import("app.modules.auth.middleware.authz", "main.py")

# ── 5. Auth dependencies ──
print("\n--- Level 5: auth dependencies ---")
try_import("app.modules.auth.dependencies", "main.py")

# ── 6. ALL routers from routers.py ──
print("\n--- Level 6: all routers from app/core/routers.py ---")

# Core direct imports
modules = [
    "app.modules.common.routes.index",
    "app.modules.auth.routes.index",
    "app.modules.sessions.routes.index",
    "app.modules.authorization.routes.roles",
    "app.modules.authorization.routes.permissions",
    "app.modules.users.routes.users",
    "app.modules.projects.routes.projects",
    "app.modules.agents.routes.index",
    "app.modules.agents.routes.pipeline_routes",
    "app.modules.agents.routes.policy_routes",
    "app.modules.entities.routes.registry",
    "app.modules.entities.instance_routes",
    "app.modules.workflows.routes.index",
    "app.modules.workflows.routes.observability",
    "app.modules.workflows.routes.configs",
    "app.modules.workflows.routes.collaboration",
    "app.modules.workflows.routes.combinatorial",
    "app.modules.workflows.routes.failure_analysis",
    "app.modules.tools.routes.index",
    "app.modules.memory.routes",
    "app.modules.memories.routes.index",
    "app.modules.vectorstores.routes",
    "app.modules.models.routes",
    "app.modules.models.external_routes",
    "app.modules.data_forge.routes",
    "app.modules.grid.routes",
    "app.modules.plugins.routes.router",
    "app.modules.daw.routes",
    "app.modules.hooks.routes",
    "app.modules.webhooks",
    "app.modules.app_builder.forms",
    "app.modules.app_builder.features",
    "app.modules.connection_health",
    "app.modules.app_builder.ecosystem",
    "app.modules.app_builder",
    "app.modules.dashboard.routes",
    "app.modules.system.routes",
    "app.modules.settings.routes",
    "app.modules.dip.routes.ingestion",
    "app.modules.dip.routes.pipeline",
    "app.modules.dip.routes.rag",
    "app.modules.dip.routes.kg",
    "app.modules.dip.routes.storage",
    "app.modules.dip.routes.embeddings",
    "app.modules.file_browser",
    "app.modules.file_browser.macro_routes",
    "app.modules.notification.routes",
    "app.modules.wildcards.routes",
    "app.modules.sam3.routes",
    "app.modules.keys_management",
    "app.modules.proxy_routing",
    "app.modules.collage.routes",
    "app.modules.experiments.routes",
    "app.modules.ext_apps",
    "app.modules.connectors.routes",
    "app.modules.connectors.mcp.server",
    "app.modules.plugins.routes",
]

for mod in modules:
    try_import(mod, "routers.py (direct)")

# Lazy imports (these are imported inside functions, but we can try them directly)
print("\n--- Level 7: lazy-loaded router modules ---")
lazy_modules = [
    "app.modules.vision.routes",
    "app.modules.filters.routes",
    "app.modules.nodes.routes",
    "app.modules.prompts.routes",
    "app.modules.configs.routes",
    "app.modules.sd_models.routes",
    "app.modules.audio.routes",
    "app.mcp.routes",
    "app.modules.debug.routes",
    "app.modules.marketplace.routes",
    "app.modules.graph.routes",
    "app.modules.app_builder.schema",
    "app.modules.sync.routes.index",
    "app.modules.integration.routes",
    "app.modules.scheduler.routes",
    "app.modules.scheduler.routes.news_routes",
    "app.modules.prompt_studio.routes",
    "app.modules.hitl.routes",
    "app.modules.knowledge.routes",
    "app.modules.governance.routes",
    "app.modules.observability.routes",
    "app.modules.docs.routes",
    "app.modules.authorization.routes.authz_router",
    "app.modules.sota.routes",
    "app.modules.rip.routes",
    "app.modules.team.routes",
    "app.modules.orchestration",
    "app.modules.kimchi",
]

for mod in lazy_modules:
    try_import(mod, "routers.py (lazy)")

# Lazy function-inside routers (try importing the specific lazy-dependency files)
print("\n--- Level 8: knowledge_hub multi-router submodules ---")
hub_modules = [
    "app.modules.knowledge_hub",
    "app.modules.connectors.seed",
]
for mod in hub_modules:
    try_import(mod, "routers.py / main.py")

# ── 9. Startup lifecycle imports ──
print("\n--- Level 9: startup lifecycle imports ---")
lifecycle_modules = [
    "common_lib.modules.memory.memory_stores.sota.service",
    "common_lib.modules.memory.memory_stores.sota",
    "common_lib.modules.integration.docs.api_docs",
    "common_lib.modules.rip.rip_synthesis.schemas",
    "common_lib.modules.rip.rip_synthesis.service",
    "common_lib.modules.integration.adapters.tools",
    "common_lib.modules.integration.services.config_service",
    "common_lib.modules.plugins.connectors.models.db",
    "common_lib.modules.keys_management.service",
    "common_lib.modules.keys_management.schemas",
    "common_lib.modules.governance.hitl.service",
    "common_lib.modules.knowledge_hub.seed_data",
    "common_lib.modules.settings.service",
    "common_lib.modules.memory.config",
    "common_lib.modules.memory.service",
    "common_lib.vectorstores.factory",
    "common_lib.modules.core_infrastructure.scheduler.service",
    "app.modules.memories.dependencies",
    "app.modules.knowledge.models",
    "common_lib.templates.node_definitions.loader",
]
for mod in lifecycle_modules:
    try_import(mod, "startup lifecycle")

# ── Summary ──
print("\n" + "=" * 70)
print("  IMPORT CHECK SUMMARY")
print("=" * 70)
print(f"  Successful: {len(ok)}")
print(f"  Failed:     {len(failed)}")

if failed:
    print("\n  FAILED IMPORTS:")
    print("-" * 70)
    for name, error, source in failed:
        print(f"  FAIL: [{source}] {name}")
        print(f"    Reason: {error}")
        print()
else:
    print("\n  ✅ ALL IMPORTS PASSED!")

print("=" * 70)

# Exit with error code if any failures
sys.exit(1 if failed else 0)
