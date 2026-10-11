import os
import sys
import time
import logging
from pathlib import Path

# --- BOOTSTRAP: Ensure development common_lib takes precedence ---
REPO_ROOT = Path(__file__).parent.parent.parent.resolve()
COMMON_LIB_SRC = str(REPO_ROOT / "Python Libs" / "common_lib" / "src")
if COMMON_LIB_SRC not in sys.path:
    sys.path.insert(0, COMMON_LIB_SRC)
    print(f"!!! [BOOTSTRAP] Injecting dev common_lib: {COMMON_LIB_SRC}")

# Silence the common 'triton' traceback on Windows before importing any torch-related libs
os.environ["XFORMERS_FORCE_DISABLE_TRITON"] = "1"

# Lazy import: set_global_precision() is called only when a CUDA/local model is deployed,
# to avoid initializing PyTorch CUDA context at startup when using cloud API providers.

# --- OBSERVABILITY INITIALIZATION ---
from common_lib.modules.observability import initialize_logging

initialize_logging()
logger = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.core.settings import get_settings
from app.core.openapi import custom_openapi

# Router imports moved to app/core/routers.py (P2-1 — declarative registry)
from fastapi import Depends
from app.modules.auth.dependencies import get_current_active_user

settings = get_settings()

import sys
import time
from sqlalchemy import text
from common_lib.modules.data_storage.database.connection import engine

# Startup logging helper with color codes - only critical messages go to console, rest to debug
import sys

# ANSI color codes
class _StartupColors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

# Only enable colors if stdout is a TTY
if sys.stdout.isatty():
    _colors = _StartupColors()
else:
    # Disable colors if not a TTY
    for attr in dir(_StartupColors):
        if not attr.startswith('_'):
            setattr(_StartupColors, attr, '')

def _startup_info(msg: str):
    """Log critical startup info to console (green)."""
    print(f"{_StartupColors.GREEN}[STARTUP]{_StartupColors.RESET} {msg}", flush=True)

def _startup_warn(msg: str):
    """Log startup warnings to console (yellow)."""
    print(f"{_StartupColors.YELLOW}[STARTUP WARN]{_StartupColors.RESET} {msg}", flush=True)

def _startup_error(msg: str):
    """Log startup errors to console (red)."""
    print(f"{_StartupColors.RED}[STARTUP ERROR]{_StartupColors.RESET} {msg}", flush=True)

