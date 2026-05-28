import os
import sys
import time
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

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

from fastapi import FastAPI, Request, Response
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
from app.modules.agents.runtime.pipeline_routes import router as pipeline_router
from app.modules.agents.runtime.policy_routes import router as policy_router
from app.modules.entities.routes.registry import router as entities_router
from app.modules.workflows.routes.index import router as workflows_router
from app.modules.workflows.routes.observability import router as observability_router
from app.modules.workflows.routes.configs import router as workflow_configs_router
from app.modules.workflows.routes.collaboration import router as collaboration_router
from app.modules.workflows.routes.combinatorial import router as combinatorial_router
from app.modules.tools.routes.index import router as tools_router
from app.modules.memory.routes import router as cognitive_memory_router
from app.modules.models.routes import router as models_router
from app.modules.models.external_routes import router as external_models_router
from app.modules.data_forge.routes import router as data_forge_router
from app.modules.grid.routes import router as grid_router
from app.modules.plugins.routes.router import router as plugins_router
from app.modules.daw.routes import router as daw_router
from app.modules.hooks.routes import router as hooks_router
from app.modules.dashboard.routes import router as dashboard_router
from app.modules.system.routes import router as system_router
from app.modules.dip.routes.ingestion import router as dip_ingestion_router
from app.modules.dip.routes.pipeline import pipeline_router
from app.modules.file_browser import router as file_browser_router
from app.modules.file_browser.macro_routes import router as macro_router
from app.modules.notification.routes import router as notification_router
from app.modules.wildcards.routes import router as wildcards_router
from app.modules.sam3.routes import router as sam3_router
from fastapi import Depends
from app.modules.auth.dependencies.index import get_current_active_user

settings = get_settings()

