import os
import sys
from pathlib import Path

# --- BOOTSTRAP: Ensure development common_lib takes precedence ---
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
COMMON_LIB_SRC = str(REPO_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)
    print(f"!!! [BOOTSTRAP] Injecting dev common_lib: {COMMON_LIB_SRC}")

# Silence the common 'triton' traceback on Windows before importing any torch-related libs
os.environ["XFORMERS_FORCE_DISABLE_TRITON"] = "1"

from common_lib.modules.image_processing.core.common.optimizations import (
    set_global_precision,
)

set_global_precision()

# --- FILE LOGGING INITIALIZATION ---
from app.core.logging_config import setup_logging

setup_logging("logs/server.log")

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.core.settings import get_settings
from app.core.openapi import custom_openapi

# Import Routers
# Import Routers
from app.modules.common.routes.index import router as common_router
from app.modules.auth.routes.index import router as auth_router
from app.modules.sessions.routes.index import router as sessions_router
from app.modules.authorization.routes.roles import router as roles_router
from app.modules.authorization.routes.permissions import router as permissions_router
from app.modules.users.routes.users import router as users_router
from app.modules.projects.routes.projects import router as projects_router
from app.modules.agents.routes.index import router as agents_router
from app.modules.entities.routes.registry import router as entities_router
from app.modules.workflows.routes.index import router as workflows_router
from app.modules.tools.routes.index import router as tools_router
from app.modules.memories.routes.index import router as memories_router
from app.modules.models.routes import router as models_router
from app.modules.models.external_routes import router as external_models_router
from fastapi import Depends
from app.modules.auth.dependencies.index import get_current_active_user

settings = get_settings()