def _startup_debug(msg: str):
    """Log startup debug info (only visible with DEBUG log level)."""
    logger.debug(f"[STARTUP] {msg}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Minimal synchronous startup - only critical operations.
    All non-critical operations run in background tasks.
    """
    # ─── Critical: MCP tool warmup, deferred routers, seeding ───
    # All handled by the single post-bind orchestrator thread (spawned below
    # via _spawn_background_tasks): Phase A mounts deferred routers, Phase B
    # triggers the MCP @node scan, Phase C seeds sequentially. Nothing heavy
    # runs inline here so the server binds immediately.

    # ─── Critical: Database connection & init_db ───
    max_retries = 4
    retry_interval = 2

    for attempt in range(max_retries):
        try:
            _startup_info(f"Verifying database connection (Attempt {attempt + 1}/{max_retries})...")
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            _startup_info("Database connection established successfully.")

            from common_lib.modules.data_storage.database.connection import init_db

            # Register metadata BEFORE init_db()
            from common_lib.modules.project_management.init_db import get_pm_metadata
            from common_lib.modules.secrets_manager.init_db import get_sm_metadata
            import common_lib.modules.open_code_review.models  # noqa: F401

            get_pm_metadata()
            get_sm_metadata()

            init_db()
            _startup_info("Database initialized and models registered.")
            break
        except Exception as e:
            if attempt < max_retries - 1:
                _startup_warn(f"Database connection failed. Retrying in {retry_interval}s...")
                _startup_debug(f"Error: {e}")
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

    # ─── Post-bind orchestrator (single thread, delayed, sequential) ───
    # Sync router mounting already ran in create_app(); deferred entries were
    # stashed on app.state there. The orchestrator mounts them (Phase A),
    # triggers the MCP scan (Phase B), then seeds sequentially (Phase C).
    # Do NOT re-mount or spawn extra import threads here — duplicate import
    # races are what made startup slow.
    _spawn_background_tasks(app)

    # ─── Critical: Exception handlers & OpenAPI ───
    app.openapi = lambda: custom_openapi(app)
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
        service_error_handler,
    )

    app.add_exception_handler(NexusException, nexus_exception_handler)
    from common_lib.modules.ai_models.domain.exceptions import ModelNotFoundError
    from app.core.exceptions import model_not_found_exception_handler
    from common_lib.modules.exceptions import ServiceError

    app.add_exception_handler(ModelNotFoundError, model_not_found_exception_handler)
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    from pydantic import ValidationError

    app.add_exception_handler(ValidationError, pydantic_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Health endpoints are registered in create_app — do NOT duplicate them
    # here (duplicate routes bloat the route table and confuse /openapi.json).

    # Yield control - app is now ready to serve requests!
    yield

    # ─── Shutdown: cleanup background tasks ───
    pass


def _spawn_background_tasks(app: FastAPI):
    """Spawn the single post-bind orchestrator thread (see run_sync_background)."""
    import asyncio
    import threading

    def run_sync_background():
        """Single-threaded post-bind orchestrator (sequential by design).

        Parallel import-heavy threads thrash the GIL and the DB pool, which
        made startup 5-10x slower AND slowed the first API calls. Everything
        here is sequential in one daemon thread:

        Phase A: mount deferred routers (API completeness first).
        Phase B: trigger MCP @node warmup (the ~100s import scan).
        Phase C: seeding / sync / wiring, one step at a time.

        Env knobs:
          NEXUS_BG_DELAY_SECONDS (default "20"): quiet period after bind so
            the server answers health + first requests uncontended.
          NEXUS_SKIP_STARTUP_SEEDING="1": skip Phase C entirely (dev iteration).
            Router mounting (Phase A) and MCP warmup (Phase B) still run.
        """
        import time

        try:
            delay = float(os.getenv("NEXUS_BG_DELAY_SECONDS", "20"))
        except ValueError:
            delay = 20.0
        if delay > 0:
            time.sleep(delay)

        # ── Phase A: deferred routers (API completeness first) ──
        try:
            from app.core.routers import register_routers_background
            from app.core.router_hot_mount import mount_context

            deferred = getattr(app.state, "_deferred_router_entries", None) or []
            ctx = mount_context(app)
            if deferred and ctx:
                api_prefix, global_deps = ctx
                register_routers_background(app, api_prefix, global_deps, deferred)
                _startup_info(f"Mounted {len(deferred)} deferred routers (API complete)")
            else:
                _startup_debug("No deferred routers to mount")
        except Exception as e:
            _startup_warn(f"Deferred router mount failed: {e}")
        finally:
            app.state.deferred_mount_complete = True

        # ── Phase A.5: pre-warm OpenAPI cache ──
        # First /openapi.json generation over ~6k routes takes 30s+; warming
        # the cache here (background) makes the first real /docs call instant.
        # Mounting already invalidated the cache per-router, and nothing below
        # mutates routes, so the warmed document stays valid.
        try:
            t0 = time.time()
            app.openapi()
            _startup_info(f"OpenAPI cache warmed in {time.time() - t0:.1f}s")
        except Exception as e:
            _startup_warn(f"OpenAPI pre-warm failed (first /docs call will be slow): {e}")

        # ── Phase B: MCP @node warmup (the big import scan, runs in its own thread) ──
        try:
            from app.mcp.server import start_node_tool_warmup

            if start_node_tool_warmup():
                _startup_info("warming @node -> MCP tool registry in background")
            else:
                _startup_debug("@node MCP tool registration skipped/complete")
        except Exception as e:
            _startup_warn(f"dynamic @node MCP registration skipped: {e}")

        # ── Phase C: seeding / sync / wiring (sequential, no thread pools) ──
        if os.getenv("NEXUS_SKIP_STARTUP_SEEDING", "0") == "1":
            _startup_info("Skipping startup seeding (NEXUS_SKIP_STARTUP_SEEDING=1)")
            return

        _seed_rbac_and_themes()
        _seed_keys_and_hitl()
        _seed_connectors()
        _seed_connections_yaml()
        _sync_nodes_registry()
        _seed_knowledge_hub()
        _seed_rules_engine()
        _seed_integration_configs()
        _register_rip_tools()
        _wire_integration_bridges()
        _seed_observability_yaml()
        _seed_self_learning_configs()
        _sync_registry_from_files()
        _seed_ui_nodes()
        _resume_model_downloads()
        _start_scheduler()
        _create_pm_tables()
        _create_sm_tables()
        _start_memory_tasks()
        _init_turbovec()
        _load_plugins()

        _startup_debug("Background startup tasks completed")

    def run_async_background():
        """Run all async background operations."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_async_background_tasks())
        finally:
            loop.close()

    def _seed_rbac_and_themes():
        # Seed RBAC
        try:
            from common_lib.modules.rbac.service import seed_roles
            from sqlmodel import Session as SQLSession

            with SQLSession(engine) as rbac_session:
                result = seed_roles(rbac_session)
                _startup_debug(f"RBAC seeded: {result['permissions']} permissions, {result['roles']} roles")
        except Exception as se:
            _startup_warn(f"RBAC seeding failed: {se}")

        # Seed themes
        try:
            from common_lib.modules.settings.service import theme_service
            from sqlmodel import Session as SQLSession

            with SQLSession(engine) as seed_session:
                result = theme_service.seed_from_json(seed_session)
                _startup_debug(f"Startup: {result.get('message', 'Themes seeded')}")
        except Exception as se:
            _startup_warn(f"Theme seeding failed: {se}")

    def _seed_keys_and_hitl():
        try:
            from common_lib.modules.secrets_manager.keys_management.service import (
                KeyManagementService,
            )

            seeded_m, seeded_f = KeyManagementService().seed_proxy_catalog()
            _startup_debug(f"Proxy catalog seeded: {seeded_m} models, {seeded_f} fallbacks.")

            seeded_k = KeyManagementService().seed_from_config()
            if seeded_k:
                _startup_debug(f"Auto-seeded {seeded_k} API keys from config.ini.")

            from common_lib.modules.governance.hitl.approval_service import (
                get_hitl_service,
            )

            get_hitl_service()._load_seed_data()
            _startup_debug("HITL Governance seed data loaded.")
        except Exception as se:
            _startup_warn(f"Proxy catalog, key, or HITL seeding failed: {se}")

    def _seed_connectors():
        try:
            from app.modules.connectors.seed import get_connector_seeds
            from common_lib.modules.plugins.connectors.models.db import (
                ConnectorRecord,
            )
            from sqlmodel import Session as SQLSession

            with SQLSession(engine) as seed_session:
                new_count = 0
                updated_count = 0
                for connector_data in get_connector_seeds():
                    existing = seed_session.get(
                        ConnectorRecord, connector_data["id"]
                    )
                    if existing:
                        for field, value in connector_data.items():
                            setattr(existing, field, value)
                        updated_count += 1
                    else:
                        record = ConnectorRecord(**connector_data)
                        seed_session.add(record)
                        new_count += 1
                if new_count or updated_count:
                    seed_session.commit()
                    _startup_debug(f"Connectors seeded: {new_count} new, {updated_count} updated")
                else:
                    _startup_debug("Connectors: all already up to date")
        except Exception as se:
            _startup_warn(f"Connector seeding failed: {se}")

    def _seed_connections_yaml():
        try:
            from common_lib.modules.plugins.connectors.bootstrap import (
                seed_connections_from_yaml,
            )
            from sqlmodel import Session as SQLSession

            with SQLSession(engine) as seed_session:
                seed_connections_from_yaml(seed_session)
        except Exception as conn_se:
            _startup_warn(f"Connections seeding from YAML failed: {conn_se}")

    def _sync_nodes_registry():
        try:
            from common_lib.modules.image_processing.nodes_registry.startup import (
                sync_nodes_on_startup,
            )

            synced = sync_nodes_on_startup()
            _startup_debug(f"Node registry synced: {synced} nodes discovered")
        except Exception as se:
            _startup_warn(f"Node registry sync failed: {se}")

    def _seed_knowledge_hub():
        try:
            from common_lib.modules.knowledge_engine.knowledge_hub.seed_data import (
                seed_all,
            )
            from sqlmodel import Session as KHSession

            with KHSession(engine) as kh_seed:
                counts = seed_all(kh_seed)
                _startup_info(
                    f"Knowledge Hub seeded: "
                    f"{counts['source_types']} source types, "
                    f"{counts['source_configs']} configs, "
                    f"{counts['pipelines']} pipelines, "
                    f"{counts['packets']} packets, "
                    f"{counts['projects']} projects"
                )
        except Exception as kh_se:
            _startup_warn(f"Knowledge Hub seeding failed: {kh_se}")

    def _seed_rules_engine():
        try:
            from common_lib.modules.governance.rules_engine.definition.registry import (
                seed_default_rules,
            )

            seeded_rules = seed_default_rules()
            if seeded_rules:
                _startup_debug(f"Seeded {seeded_rules} default rules into the rules engine")
            else:
                _startup_debug("Default rules already seeded")

            from common_lib.modules.integration.services.governance_rules_service import (
                GovernanceRulesService as RuleEngineService,
            )
            from sqlmodel import Session as _RE_Session

            with _RE_Session(engine) as _re_session:
                service = RuleEngineService()
                synced = service.sync_to_engine(_re_session)
                if synced:
                    _startup_debug(f"Synced {synced} DB rules into the rules engine")
                else:
                    _startup_debug("No new DB rules to sync into the rules engine")
        except Exception as re_err:
            _startup_warn(f"Rules engine seed/sync failed: {re_err}")

    def _seed_integration_configs():
        try:
            from common_lib.modules.integration.services.config_service import (
                get_integration_config_service,
            )
            from sqlmodel import Session as SQLSession

            with SQLSession(engine) as seed_ic_session:
                svc = get_integration_config_service()
                count = svc.seed_default_modules(session=seed_ic_session)
                if count:
                    _startup_debug(f"Seeded {count} integration module configs")
                else:
                    _startup_debug("Integration module configs already seeded")

                pipeline_count = svc.seed_default_pipelines(session=seed_ic_session)
                if pipeline_count:
                    _startup_debug(f"Seeded {pipeline_count} integration sample pipelines")
                else:
                    _startup_debug("Integration sample pipelines already seeded")

                active_pipeline = svc.get_active_pipeline(session=seed_ic_session)
                if active_pipeline is None:
                    minimal = svc.list_pipelines(session=seed_ic_session)
                    if minimal:
                        minimal_pipeline = next(
                            (p for p in minimal if p.name == "Minimal Pipeline"),
                            None,
                        )
                        if minimal_pipeline:
                            result = svc.apply_pipeline(
                                minimal_pipeline.id,
                                session=seed_ic_session,
                            )
                            if result.get("success"):
                                _startup_info(
                                    "Auto-activated Minimal Pipeline "
                                    f"({result.get('modules_updated', 0)} modules updated)"
                                )
                            else:
                                _startup_warn(
                                    f"Failed to auto-activate Minimal Pipeline: {result.get('error')}"
                                )
        except Exception as ic_se:
            _startup_warn(f"Integration module config seeding failed: {ic_se}")

    def _register_rip_tools():
        try:
            from common_lib.modules.integration.adapters.tools import (
                RIPToolsAdapter,
            )

            adapter = RIPToolsAdapter()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            registered = loop.run_until_complete(adapter.register_rip_tools())
            if registered:
                _startup_debug(
                    f"Registered {len(registered)} RIP tools: "
                    f"{[t['name'] for t in registered]}"
                )
            else:
                _startup_debug("RIP tools already registered")
            loop.close()
        except Exception as rip_se:
            _startup_warn(f"RIP tool registration failed: {rip_se}")

    def _wire_integration_bridges():
        try:
            from common_lib.modules.integration.loader import wire_all_bridges

            wire_all_bridges()
            _startup_debug("Integration bridges wired (RIP, memory, data pipeline)")
        except Exception as bridge_we:
            _startup_warn(f"Integration bridge wiring failed: {bridge_we}")

    def _seed_observability_yaml():
        try:
            from common_lib.modules.observability.bootstrap import (
                seed_observability_from_yaml,
            )
            from sqlmodel import Session as SQLSession

            with SQLSession(engine) as seed_session:
                seed_observability_from_yaml(seed_session)
        except Exception as obs_se:
            _startup_warn(f"Observability seeding from YAML failed: {obs_se}")

    def _seed_self_learning_configs():
        try:
            from app.modules.knowledge.models import ComponentConfigRecord
            from common_lib.modules.data_storage.database.connection import (
                engine as _sl_engine,
            )
            from sqlmodel import Session as _SLSession, select as _sl_select

            with _SLSession(_sl_engine) as _sl_seed:
                existing = _sl_seed.exec(
                    _sl_select(ComponentConfigRecord).where(
                        ComponentConfigRecord.instance_id == "sl_sample_simple"
                    )
                ).first()
                if not existing:
                    from datetime import datetime
                    now = datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                    _rows = []

                    # Simple: Quick Starter
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_simple",
                            category="full",
                            config_data={
                                "name": "Quick Starter",
                                "description": "Minimal config with core quality logging and scorer.",
                                "tags": ["beginner", "minimal"],
                                "variant": "v1",
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_simple",
                            category="qualityLog",
                            config_data={
                                "enabled": True,
                                "log_dir": "",
                                "enabled_fields": [
                                    "query",
                                    "result_count",
                                    "latency_ms",
                                    "precision",
                                    "recall",
                                ],
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_simple",
                            category="scorer",
                            config_data={"decay_rate": 0.1, "min_samples": 1},
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_simple",
                            category="failure",
                            config_data={
                                "latency_threshold_ms": 500,
                                "min_severity": "low",
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )

                    # Medium: Balanced Learner
                    _full_cfg = {
                        "name": "Balanced Learner",
                        "description": "Mid-tier config with meta-reasoning, belief revision, and conflict resolution.",
                        "tags": ["intermediate", "adaptive"],
                        "variant": "v1",
                    }
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="full",
                            config_data=_full_cfg,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="qualityLog",
                            config_data={
                                "enabled": True,
                                "log_dir": "",
                                "enabled_fields": [
                                    "query",
                                    "retrieval_plan",
                                    "result_count",
                                    "latency_ms",
                                    "precision",
                                    "recall",
                                    "user_feedback",
                                    "user_rating",
                                    "methods_used",
                                    "error",
                                ],
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="autoEvolve",
                            config_data={"enabled": True, "interval": 100},
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="scorer",
                            config_data={"decay_rate": 0.15, "min_samples": 3},
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="failure",
                            config_data={
                                "latency_threshold_ms": 300,
                                "min_severity": "medium",
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="reasoner",
                            config_data={
                                "short_query_threshold": 5,
                                "enable_hyde_suggestion": True,
                                "latency_weight": 0.8,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="belief",
                            config_data={
                                "confidence_threshold": 0.6,
                                "use_moving_average": True,
                                "constant_learning_rate": 0.1,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_medium",
                            category="conflict",
                            config_data={
                                "strategy": "auto",
                                "min_confidence_gap": 0.2,
                                "min_source_trust_gap": 0.15,
                                "enable_auto_resolution": True,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )

                    # Complex: Full Autopilot
                    _full_cfg2 = {
                        "name": "Full Autopilot",
                        "description": "All 9 subsystems enabled with evolution branching and pruning.",
                        "tags": ["advanced", "production", "autopilot"],
                        "variant": "v4",
                    }
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="full",
                            config_data=_full_cfg2,
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="qualityLog",
                            config_data={
                                "enabled": True,
                                "log_dir": "/var/log/retrieval",
                                "enabled_fields": [
                                    "query",
                                    "retrieval_plan",
                                    "result_count",
                                    "latency_ms",
                                    "precision",
                                    "recall",
                                    "user_feedback",
                                    "user_rating",
                                    "methods_used",
                                    "error",
                                ],
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="autoEvolve",
                            config_data={"enabled": True, "interval": 50},
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="scorer",
                            config_data={"decay_rate": 0.2, "min_samples": 5},
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="failure",
                            config_data={
                                "latency_threshold_ms": 200,
                                "min_severity": "high",
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="reasoner",
                            config_data={
                                "short_query_threshold": 3,
                                "enable_hyde_suggestion": True,
                                "latency_weight": 1.5,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="belief",
                            config_data={
                                "confidence_threshold": 0.7,
                                "use_moving_average": True,
                                "constant_learning_rate": 0.05,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="conflict",
                            config_data={
                                "strategy": "auto",
                                "min_confidence_gap": 0.15,
                                "min_source_trust_gap": 0.1,
                                "enable_auto_resolution": True,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="branching",
                            config_data={
                                "enable_branching": True,
                                "diversity_weight": 0.6,
                                "max_branches": 5,
                                "specialization_threshold": 0.8,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    _rows.append(
                        ComponentConfigRecord(
                            instance_id="sl_sample_complex",
                            category="pruner",
                            config_data={
                                "min_importance": 0.3,
                                "max_age_hours": 48,
                                "enable_user_review": False,
                                "auto_prune_threshold": 0.5,
                            },
                            created_at=now,
                            updated_at=now,
                        )
                    )

                    for _r in _rows:
                        _sl_seed.add(_r)
                    _sl_seed.commit()
                    print(
                        )
                else:
                    print("Startup: Self-learning sample configs already seeded")
        except Exception as se:
            print(f"Warning: Self-learning config seeding failed: {se}")

    def _sync_registry_from_files():
        if settings.SKIP_REGISTRY_SYNC:
            print("Startup: Skipping registry sync (SKIP_REGISTRY_SYNC=True)")
            return

        print("Startup: Synchronizing file system entities to database...")
        try:
            from app.core.common_lib_integration import sync_manager, common_memory

            from common_lib.modules.ai_models.container import AIModelsContainer

            AIModelsContainer().seed_defaults()
            print("AI Model Registry synchronized.")

            try:
                from sqlmodel import create_engine, Session
                from common_lib.modules.data_storage.database.constants import (
                    DEFAULT_DB_URL,
                )
                from common_lib.modules.knowledge_engine.embedding.registry import (
                    init_registry,
                )

                _engine = create_engine(os.getenv("DATABASE_URL", DEFAULT_DB_URL))
                with Session(_engine) as _session:
                    init_registry(_session)
                print("Embedding Model Registry synchronized.")
            except Exception as ei:
                print(f"Warning: Embedding registry sync failed: {ei}")

            report = sync_manager.sync_all_from_files()

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

    def _seed_ui_nodes():
        if settings.SKIP_REGISTRY_SYNC:
            return
        try:
            from common_lib.templates.node_definitions.loader import seed_ui_nodes_to_db

            seeded = seed_ui_nodes_to_db(common_memory)
            if seeded:
                print(f"Startup: Seeded {seeded} UI node definitions to database")
        except Exception as e:
            print(f"Warning: UI node seed failed: {e}")

    def _resume_model_downloads():
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

                            from common_lib.paths import IMAGE_MODELS_ROOT

                            target_path = IMAGE_MODELS_ROOT / dest_folder

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

                                    last_disk_size = 0

                                    def disk_progress_check():
                                        nonlocal last_disk_size
                                        while True:
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

    def _start_scheduler():
        try:
            from common_lib.modules.core_infrastructure.scheduler.service import (
                get_scheduler_service,
            )

            scheduler = get_scheduler_service()
            scheduler.load_from_disk()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scheduler.start_all())
            loop.close()
            print("Startup: Scheduler loaded jobs and started active cron loops")
        except Exception as e:
            print(f"Warning: Could not start scheduler: {e}")

    def _create_pm_tables():
        try:
            from common_lib.modules.project_management.init_db import create_pm_tables

            create_pm_tables(engine)
            print("Startup: Project Management tables created/verified")
        except Exception as e:
            print(f"Warning: PM table creation failed: {e}")

    def _create_sm_tables():
        try:
            from common_lib.modules.secrets_manager.init_db import create_sm_tables

            create_sm_tables(engine)
            print("Startup: Secrets Manager tables created/verified")
        except Exception as e:
            print(f"Warning: SM table creation failed: {e}")

    def _start_memory_tasks():
        import asyncio

        # Decay task
        try:
            from common_lib.modules.memory.config import get_config as _gmcfg

            _init_decay = _gmcfg().decay_interval_seconds
            logger.info(f"Periodic memory decay interval configured to {_init_decay}s")

            async def decay_periodic_loop():
                await asyncio.sleep(15)
                while True:
                    try:
                        from app.core.memory_service import get_memory_service

                        svc = get_memory_service()
                        logger.info(
                            "Executing periodic memory decay cycle background task..."
                        )
                        await svc.run_decay_cycle()
                    except Exception as e:
                        logger.error(
                            f"Error in periodic memory decay cycle background task: {e}"
                        )
                    from common_lib.modules.memory.config import get_config as _gmcfg2

                    await asyncio.sleep(_gmcfg2().decay_interval_seconds)

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.create_task(decay_periodic_loop())
            loop.run_forever()
        except Exception as e:
            print(f"Warning: Could not start periodic memory decay task: {e}")

    def _init_turbovec():
        try:
            vector_backend = os.getenv("VECTOR_BACKEND", "auto")
            if vector_backend in ("turbovec", "auto"):
                from common_lib.modules.memory.service import get_memory_service

                svc = get_memory_service()
                if svc and not svc.turbovec_adapter:
                    from common_lib.vectorstores.factory import VectorStoreFactory

                    factory = VectorStoreFactory(
                        {
                            "vector_backend": "turbovec",
                            "dim": int(os.getenv("EMBEDDING_DIMENSION", "768")),
                            "bit_width": int(os.getenv("TURBOVEC_BIT_WIDTH", "2")),
                            "turbovec_index_path": os.getenv(
                                "TURBOVEC_INDEX_PATH", "/data/turbovec"
                            ),
                        }
                    )
                    if factory._turbovec_available():
                        adapter = factory.create(vector_backend="turbovec")
                        svc.set_turbovec_adapter(adapter)
                        print(
                            f"Startup: TurboVec vector store initialized (dim={adapter.dim}, bit_width={adapter.bit_width})"
                        )
                    else:
                        print("Startup: TurboVec not available (pip install turbovec)")
        except Exception as e:
            print(f"Startup: TurboVec initialization skipped: {e}")

    def _load_plugins():
        try:
            from common_lib.modules.orchestration.plugin import PluginContext, PluginLoader

            plugin_ctx = PluginContext(name="platform")

            # Code signing: read key from env; if set, all plugins verified on boot
            _plugin_signing_key = os.environ.get("PLUGIN_SIGNING_KEY", "")
            plugin_loader = PluginLoader(
                plugin_ctx, signing_key=_plugin_signing_key or None
            )

            # Resolve platform.yml path
            _common_lib_src = (
                Path(__file__).parent.parent / "Python Libs" / "common_lib" / "src"
            )
            _platform_yml = (
                _common_lib_src / "common_lib" / "configs" / "plugins" / "platform.yml"
            )

            if _platform_yml.exists():
                plugin_loader.load_from_yaml(str(_platform_yml))
                loaded_count = len(plugin_loader._plugins)
                loaded_names = list(plugin_loader._plugins.keys())
                print(
                    f"Startup: Plugin system loaded {loaded_count} plugins: {', '.join(loaded_names[:10])}{'...' if loaded_count > 10 else ''}"
                )
            else:
                print(
                    f"Warning: platform.yml not found at {_platform_yml}. Plugin system loaded without platform config."
                )
        except Exception as e:
            print(f"Startup: Plugin system initialization skipped: {e}")

    async def _async_background_tasks():
        # Any async operations that need to run after app is ready
        pass

    # Start sync background thread
    threading.Thread(target=run_sync_background, daemon=True, name="startup-bg-sync").start()

    # Schedule async background tasks on the event loop (will run when loop starts)
    @app.on_event("startup")
    async def _startup_async_tasks():
        await _async_background_tasks()


def create_app() -> FastAPI:
    # ── Per-instance feature config ──────────────────────────────────────────
    # MUST be the first thing create_app() does. Everything after this point can
    # observe or act on flag state: register_routers() (line ~1519) prunes
    # ROUTER_DEFINITIONS, and the MCP warmup in `lifespan` calls
    # discover_nodes(), which prunes the node list. Applying the config later would
    # let both read stale state and prune the wrong modules.
    #
    # `load_feature_config` raises FeatureConfigError on an unreadable or structurally
    # invalid document. That is deliberate and it propagates: a refused start is loud,
    # whereas silently falling back to all-on would boot a server with modules the
    # operator believes are gone. See docs/duplication-audit/FEATURE-CONFIG.md.
    from common_lib.modules.common.feature_config import (
        FeatureConfigError,
        load_feature_config,
    )

    try:
        _feature_report = load_feature_config()
    except FeatureConfigError as _feature_error:
        print("")
        print("=" * 78)
        print("FATAL: invalid per-instance feature config — refusing to start.")
        print("=" * 78)
        print(str(_feature_error))
        print(
            "\nSet PLATFORM_FEATURE_CONFIG to a valid document, or delete it to fall "
            "back to the shipped reference (all flags on)."
        )
        print("See docs/duplication-audit/FEATURE-CONFIG.md for the schema.")
        raise

    print(
        f"[FeatureConfig] {_feature_report['config_path']} "
        f"(source={_feature_report['source']}): "
        f"{_feature_report['applied']} flag value(s) applied, "
        f"{_feature_report['disabled_count']} disabled — "
        f"modules off: "
        f"{', '.join(_feature_report['disabled_modules']) or 'none'}"
    )

    # ── @node instance registry ──────────────────────────────────────────────
    # MUST run after `load_feature_config()` and before `register_routers()` and the
    # MCP warmup's `discover_nodes()`. Two reasons, both about ordering:
    #
    #   1. AFTER the feature config, because each wiring entry is gated on the
    #      pruning flag for its module. Constructing instances for a module the
    #      operator switched off is exactly the waste the pruning work exists to
    #      avoid, and the wiring reads the same `is_module_enabled` predicate the
    #      router/node pruners use so the two can never disagree.
    #   2. BEFORE discovery, because binding happens when the bridge generates a
    #      handler for a dotted `Class.method` node. Register afterwards and every
    #      node generated during this boot's scan was already built unbound — the
    #      registry would be correct and useless.
    #
    # Resilient by construction: a class that cannot be constructed is logged and
    # skipped, never fatal. See app/core/node_instances.py for the table, the
    # per-request mechanism the refused population needs, and the counts.
    try:
        from app.core.node_instances import register_startup_instances

        _instance_report = register_startup_instances()
        # Structured logger, not print(): golden rule 11. The neighbouring
        # feature-config block predates that rule and still prints; this hunk does not
        # add to the debt.
        logger.info("[NodeInstances] %s", _instance_report.summary())
        if _instance_report.failed:
            logger.warning(
                "[NodeInstances] %d owner(s) left unbound -- their nodes stay "
                "advertised but uncallable: %s",
                len(_instance_report.failed),
                ", ".join(sorted(_instance_report.failed)),
            )
    except Exception as _instance_error:  # noqa: BLE001 - never block the boot
        logger.warning(
            "[NodeInstances] registration had failures (fail-open): %s",
            _instance_error,
        )

    app = FastAPI(
        title="Nexus Platform API",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # NOTE: background work (deferred routers, MCP warmup, seeding) is NOT
    # spawned here. It starts from lifespan via _spawn_background_tasks, after
    # the DB is verified. Spawning import-heavy threads during create_app
    # raced the main thread's own imports and multiplied startup time.
    # ─── Critical: Exception handlers & OpenAPI ───
    app.openapi = lambda: custom_openapi(app)
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
        service_error_handler,
    )

    app.add_exception_handler(NexusException, nexus_exception_handler)
    from common_lib.modules.ai_models.domain.exceptions import ModelNotFoundError
    from app.core.exceptions import model_not_found_exception_handler
    from common_lib.modules.exceptions import ServiceError

    app.add_exception_handler(ModelNotFoundError, model_not_found_exception_handler)
    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    from pydantic import ValidationError

    app.add_exception_handler(ValidationError, pydantic_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Health endpoint
    from common_lib.modules.observability import get_health_data

    @app.get("/health", include_in_schema=False)
    @app.get("/readyz", include_in_schema=False)
    async def health_check():
        return get_health_data()

    @app.get("/v1/models", include_in_schema=False)
    async def v1_models_compat():
        return {"object": "list", "data": []}

    @app.get("/readyz-deep", include_in_schema=False)
    async def readiness_deep():
        """Deep readiness: true only once deferred routers are mounted.

        Poll this (instead of hammering real endpoints) to know when the
        full API surface is live after a restart.
        """
        complete = bool(getattr(app.state, "deferred_mount_complete", False))
        return {
            "ready": complete,
            "deferred_routers_mounted": complete,
            "routes": len(app.routes),
        }

    # ─── Critical: Always-on routers (sync) ───
    # Only the always-on subset mounts here (~8s). Deferred entries are
    # stashed for the post-bind orchestrator (lifespan). No background
    # threads are spawned here — see lifespan.
    global_deps = [Depends(get_current_active_user)] if not settings.DEV_MODE else []
    from app.core.routers import register_routers

    deferred = register_routers(app, settings.API_V1_STR, global_deps, sync_only=True)
    app.state._deferred_router_entries = deferred
    app.state.deferred_mount_complete = False

    # FastMCP SSE transport — enables opencode / MCP clients to connect directly
    from app.mcp.server import mcp_server, wait_for_node_tools

    sse_app = mcp_server.sse_app()

    async def _sse_gated(scope, receive, send):
        """Hold SSE connections until the background @node scan has finished.

        FastMCP enumerates tools per connection, so a client connecting inside
        the warmup window would otherwise see a partial tool list. The wait runs
        in a thread executor so the event loop keeps serving other requests, and
        is bounded by MCP_NODE_TOOLS_WAIT_SECONDS.
        """
        import asyncio

        from app.mcp.routes import _NODE_TOOLS_WAIT_SECONDS

        # wait_for_node_tools returns immediately when the scan has already
        # finished, so no ready-check is needed here.
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None, wait_for_node_tools, _NODE_TOOLS_WAIT_SECONDS
            )
        except Exception:
            pass
        await sse_app(scope, receive, send)

    app.mount(
        "/mcp/transport",
        _sse_gated,
        name="mcp_sse",
    )

    # Plugin Server proxy (port 8081) — frontend hits these and we
    # proxy to the standalone Plugin Server. The frontend doesn't
    # need to know about port 8081.
    try:
        from app.routes.plugin_server_proxy import router as plugin_server_proxy_router

        app.include_router(
            plugin_server_proxy_router,
            prefix="/api/plugin-server",
            tags=["plugin-server"],
        )
    except Exception as _e:
        # Plugin server proxy is optional; don't fail startup
        import logging as _logging

        _logging.getLogger(__name__).warning(
            f"Plugin server proxy router not registered: {_e}"
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

    # Observability — health endpoint registered directly, not via common_lib
    from common_lib.modules.observability import (
        get_health_data,
        initialize_tracing,
    )

    @app.get("/health", include_in_schema=False)
    @app.get("/readyz", include_in_schema=False)
    async def health_check():
        return get_health_data()

    @app.get("/v1/models", include_in_schema=False)
    async def v1_models_compat():
        """OpenAI-compatible models discovery fallback for background health/client checks."""
        return {"object": "list", "data": []}

    initialize_tracing()

    # FastAPI instrumentation (requires app reference) — moved from common_lib
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        pass
    except Exception:
        pass

    # Prometheus auto-instrumentation for HTTP + custom metrics
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(
            app, endpoint="/metrics", include_in_schema=False
        )
    except Exception:
        from common_lib.modules.observability import get_metrics_data

        @app.get("/metrics", include_in_schema=False)
        async def metrics_endpoint():
            return get_metrics_data()

    # NOTE: Knowledge Engine, Governance, Observability Admin, Docs,
    # Knowledge Hub, AuthZ, and Team routers are all registered by
    # register_routers() above via app/core/routers.py (P2-1).

    return app


app = create_app()

if __name__ == "__main__":
    import os
    import uvicorn

    # Worker pool support for production zero-downtime reloads.
    # Set UVICORN_WORKERS=N to run N processes. Each process has
    # its own PluginManager and ReloadGuard singleton, so reloads
    # are per-worker (use POST /api/v1/plugins/reload on each).
    #
    # For a real zero-downtime setup, run a process supervisor
    # (e.g. honcho, supervisord) that can do rolling restarts.
    workers = int(os.environ.get("UVICORN_WORKERS", "1"))
    if workers > 1:
        # reload=True is incompatible with workers>1 in uvicorn
        uvicorn.run(
            "app.main:app",
            host=os.environ.get("UVICORN_HOST", "0.0.0.0"),
            port=int(os.environ.get("UVICORN_PORT", "8000")),
            workers=workers,
        )
    else:
        uvicorn.run(
            app,
            host=os.environ.get("UVICORN_HOST", "0.0.0.0"),
            port=int(os.environ.get("UVICORN_PORT", "8000")),
            reload=os.environ.get("UVICORN_RELOAD", "false").lower() == "true",
        )