import sys
import time
from sqlalchemy import text
from common_lib.modules.data_storage.database.connection import engine, get_session


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

            from common_lib.modules.data_storage.database.connection import init_db
            from common_lib.modules.workflows.standard.models.observability import (
                WorkflowExecution,
                WorkflowEvent,
            )

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
            s_count = len(common_memory.list_skill_definitions())
            p_count = len(common_memory.list_prompt_definitions())
            c_count = len(common_memory.list_command_definitions())
            wc_count = len(common_memory.list_workflow_config_definitions())
            kb_count = len(common_memory.list_kb_entries())
            tpl_count = len(common_memory.list_template_definitions())

            print("=" * 60)
            print(f"Registry Sync Complete:")
            print(f"- Tools Indexed: {t_count}")
            print(f"- Workflows Indexed: {w_count}")
            print(f"- Agents Indexed: {a_count}")
            print(f"- Skills Indexed: {s_count}")
            print(f"- Prompts Indexed: {p_count}")
            print(f"- Commands Indexed: {c_count}")
            print(f"- Workflow Configs Indexed: {wc_count}")
            print(f"- Knowledgebase Indexed: {kb_count}")
            print(f"- Templates Indexed: {tpl_count}")
            print(f"Sync Report: {report.entities_processed} entities processed.")
            print("=" * 60)
        except Exception as e:
            print(f"Warning: Initial sync failed: {e}")
    else:
        print("Startup: Skipping registry sync (SKIP_REGISTRY_SYNC=True)")

    # --- SEED: UI-only node definitions into DB ---
    if not settings.SKIP_REGISTRY_SYNC:
        try:
            from common_lib.templates.node_definitions.loader import seed_ui_nodes_to_db

            seeded = seed_ui_nodes_to_db(common_memory)
            if seeded:
                print(f"Startup: Seeded {seeded} UI node definitions to database")
        except Exception as e:
            print(f"Warning: UI node seed failed: {e}")

    # --- RESUME: Pending model downloads ---
    try:
        import json
        from pathlib import Path
        from common_lib.modules.ai_models.container import AIModelsContainer

        queue_dir = Path(os.environ.get("MODEL_QUEUE_DIR", "/tmp/model_downloads"))
        if queue_dir.exists():
            pending_tasks = list(queue_dir.glob("*.json"))
            if pending_tasks:
                print(
                    f"Startup: Found {len(pending_tasks)} pending downloads to resume..."
                )

                container = AIModelsContainer()
                event_bus = container.downloader.event_bus
                downloader_factory = CivitAIDownloader

                for task_file in pending_tasks:
                    try:
                        with open(task_file) as f:
                            task_data = json.load(f)

                        task_id = task_data.get("task_id")
                        model_id = task_data.get("model_id")
                        version_id = task_data.get("version_id")
                        file_id = task_data.get("file_id")
                        dest_folder = task_data.get("destination_subfolder")
                        model_type = task_data.get("model_type", "Checkpoint")
                        expected_size = task_data.get("expected_size")

                        logger.info(f"Resuming download: {task_id}")

                        # Determine target path for disk progress checking
                        from common_lib.paths import IMAGE_MODELS_ROOT

                        target_path = IMAGE_MODELS_ROOT / dest_folder

                        # Resume in background
                        def resume_download():
                            try:
                                import time

                                event_bus.publish(
                                    task_id,
                                    {
                                        "task_id": task_id,
                                        "status": "resuming",
                                        "progress": 0,
                                        "model_id": model_id,
                                        "version_id": version_id,
                                        "expected_size": expected_size,
                                    },
                                )

                                # Start disk progress checker
                                last_disk_size = 0

                                def disk_progress_check():
                                    nonlocal last_disk_size
                                    while True:
                                        # Find the downloaded file in target directory
                                        if target_path.exists():
                                            files = list(target_path.glob("*"))
                                            for f in files:
                                                if (
                                                    f.is_file()
                                                    and f.stat().st_size > 1024
                                                ):
                                                    current_size = f.stat().st_size
                                                    if current_size != last_disk_size:
                                                        last_disk_size = current_size
                                                        if (
                                                            expected_size
                                                            and expected_size > 0
                                                        ):
                                                            disk_progress = int(
                                                                (
                                                                    current_size
                                                                    / expected_size
                                                                )
                                                                * 100
                                                            )
                                                            event_bus.publish(
                                                                task_id,
                                                                {
                                                                    "task_id": task_id,
                                                                    "status": "downloading",
                                                                    "progress": disk_progress,
                                                                    "downloaded": current_size,
                                                                    "total": expected_size,
                                                                    "expected_size": expected_size,
                                                                    "source": "disk",
                                                                },
                                                            )
                                        time.sleep(2)

                                disk_thread = threading.Thread(
                                    target=disk_progress_check, daemon=True
                                )
                                disk_thread.start()

                                dler = downloader_factory(
                                    mirror_service=container.mirror_service
                                )
                                target_path = dler.download_model(
                                    model_id=model_id,
                                    version_id=version_id,
                                    file_id=file_id,
                                    destination_subfolder=dest_folder,
                                    model_type=model_type,
                                    progress_callback=lambda d, t: event_bus.publish(
                                        task_id,
                                        {
                                            "task_id": task_id,
                                            "status": "downloading",
                                            "progress": int((d / t * 100))
                                            if t > 0
                                            else 0,
                                            "downloaded": d,
                                            "total": t,
                                        },
                                    ),
                                )

                                event_bus.publish(
                                    task_id,
                                    {
                                        "task_id": task_id,
                                        "status": "completed",
                                        "progress": 100,
                                        "file_path": str(target_path),
                                    },
                                )
                                event_bus.publish(
                                    "__global__",
                                    {
                                        "task_id": task_id,
                                        "status": "completed",
                                        "progress": 100,
                                    },
                                )
                            except Exception as dl_err:
                                logger.error(f"Failed to resume {task_id}: {dl_err}")
                                event_bus.publish(
                                    task_id,
                                    {
                                        "task_id": task_id,
                                        "status": "failed",
                                        "error": str(dl_err),
                                    },
                                )
                            finally:
                                try:
                                    task_file.unlink(missing_ok=True)
                                except:
                                    pass

                        import threading

                        threading.Thread(target=resume_download, daemon=True).start()

                    except Exception as e:
                        logger.error(f"Failed to load task {task_file}: {e}")

                print(f"Startup: Resumed {len(pending_tasks)} downloads in background")
    except Exception as e:
        print(f"Warning: Could not resume downloads: {e}")

    # Start scheduler cron loops
    try:
        from app.modules.scheduler.service import get_scheduler_service

        scheduler = get_scheduler_service()
        scheduler.load_from_disk()
        await scheduler.start_all()
        print("Startup: Scheduler loaded jobs and started active cron loops")
    except Exception as e:
        print(f"Warning: Could not start scheduler: {e}")

    yield
    # Shutdown
    engine.dispose()

    # Stop scheduler cron loops
    try:
        from app.modules.scheduler.service import get_scheduler_service

        scheduler = get_scheduler_service()
        await scheduler.stop_all()
        print("Shutdown: Scheduler stopped, all jobs persisted")
    except Exception as e:
        print(f"Warning: Could not stop scheduler: {e}")


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

    # Response Caching Middleware (Phase 1 — centralized HTTP response cache)
    if os.environ.get("RESPONSE_CACHE_ENABLED", "true").lower() == "true":
        from app.middleware.response_cache import ResponseCacheMiddleware

        app.add_middleware(ResponseCacheMiddleware)
        print("Startup: Response Cache Middleware enabled")

    # Register Custom OpenAPI
    app.openapi = lambda: custom_openapi(app)

    # Global auth dependency — applied to ALL routes at once.
    # When DEV_MODE=True, auth is bypassed entirely.
    # When DEV_MODE=False, every request must be authenticated.
    global_deps = [Depends(get_current_active_user)] if not settings.DEV_MODE else []

    # Include Routers
    print(f"Startup: Including Common router with prefix: {settings.API_V1_STR}")
    app.include_router(
        common_router, prefix=settings.API_V1_STR, dependencies=global_deps
    )
    print(f"Startup: Including Auth router with prefix: {settings.API_V1_STR}/auth")
    app.include_router(
        auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"]
    )  # Auth handles its own security
    print(
        f"Startup: Including Sessions router with prefix: {settings.API_V1_STR}/sessions"
    )
    app.include_router(
        sessions_router,
        prefix=f"{settings.API_V1_STR}/sessions",
        tags=["Sessions"],
        dependencies=global_deps,
    )

    # Module Routers
    print(f"Startup: Including Roles router with prefix: {settings.API_V1_STR}/roles")
    app.include_router(
        roles_router,
        prefix=f"{settings.API_V1_STR}/roles",
        tags=["Roles"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Permissions router with prefix: {settings.API_V1_STR}/permissions"
    )
    app.include_router(
        permissions_router,
        prefix=f"{settings.API_V1_STR}/permissions",
        tags=["Permissions"],
        dependencies=global_deps,
    )
    print(f"Startup: Including Users router with prefix: {settings.API_V1_STR}/users")
    app.include_router(
        users_router,
        prefix=f"{settings.API_V1_STR}/users",
        tags=["Users"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Projects router with prefix: {settings.API_V1_STR}/projects"
    )
    app.include_router(
        projects_router,
        prefix=f"{settings.API_V1_STR}/projects",
        tags=["Projects"],
        dependencies=global_deps,
    )

    print(f"Startup: Including Hooks router with prefix: {settings.API_V1_STR}/hooks")
    app.include_router(
        hooks_router,
        prefix=f"{settings.API_V1_STR}/hooks",
        tags=["Hooks"],
        dependencies=global_deps,
    )

    # Entities & Orchestration
    print(
        f"Startup: Including Entities Registry router with prefix: {settings.API_V1_STR}/entities/registry"
    )
    app.include_router(
        entities_router,
        prefix=f"{settings.API_V1_STR}/entities/registry",
        tags=["Entities Registry"],
        dependencies=global_deps,
    )
    print(f"Startup: Including Agents router with prefix: {settings.API_V1_STR}/agents")
    app.include_router(
        agents_router,
        prefix=f"{settings.API_V1_STR}/agents",
        tags=["Agents (Management)"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Pipelines router with prefix: {settings.API_V1_STR}/agents/pipelines"
    )
    app.include_router(
        pipeline_router,
        prefix=f"{settings.API_V1_STR}/agents/pipelines",
        tags=["Pipelines"],
        dependencies=global_deps,
    )
    print(f"Startup: Including Policy router with prefix: {settings.API_V1_STR}/agents")
    app.include_router(
        policy_router,
        prefix=f"{settings.API_V1_STR}/agents",
        tags=["Policy & Multi-Agent"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Workflows router with prefix: {settings.API_V1_STR}/workflows"
    )
    app.include_router(
        workflows_router,
        prefix=f"{settings.API_V1_STR}/workflows",
        tags=["Workflows"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Workflow Collaboration router with prefix: {settings.API_V1_STR}/workflows"
    )
    app.include_router(
        collaboration_router,
        prefix=f"{settings.API_V1_STR}/workflows",
        tags=["Workflow Collaboration"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Workflow Observability router with prefix: {settings.API_V1_STR}/workflows/observability"
    )
    app.include_router(
        observability_router,
        prefix=f"{settings.API_V1_STR}/workflows/observability",
        tags=["Workflow Observability"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Workflow Configs router with prefix: {settings.API_V1_STR}/workflow-configs"
    )
    app.include_router(
        workflow_configs_router,
        prefix=f"{settings.API_V1_STR}/workflow-configs",
        tags=["Workflow Configs"],
        dependencies=global_deps,
    )

    # Failure Analysis API (Phase 1 — root cause analysis + pattern matching)
    from app.modules.workflows.routes.failure_analysis import (
        router as failure_analysis_router,
    )

    print(
        f"Startup: Including Failure Analysis router with prefix: {settings.API_V1_STR}/workflows"
    )
    app.include_router(
        failure_analysis_router,
        prefix=f"{settings.API_V1_STR}/workflows",
        tags=["Workflow Failure Analysis"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Combinatorial router with prefix: {settings.API_V1_STR}/workflows/combinatorial"
    )
    app.include_router(
        combinatorial_router,
        prefix=f"{settings.API_V1_STR}/workflows/combinatorial",
        tags=["Workflow Combinatorial"],
        dependencies=global_deps,
    )
    print(f"Startup: Including Tools router with prefix: {settings.API_V1_STR}/tools")
    app.include_router(
        tools_router,
        prefix=f"{settings.API_V1_STR}/tools",
        tags=["Tools"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including Models Hub router with prefix: {settings.API_V1_STR}/models"
    )
    app.include_router(
        models_router,
        prefix=f"{settings.API_V1_STR}/models",
        tags=["Models Hub"],
        dependencies=global_deps,
    )
    print(
        f"Startup: Including External Models router with prefix: {settings.API_V1_STR}/models/external"
    )
    app.include_router(
        external_models_router,
        prefix=f"{settings.API_V1_STR}/models/external",
        tags=["External Models Discovery"],
        dependencies=global_deps,
    )

    # SAM3 Segmentation
    print(f"Startup: Including SAM3 router with prefix: {settings.API_V1_STR}/sam3")
    app.include_router(
        sam3_router,
        prefix=f"{settings.API_V1_STR}/sam3",
        tags=["SAM3 Segmentation"],
        dependencies=global_deps,
    )

    # New Vision API
    from app.modules.vision.routes import router as vision_router

    print(f"Startup: Including Vision router with prefix: {settings.API_V1_STR}/vision")
    app.include_router(
        vision_router,
        prefix=f"{settings.API_V1_STR}/vision",
        tags=["Vision"],
        dependencies=global_deps,
    )

    # Filters API (Image filter CRUD, presets, pipeline execution)
    from app.modules.filters.routes import router as filters_router

    print(
        f"Startup: Including Filters router with prefix: {settings.API_V1_STR}/filters"
    )
    app.include_router(
        filters_router,
        prefix=f"{settings.API_V1_STR}/filters",
        tags=["Filters"],
        dependencies=global_deps,
    )

    # Nodes Catalog API (Unified node definitions for Nodes Studio)
    from app.modules.nodes.routes import router as nodes_router

    print(f"Startup: Including Nodes router with prefix: {settings.API_V1_STR}/nodes")
    app.include_router(
        nodes_router,
        prefix=f"{settings.API_V1_STR}",
        tags=["Nodes"],
        dependencies=global_deps,
    )

    # Wildcards API
    print(
        f"Startup: Including Wildcards router with prefix: {settings.API_V1_STR}/vision/wildcards"
    )
    app.include_router(
        wildcards_router,
        prefix=f"{settings.API_V1_STR}/vision",
        tags=["Wildcards"],
        dependencies=global_deps,
    )

    # Prompts Import API (PromptHero scraping + saving)
    from app.modules.prompts.routes import router as prompts_router

    print(
        f"Startup: Including Prompts router with prefix: {settings.API_V1_STR}/prompts"
    )
    app.include_router(
        prompts_router,
        prefix=f"{settings.API_V1_STR}/prompts",
        tags=["Prompts"],
        dependencies=global_deps,
    )

    # Configs API (Industrialized Vision Presets)
    from app.modules.configs.routes import router as configs_router

    print(f"Startup: Including Configs router with prefix: {settings.API_V1_STR}")
    app.include_router(
        configs_router,
        prefix=f"{settings.API_V1_STR}",
        tags=["Configs"],
        dependencies=global_deps,
    )

    # SD Models Registry
    from app.modules.sd_models.routes import router as sd_models_router

    print(f"Startup: Including SD Models router with prefix: {settings.API_V1_STR}")
    app.include_router(
        sd_models_router,
        prefix=f"{settings.API_V1_STR}",
        tags=["SD Models"],
        dependencies=global_deps,
    )

    # New Audio API
    from app.modules.audio.routes import router as audio_router

    print(f"Startup: Including Audio router with prefix: {settings.API_V1_STR}/audio")
    app.include_router(
        audio_router,
        prefix=f"{settings.API_V1_STR}/audio",
        tags=["Audio & TTS"],
        dependencies=global_deps,
    )

    # MCP (Model Context Protocol)
    from app.mcp.routes import router as mcp_router

    print(f"Startup: Including MCP router with prefix: {settings.API_V1_STR}/mcp")
    app.include_router(
        mcp_router,
        prefix=f"{settings.API_V1_STR}/mcp",
        tags=["MCP Ecosystem"],
        dependencies=global_deps,
    )

    # SOTA Debug (Simulating Parallel Spans)
    from app.modules.debug.routes import router as debug_router

    print(f"Startup: Including Debug router with prefix: {settings.API_V1_STR}/debug")
    app.include_router(
        debug_router,
        prefix=f"{settings.API_V1_STR}/debug",
        tags=["Debug Simulator"],
        dependencies=global_deps,
    )

    # DataForge & Grid Persistence
    print(
        f"Startup: Including DataForge router with prefix: {settings.API_V1_STR}/data-forge"
    )
    app.include_router(
        data_forge_router,
        prefix=f"{settings.API_V1_STR}/data-forge",
        tags=["DataForge Simulation"],
        dependencies=global_deps,
    )
    print(f"Startup: Including Grid router with prefix: {settings.API_V1_STR}/grid")
    app.include_router(
        grid_router,
        prefix=f"{settings.API_V1_STR}/grid",
        tags=["Grid Customization Persistence"],
        dependencies=global_deps,
    )

    # Plugin Management System
    print(
        f"Startup: Including Plugins router with prefix: {settings.API_V1_STR}/plugins"
    )
    app.include_router(
        plugins_router,
        prefix=f"{settings.API_V1_STR}/plugins",
        tags=["Plugin Management"],
        dependencies=global_deps,
    )

    # DAW - Digital Audio Workstation
    print(f"Startup: Including DAW router with prefix: {settings.API_V1_STR}/daw")
    app.include_router(
        daw_router,
        prefix=f"{settings.API_V1_STR}/daw",
        tags=["DAW"],
        dependencies=global_deps,
    )

    # Unified Memory API (blocks + marketplace + cognitive memory + all operations)
    print(f"Startup: Including Memory router with prefix: {settings.API_V1_STR}/memory")
    app.include_router(
        cognitive_memory_router,
        prefix=f"{settings.API_V1_STR}/memory",
        tags=["Memory"],
        dependencies=global_deps,
    )

    # Marketplace API (agents, skills, workflows, hardware, blocks)
    print(
        f"Startup: Including Marketplace router with prefix: {settings.API_V1_STR}/marketplace"
    )
    from app.modules.marketplace.routes import router as marketplace_router

    app.include_router(
        marketplace_router,
        prefix=f"{settings.API_V1_STR}/marketplace",
        tags=["Marketplace"],
        dependencies=global_deps,
    )

    # Graph (AGE) API
    print(f"Startup: Including Graph router with prefix: {settings.API_V1_STR}/graph")
    from app.modules.graph.routes import router as graph_router

    app.include_router(
        graph_router,
        prefix=f"{settings.API_V1_STR}/graph",
        tags=["Graph"],
        dependencies=global_deps,
    )

    # Sync API
    print(f"Startup: Including Sync router with prefix: {settings.API_V1_STR}/sync")
    from app.modules.sync.routes.index import router as sync_router

    app.include_router(
        sync_router,
        prefix=f"{settings.API_V1_STR}/sync",
        tags=["Sync"],
        dependencies=global_deps,
    )

    # DIP Ingestion API
    print(
        f"Startup: Including DIP Ingestion router with prefix: {settings.API_V1_STR}/dip/ingestion"
    )
    app.include_router(
        dip_ingestion_router,
        prefix=settings.API_V1_STR,
        tags=["dip/ingestion"],
    )

    # DIP Pipeline API
    print(
        f"Startup: Including DIP Pipeline router with prefix: {settings.API_V1_STR}/dip/pipeline"
    )
    app.include_router(
        pipeline_router,
        prefix=settings.API_V1_STR,
        tags=["dip/pipeline"],
    )

    # Notification SSE API
    print(
        f"Startup: Including Notification router with prefix: {settings.API_V1_STR}/notifications"
    )
    app.include_router(
        notification_router,
        prefix=settings.API_V1_STR,
        tags=["notifications"],
    )

    # Integration API (cross-module triggers, hooks, rules, observability)
    from app.modules.integration.routes import router as integration_router

    print(
        f"Startup: Including Integration router with prefix: {settings.API_V1_STR}/integration"
    )
    app.include_router(
        integration_router,
        prefix=settings.API_V1_STR,
        tags=["integration"],
    )

    # Scheduler API (cron jobs, scheduled workflows)
    from app.modules.scheduler.routes import router as scheduler_router
    from app.modules.scheduler.workflows import register_all_workflows

    register_all_workflows()
    print("Startup: Registered scheduler workflow executors")

    print(
        f"Startup: Including Scheduler router with prefix: {settings.API_V1_STR}/scheduler"
    )
    app.include_router(
        scheduler_router,
        prefix=settings.API_V1_STR,
        tags=["scheduler"],
    )

    # SD News API (article archive and browsing)
    from app.modules.scheduler.news_routes import router as sd_news_router

    print(
        f"Startup: Including SD News router with prefix: {settings.API_V1_STR}/sd-news"
    )
    app.include_router(
        sd_news_router,
        prefix=settings.API_V1_STR,
        tags=["sd-news"],
    )

    # Dashboard API
    print(
        f"Startup: Including Dashboard router with prefix: {settings.API_V1_STR}/dashboard"
    )
    app.include_router(
        dashboard_router,
        prefix=f"{settings.API_V1_STR}/dashboard",
        tags=["dashboard"],
    )

    # System API
    print(f"Startup: Including System router with prefix: {settings.API_V1_STR}/system")
    app.include_router(
        system_router,
        prefix=f"{settings.API_V1_STR}/system",
        tags=["System"],
        dependencies=global_deps,
    )

    # Response Cache Admin API (Phase 1)
    from fastapi import APIRouter, Depends
    from app.modules.common.types.index import APIResponse

    _cache_router = APIRouter()

    @_cache_router.get("/cache/response/stats")
    async def _get_response_cache_stats():
        from app.middleware.response_cache import get_cache_stats

        return APIResponse(
            data=get_cache_stats(), message="Response cache stats retrieved"
        )

    @_cache_router.post("/cache/response/clear")
    async def _clear_response_cache():
        from app.middleware.response_cache import clear_response_cache

        success = clear_response_cache()
        return APIResponse(data={"success": success}, message="Response cache cleared")

    print(
        f"Startup: Including Response Cache admin router with prefix: {settings.API_V1_STR}/system"
    )
    app.include_router(
        _cache_router,
        prefix=f"{settings.API_V1_STR}/system",
        tags=["System"],
        dependencies=global_deps,
    )

    print(
        f"Startup: Including File Browser router with prefix: {settings.API_V1_STR}/file-browser"
    )
    app.include_router(
        file_browser_router,
        prefix=settings.API_V1_STR,
        tags=["file-browser"],
    )

    print(
        f"Startup: Including Macro router with prefix: {settings.API_V1_STR}/file-browser/macros"
    )
    app.include_router(
        macro_router,
        prefix=settings.API_V1_STR + "/file-browser",
        tags=["macros"],
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
    from common_lib.modules.ai_models.domain.exceptions import ModelNotFoundError
    from app.core.exceptions import model_not_found_exception_handler

    app.add_exception_handler(ModelNotFoundError, model_not_found_exception_handler)
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