import sys
import time
from sqlalchemy import text
from app.modules.database.service.connection import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Verify Database Connection
    max_retries = 4
    retry_interval = 2

    for attempt in range(max_retries):
        try:
            print(
                f"Startup: Verifying database connection (Attempt {attempt + 1}/{max_retries})..."
            )
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            print("Database connection established successfully.")

            from app.modules.database.service.connection import init_db

            init_db()
            print("Database initialized and models registered.")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(
                    f"Warning: Database connection failed. Retrying in {retry_interval} seconds..."
                )
                print(f"Error: {e}")
                time.sleep(retry_interval)
            else:
                print("=" * 60)
                print(
                    f"CRITICAL ERROR: Could not connect to the database after {max_retries} attempts."
                )
                print(
                    f"Please ensure the database server is running at {settings.POSTGRES_SERVER}:{settings.POSTGRES_PORT}."
                )
                print(f"Detailed Error: {e}")
                print("=" * 60)
                sys.exit(1)

    # --- SYNC: Import all entities from file system to database ---
    if not settings.SKIP_REGISTRY_SYNC:
        print("Startup: Synchronizing file system entities to database...")
        try:
            from app.core.common_lib_integration import sync_manager, common_memory

            # --- SYNC: AI Models Registry ---
            from common_lib.modules.ai_models.container import AIModelsContainer

            AIModelsContainer().seed_defaults()
            print("AI Model Registry synchronized.")

            # Perform sync
            report = sync_manager.sync_all_from_files()

            # Fetch counts for verification
            t_count = len(common_memory.list_tool_definitions())
            w_count = len(common_memory.list_workflow_definitions())
            a_count = len(common_memory.list_agent_definitions())

            print("=" * 60)
            print(f"Registry Sync Complete:")
            print(f"- Tools Indexed: {t_count}")
            print(f"- Workflows Indexed: {w_count}")
            print(f"- Agents Indexed: {a_count}")
            print(f"Sync Report: {report.entities_processed} entities processed.")
            print("=" * 60)
        except Exception as e:
            print(f"Warning: Initial sync failed: {e}")
    else:
        print("Startup: Skipping registry sync (SKIP_REGISTRY_SYNC=True)")

    yield
    # Shutdown
    engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=settings.OPENAPI_URL,
        docs_url=settings.DOCS_URL,
        redoc_url=settings.REDOC_URL,
        lifespan=lifespan,
    )

    # Set all CORS enabled origins
    # Set all CORS enabled origins
    # Using allow_origin_regex to allow any origin with credentials (safe for dev, restrict in prod if needed)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex="https?://.*",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register Custom OpenAPI
    app.openapi = lambda: custom_openapi(app)

    # Global auth dependency — applied to ALL routes at once.
    # When DEV_MODE=True, auth is bypassed entirely.
    # When DEV_MODE=False, every request must be authenticated.
    global_deps = [Depends(get_current_active_user)] if not settings.DEV_MODE else []

    # Include Routers
    app.include_router(
        common_router, prefix=settings.API_V1_STR, dependencies=global_deps
    )
    app.include_router(
        auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"]
    )  # Auth handles its own security
    app.include_router(
        sessions_router,
        prefix=f"{settings.API_V1_STR}/sessions",
        tags=["Sessions"],
        dependencies=global_deps,
    )

    # Module Routers
    app.include_router(
        roles_router,
        prefix=f"{settings.API_V1_STR}/roles",
        tags=["Roles"],
        dependencies=global_deps,
    )
    app.include_router(
        permissions_router,
        prefix=f"{settings.API_V1_STR}/permissions",
        tags=["Permissions"],
        dependencies=global_deps,
    )
    app.include_router(
        users_router,
        prefix=f"{settings.API_V1_STR}/users",
        tags=["Users"],
        dependencies=global_deps,
    )
    app.include_router(
        projects_router,
        prefix=f"{settings.API_V1_STR}/projects",
        tags=["Projects"],
        dependencies=global_deps,
    )

    # Entities & Orchestration
    app.include_router(
        entities_router,
        prefix=f"{settings.API_V1_STR}/entities/registry",
        tags=["Entities Registry"],
        dependencies=global_deps,
    )
    app.include_router(
        agents_router,
        prefix=f"{settings.API_V1_STR}/agents",
        tags=["Agents (Management)"],
        dependencies=global_deps,
    )
    app.include_router(
        workflows_router,
        prefix=f"{settings.API_V1_STR}/workflows",
        tags=["Workflows"],
        dependencies=global_deps,
    )
    app.include_router(
        tools_router,
        prefix=f"{settings.API_V1_STR}/tools",
        tags=["Tools"],
        dependencies=global_deps,
    )
    app.include_router(
        memories_router,
        prefix=f"{settings.API_V1_STR}/memories",
        tags=["Memories"],
        dependencies=global_deps,
    )
    app.include_router(
        models_router,
        prefix=f"{settings.API_V1_STR}/models",
        tags=["Models Hub"],
        dependencies=global_deps,
    )
    app.include_router(
        external_models_router,
        prefix=f"{settings.API_V1_STR}/models/external",
        tags=["External Models Discovery"],
        dependencies=global_deps,
    )

    # New Vision API
    from app.modules.vision.routes import router as vision_router

    print(f"Including Vision router with prefix: {settings.API_V1_STR}/vision")
    app.include_router(
        vision_router,
        prefix=f"{settings.API_V1_STR}/vision",
        tags=["Vision"],
        dependencies=global_deps,
    )

    # MCP (Model Context Protocol)
    from app.modules.mcp.routes import router as mcp_router

    app.include_router(
        mcp_router,
        prefix=f"{settings.API_V1_STR}/mcp",
        tags=["MCP Ecosystem"],
        dependencies=global_deps,
    )

    # SOTA Debug (Simulating Parallel Spans)
    from app.modules.debug.routes import router as debug_router

    app.include_router(
        debug_router,
        prefix=f"{settings.API_V1_STR}/debug",
        tags=["Debug Simulator"],
        dependencies=global_deps,
    )

    # Serve generated images as static files
    from common_lib.paths import GENERATED_CONTENT

    os.makedirs(GENERATED_CONTENT, exist_ok=True)
    app.mount(
        "/generated", StaticFiles(directory=str(GENERATED_CONTENT)), name="generated"
    )

    # Serve character profiles for UI previews
    from common_lib.paths import CHARACTER_PROFILES_DIR

    if CHARACTER_PROFILES_DIR.exists():
        app.mount(
            f"{settings.API_V1_STR}/profiles",
            StaticFiles(directory=str(CHARACTER_PROFILES_DIR)),
            name="profiles",
        )

    # Serve assets for UI previews and loading
    from common_lib.paths import ASSETS_DIR

    os.makedirs(ASSETS_DIR, exist_ok=True)
    app.mount(
        f"{settings.API_V1_STR}/assets",
        StaticFiles(directory=str(ASSETS_DIR)),
        name="assets",
    )

    # Exception Handlers
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException as StarletteHTTPException
    from sqlalchemy.exc import SQLAlchemyError
    from app.core.exceptions import (
        NexusException,
        nexus_exception_handler,
        validation_exception_handler,
        pydantic_exception_handler,
        sqlalchemy_exception_handler,
        generic_exception_handler,
        http_exception_handler,
    )

    app.add_exception_handler(NexusException, nexus_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    from pydantic import ValidationError

    app.add_exception_handler(ValidationError, pydantic_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
