import os
import sys
import time
import json
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
from common_lib.modules.observability import initialize_logging, initialize_tracing

initialize_logging()
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Request, Response
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

            # Seed RBAC roles and permissions
            try:
                from common_lib.modules.rbac.service import seed_roles
                from sqlmodel import Session as SQLSession

                with SQLSession(engine) as rbac_session:
                    result = seed_roles(rbac_session)
                    print(
                        f"RBAC seeded: {result['permissions']} permissions, {result['roles']} roles"
                    )
            except Exception as se:
                import traceback

                print(f"Warning: RBAC seeding failed: {se}")
                traceback.print_exc()

            # Seed built-in themes from themes.json into DB
            try:
                from common_lib.modules.settings.service import theme_service
                from sqlmodel import Session as SQLSession

                with SQLSession(engine) as seed_session:
                    result = theme_service.seed_from_json(seed_session)
                    print(f"Startup: {result.get('message', 'Themes seeded')}")
            except Exception as se:
                import traceback

                print(f"Warning: Theme seeding failed: {se}")
                traceback.print_exc()

            try:
                from common_lib.modules.keys_management.service import (
                    KeyManagementService,
                )

                seeded_m, seeded_f = KeyManagementService().seed_proxy_catalog()
                print(f"Proxy catalog seeded: {seeded_m} models, {seeded_f} fallbacks.")

                seeded_k = KeyManagementService().seed_from_config()
                if seeded_k:
                    print(f"Auto-seeded {seeded_k} API keys from config.ini.")

                # Seed Human-in-the-Loop (HITL) seed data
                from common_lib.modules.governance.hitl.service import get_hitl_service

                get_hitl_service()._load_seed_data()
                print("HITL Governance seed data loaded.")
            except Exception as se:
                print(f"Warning: Proxy catalog, key, or HITL seeding failed: {se}")

            # Seed 20 popular connector definitions
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
                            # Update existing record — keeps seed.py as single source of truth
                            for field, value in connector_data.items():
                                setattr(existing, field, value)
                            updated_count += 1
                        else:
                            record = ConnectorRecord(**connector_data)
                            seed_session.add(record)
                            new_count += 1
                    if new_count or updated_count:
                        seed_session.commit()
                        print(
                            f"Connectors seeded: {new_count} new, {updated_count} updated"
                        )
                    else:
                        print("Connectors: all already up to date")
            except Exception as se:
                print(f"Warning: Connector seeding failed: {se}")

            # Seed default dev connection for Atlassian (DEV_MODE only)
            if settings.DEV_MODE:
                try:
                    from common_lib.modules.plugins.connectors.models.db import (
                        ConnectionRecord,
                    )
                    from common_lib.modules.keys_management.service import (
                        KeyManagementService,
                    )
                    from common_lib.modules.keys_management.schemas import (
                        ApiKeyCreate,
                        KeyProvider,
                    )
                    from sqlmodel import Session as SQLSession
                    from sqlmodel import select

                    with SQLSession(engine) as dev_session:
                        existing_dev = dev_session.exec(
                            select(ConnectionRecord).where(
                                ConnectionRecord.connector_id == "atlassian",
                                ConnectionRecord.label == "Atlassian Dev Default",
                            )
                        ).first()

                        if not existing_dev:
                            # Create a placeholder API key
                            import uuid

                            kms = KeyManagementService()
                            key_result = kms.create_key(
                                ApiKeyCreate(
                                    provider=KeyProvider.ATLASSIAN,
                                    label="Atlassian Dev Default Key",
                                    key_value="dev-placeholder-api-key",
                                    enabled=True,
                                )
                            )
                            key_id = key_result.id

                            dev_conn = ConnectionRecord(
                                id=str(uuid.uuid4()),
                                connector_id="atlassian",
                                user_id="default",
                                auth_scheme="api_key",
                                key_id=key_id,
                                status="active",
                                label="Atlassian Dev Default",
                                form_data={
                                    "atlassian_instance_url": "https://your-domain.atlassian.net",
                                    "atlassian_email": "dev@example.com",
                                },
                                metadata_json={
                                    "seeded": True,
                                    "source": "startup",
                                },
                            )
                            dev_session.add(dev_conn)
                            dev_session.commit()
                            print(
                                f"Seeded default Atlassian dev connection (key_id={key_id})"
                            )
                        else:
                            print("Atlassian dev connection already exists")
                except Exception as se:
                    print(f"Warning: Default connection seeding failed: {se}")

            # --- SEED: Connections YAML Data ---
            try:
                from common_lib.modules.connectors.bootstrap import seed_connections_from_yaml
                from sqlmodel import Session as SQLSession
                with SQLSession(engine) as seed_session:
                    seed_connections_from_yaml(seed_session)
            except Exception as conn_se:
                print(f"Warning: Connections seeding from YAML failed: {conn_se}")

            # --- SEED: Node registry (all @node functions) -> node_definitions ---
            try:
                from common_lib.modules.image_processing.nodes_registry.startup import (
                    sync_nodes_on_startup,
                )

                synced = sync_nodes_on_startup()
                print(f"Node registry synced: {synced} nodes discovered")
            except Exception as se:
                print(f"Warning: Node registry sync failed: {se}")

            # --- SEED: Knowledge Hub initial data ---
            try:
                from common_lib.modules.knowledge_hub.seed_data import seed_all
                from sqlmodel import Session as KHSession

                with KHSession(engine) as kh_seed:
                    counts = seed_all(kh_seed)
                    print(
                        f"Startup: Knowledge Hub seeded: "
                        f"{counts['source_types']} source types, "
                        f"{counts['source_configs']} configs, "
                        f"{counts['pipelines']} pipelines, "
                        f"{counts['packets']} packets, "
                        f"{counts['projects']} projects"
                    )
            except Exception as kh_se:
                print(f"Warning: Knowledge Hub seeding failed: {kh_se}")

            # --- SEED: Rules Engine default rules ---
            try:
                from common_lib.modules.rules_engine.definition.registry import (
                    seed_default_rules,
                )

                seeded_rules = seed_default_rules()
                if seeded_rules:
                    print(
                        f"Startup: Seeded {seeded_rules} default rules into the rules engine"
                    )
                else:
                    print("Startup: Default rules already seeded")

                # --- SYNC: DB-persisted rules into in-memory engine ---
                from common_lib.modules.integration.services.governance_rules_service import (
                    GovernanceRulesService as RuleEngineService,
                )
                from sqlmodel import Session as _RE_Session

                with _RE_Session(engine) as _re_session:
                    service = RuleEngineService()
                    synced = service.sync_to_engine(_re_session)
                    if synced:
                        print(
                            f"Startup: Synced {synced} DB rules into the rules engine"
                        )
                    else:
                        print("Startup: No new DB rules to sync into the rules engine")
            except Exception as re_err:
                print(f"Warning: Rules engine seed/sync failed: {re_err}")

            # --- SEED: Integration module configs ---
            try:
                from common_lib.modules.integration.services.config_service import (
                    get_integration_config_service,
                )
                from sqlmodel import Session as SQLSession

                with SQLSession(engine) as seed_ic_session:
                    svc = get_integration_config_service()
                    count = svc.seed_default_modules(session=seed_ic_session)
                    if count:
                        print(f"Startup: Seeded {count} integration module configs")
                    else:
                        print("Startup: Integration module configs already seeded")

                    # --- SEED: Integration sample pipelines ---
                    pipeline_count = svc.seed_default_pipelines(session=seed_ic_session)
                    if pipeline_count:
                        print(
                            f"Startup: Seeded {pipeline_count} integration sample pipelines"
                        )
                    else:
                        print("Startup: Integration sample pipelines already seeded")

                    # --- AUTO-ACTIVATE: Minimal Pipeline ---
                    # Only activate if no pipeline is currently active
                    active_pipeline = svc.get_active_pipeline(session=seed_ic_session)
                    if active_pipeline is None:
                        minimal = svc.list_pipelines(session=seed_ic_session)
                        if minimal:
                            # Find the Minimal Pipeline (first seeded)
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
                                    print(
                                        "Startup: Auto-activated Minimal Pipeline "
                                        f"({result.get('modules_updated', 0)} modules updated)"
                                    )
                                else:
                                    print(
                                        "Startup: Failed to auto-activate Minimal "
                                        f"Pipeline: {result.get('error')}"
                                    )
            except Exception as ic_se:
                print(f"Warning: Integration module config seeding failed: {ic_se}")

            # --- REGISTER: RIP Tools ---
            try:
                from common_lib.modules.integration.adapters.tools import (
                    RIPToolsAdapter,
                )

                adapter = RIPToolsAdapter()
                registered = await adapter.register_rip_tools()
                if registered:
                    print(
                        f"Startup: Registered {len(registered)} RIP tools: "
                        f"{[t['name'] for t in registered]}"
                    )
                else:
                    print("Startup: RIP tools already registered")
            except Exception as rip_se:
                print(f"Warning: RIP tool registration failed: {rip_se}")

            # --- SEED: Observability YAML Data ---
            try:
                from common_lib.modules.observability.bootstrap import seed_observability_from_yaml
                from sqlmodel import Session as SQLSession
                with SQLSession(engine) as seed_session:
                    seed_observability_from_yaml(seed_session)
            except Exception as obs_se:
                print(f"Warning: Observability seeding from YAML failed: {obs_se}")

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

    # --- SEED: Self-learning sample configs ---
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
                now = (
                    __import__("datetime")
                    .datetime.now(__import__("datetime").timezone.utc)
                    .replace(tzinfo=None)
                )
                _rows: list[ComponentConfigRecord] = []

                # ── Simple: Quick Starter ──
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

                # ── Medium: Balanced Learner ──
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

                # ── Complex: Full Autopilot ──
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
                    f"Startup: Seeded {len(_rows)} self-learning config rows across 3 sample instances"
                )
            else:
                print("Startup: Self-learning sample configs already seeded")
    except Exception as se:
        print(f"Warning: Self-learning config seeding failed: {se}")

    # --- SYNC: Import all entities from file system to database ---
    if not settings.SKIP_REGISTRY_SYNC:
        print("Startup: Synchronizing file system entities to database...")
        try:
            from app.core.common_lib_integration import sync_manager, common_memory

            # --- SYNC: AI Models Registry ---
            from common_lib.modules.ai_models.container import AIModelsContainer

            AIModelsContainer().seed_defaults()
            print("AI Model Registry synchronized.")

            # --- SYNC: Embedding Model Registry ---
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
        from common_lib.modules.scheduler.service import get_scheduler_service

        scheduler = get_scheduler_service()
        scheduler.load_from_disk()
        await scheduler.start_all()
        print("Startup: Scheduler loaded jobs and started active cron loops")
    except Exception as e:
        print(f"Warning: Could not start scheduler: {e}")

    # Start periodic decay loop task (interval live-configurable from config.ini / API)
    decay_task = None
    try:
        import asyncio
        from common_lib.modules.memory.config import get_config as _gmcfg

        _init_decay = _gmcfg().decay_interval_seconds
        logger.info(f"Periodic memory decay interval configured to {_init_decay}s")

        async def decay_periodic_loop():
            await asyncio.sleep(15)
            while True:
                try:
                    from app.modules.memories.dependencies import get_memory_service

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

        decay_task = asyncio.create_task(decay_periodic_loop())
        print(
            f"Startup: Periodic memory decay task started (interval={_init_decay}s, live-updatable)"
        )
    except Exception as e:
        print(f"Warning: Could not start periodic memory decay task: {e}")

    # Start periodic compaction loop task (interval live-configurable from config.ini / API)
    compaction_task = None
    try:
        import asyncio
        from common_lib.modules.memory.config import get_config as _gmcfg

        _init_compact = _gmcfg().compaction_interval_seconds
        logger.info(
            f"Periodic memory compaction interval configured to {_init_compact}s"
        )

        async def compaction_periodic_loop():
            await asyncio.sleep(30)
            while True:
                try:
                    from app.modules.memories.dependencies import get_memory_service

                    svc = get_memory_service()
                    await svc.check_and_run_autocompaction(threshold=15)
                except Exception as e:
                    logger.error(
                        f"Error in periodic memory compaction background task: {e}"
                    )
                from common_lib.modules.memory.config import get_config as _gmcfg2

                await asyncio.sleep(_gmcfg2().compaction_interval_seconds)

        compaction_task = asyncio.create_task(compaction_periodic_loop())
        print(
            f"Startup: Periodic memory compaction task started (interval={_init_compact}s, live-updatable)"
        )
    except Exception as e:
        print(f"Warning: Could not start periodic memory compaction task: {e}")

    # --- Initialize TurboVec adapter if enabled ---
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

    yield
    # Shutdown
    engine.dispose()

    # Stop periodic decay loop task
    if decay_task:
        try:
            decay_task.cancel()
            await decay_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Warning: Error canceling periodic memory decay task: {e}")
        print("Shutdown: Periodic memory decay task stopped")

    # Stop periodic compaction loop task
    if compaction_task:
        try:
            compaction_task.cancel()
            await compaction_task
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Warning: Error canceling periodic memory compaction task: {e}")
        print("Shutdown: Periodic memory compaction task stopped")

    # Stop scheduler cron loops
    try:
        from common_lib.modules.scheduler.service import get_scheduler_service

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

    # Observability Middleware (outermost — capture correlation context first)
    from common_lib.modules.observability.constants import (
        ENABLE_OBSERVABILITY_EXTENSIONS,
    )

    if ENABLE_OBSERVABILITY_EXTENSIONS:
        from common_lib.modules.observability.middleware import (
            CorrelationMiddleware,
            RequestLoggingMiddleware,
        )

        # P1-5 FIX: Activate middleware — previously commented out while the startup
        # message claimed they were enabled. Both are now actually registered.
        app.add_middleware(CorrelationMiddleware)
        app.add_middleware(RequestLoggingMiddleware)
        print("Startup: Correlation and Request Logging middleware enabled")
    else:
        print(
            "Startup: Observability extensions disabled (ENABLE_OBSERVABILITY_EXTENSIONS=False)"
        )

    # Register all events in the observability catalog
    from common_lib.modules.observability.events import register_all_events

    register_all_events()
    print("Startup: All observability events registered")

    # Wire AI trackers into execution paths
    from common_lib.modules.observability.wiring import wire_all

    wire_all()
    print("Startup: AI Tracker wiring complete")

    # Register SLO defaults
    from common_lib.modules.observability.slos import SLOManager

    SLOManager.register_defaults()
    print("Startup: SLO defaults registered")

    # P0-3 FIX: CORS now uses the explicit allowlist from settings.BACKEND_CORS_ORIGINS.
    # Previously allow_origin_regex="https?://.*" allowed ANY website to make credentialed
    # requests to the API — a high-risk cross-origin attack surface.
    #
    # - Dev: defaults to ["http://localhost:3000", "http://localhost:5173"]
    # - Prod/staging: set BACKEND_CORS_ORIGINS in config.ini or env to the real frontend URL(s)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Tenant-Id",
            "X-Subject-Id",
            "X-Subject-Type",
            "Accept",
            "Cache-Control",
        ],
    )

    # P1-3: Global ingress rate limiter — sliding window keyed by tenant+subject.
    # Limits per group: auth=10, generation=20, download=5, streaming=10, default=120 (per minute).
    # Configure via RATE_LIMIT_* env vars; disable with RATE_LIMIT_ENABLED=false.
    from app.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware)
    print("Startup: Rate Limit Middleware enabled")

    # Response Caching Middleware — disabled by default (P0-2 fix).
    # Enable only after identity-aware isolation tests pass.
    if os.environ.get("RESPONSE_CACHE_ENABLED", "false").lower() == "true":
        from app.middleware.response_cache import ResponseCacheMiddleware

        app.add_middleware(ResponseCacheMiddleware)
        print("Startup: Response Cache Middleware enabled")

    # Authz Middleware — extracts subject identity from JWT/headers for every request
    from app.modules.auth.middleware.authz import AuthzMiddleware

    app.add_middleware(AuthzMiddleware)
    print("Startup: Authz Middleware enabled")

    # Control Center Activity Logging — automatically logs every API request
    try:
        from app.modules.control_center.middleware.activity_logger import (
            ActivityLoggingMiddleware,
        )

        app.add_middleware(ActivityLoggingMiddleware)
        print("Startup: Control Center Activity Logging middleware enabled")
    except Exception as cc_err:
        print(f"Warning: Control Center Activity Logging middleware failed: {cc_err}")

    # Register Custom OpenAPI
    app.openapi = lambda: custom_openapi(app)

    # Global auth dependency — applied to ALL routes at once.
    # When DEV_MODE=True, auth is bypassed entirely.
    # When DEV_MODE=False, every request must be authenticated.
    global_deps = [Depends(get_current_active_user)] if not settings.DEV_MODE else []

    # P2-1: All routers registered via declarative registry.
    # See app/core/routers.py for the full list.
    from app.core.routers import register_routers

    register_routers(app, settings.API_V1_STR, global_deps)

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
        service_error_handler,
    )

    app.add_exception_handler(NexusException, nexus_exception_handler)
    from common_lib.modules.ai_models.domain.exceptions import ModelNotFoundError
    from app.core.exceptions import model_not_found_exception_handler

    app.add_exception_handler(ModelNotFoundError, model_not_found_exception_handler)
    from common_lib.modules.exceptions import ServiceError

    app.add_exception_handler(ServiceError, service_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    from pydantic import ValidationError

    app.add_exception_handler(ValidationError, pydantic_exception_handler)
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Observability — health endpoint registered directly, not via common_lib
    from common_lib.modules.observability import (
        get_health_data,
        initialize_tracing,
    )

    @app.get("/health", include_in_schema=False)
    @app.get("/readyz", include_in_schema=False)
    async def health_check():
        return get_health_data()

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
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
