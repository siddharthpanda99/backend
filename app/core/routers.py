"""Declarative router registry — P2-1.

All FastAPI routers are defined here as a structured list.
``register_routers(app, api_prefix, global_deps)`` is called once from
``create_app()`` in ``main.py``.

Adding a new module is a one-line change in ROUTER_DEFINITIONS.
Removing or reordering is equally safe — no hidden coupling to main.py body.

Router entry format:
    {
        "router": <APIRouter>,
        "prefix": "<path suffix appended to api_prefix>",
        "tags": ["<OpenAPI tag>"],
        "auth": True | False,   # True  = include global_deps (default)
                                 # False = no auth (e.g. auth endpoints handle their own)
        "module": "<top-level module name>",        # OPTIONAL, additive
        "feature_flag": "<explicit flag path>",     # OPTIONAL, additive
    }

Load-time feature-flag pruning
-------------------------------
``module`` and ``feature_flag`` are optional and purely additive — every existing entry
is valid without them. When present, a router whose module is *explicitly disabled*
(``set_module_enabled("memory", False)``, or ``memory = false`` in
``memory_config.ini``) is not mounted: it serves no requests and does not appear in the
OpenAPI schema. ``feature_flag`` overrides the derived flag path when a router's module
name does not match its flag namespace — e.g. the ``knowledge_hub`` routers map onto the
``knowledge_engine.*`` flag namespace, so they set ``feature_flag`` explicitly.

Entries that declare neither key are always mounted (fail-open): most of the 219 entries
do not, so pruning is opt-in per router and adding the key is the only way to make a
router prunable.

Pruning is driven by the same helpers as node discovery —
``common_lib.modules.common.module_pruning`` — and is fail-open in both directions: an
entry with no ``module``/``feature_flag`` is always mounted, and a module that merely
ships default-False (e.g. ``platform_controls``) is not pruned. If pruning itself raises,
the full unfiltered list is mounted.

See ``docs/duplication-audit/MODULE-PRUNING.md``.
"""

from __future__ import annotations

import logging
from typing import Any, List

from fastapi import FastAPI

from app.core.router_hot_mount import (
    mount_router_entry,
    remember_definitions,
    remember_mount_context,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy loader helpers for heavyweight / late-registered routers
# ---------------------------------------------------------------------------


def _dynamic_workflow_router():
    from app.modules.workflows.routes.dynamic import router

    return router


def _layouts_router():
    from app.routes.layouts import router

    return router


def _cognitive_runtime_router():
    from app.modules.cognitive_runtime.routes import router

    return router


def _flag_change_listener_router():
    from app.core.flag_change_listener import router

    return router


def _data_configs_router():
    from app.modules.workflows.routes.data_configs import router

    return router


def _knowledge_router():
    from app.modules.knowledge.routes import router

    return router


def _alerts_router():
    from app.modules.knowledge_engine.alerts.routes import router

    return router


def _context_acquisition_router():
    from app.modules.knowledge_engine.acquisition.routes import router

    return router


def _compiler_router():
    from app.modules.knowledge_engine.compiler.routes import router

    return router


def _communities_router():
    from app.modules.knowledge_engine.routes.communities import router

    return router


def _knowledge_engine_router():
    from app.modules.knowledge_engine.routes import router

    return router


def _world_model_router():
    from app.modules.knowledge.routes.world_model import router

    return router


def _ontology_router():
    from app.modules.knowledge.routes.ontology import router

    return router


def _governance_router():
    from app.modules.governance.routes import router

    return router


def _obs_admin_router():
    from app.modules.observability.routes import router

    return router


def _docs_router():
    from app.modules.docs.routes import router

    return router


def _authz_router():
    from app.modules.authorization.routes.authz_router import (
        router as authz_full_router,
    )

    return authz_full_router


def _sota_router():
    from app.modules.sota.routes import router

    return router


def _rip_router():
    from app.modules.rip.routes import router

    return router


def _team_router():
    from app.modules.team.routes import router

    return router


def _reporting_router():
    from app.modules.reporting.routes import router

    return router


def _orchestration_router():
    from app.modules.orchestration import router

    return router


def _patterns_router():
    from app.modules.orchestration.patterns_routes import router

    return router


def _drift_router():
    from app.modules.orchestration.drift_routes import router

    return router


def _plugins_router():
    from app.modules.orchestration.plugins_routes import router

    return router


def _search_settings_router():
    from app.modules.orchestration.search_settings_routes import router

    return router


def _kpe_router():
    from app.modules.kpe.routes import router

    return router


def _kimchi_router():
    from app.modules.kimchi import router

    return router


def _ferment_router():
    from app.modules.ferment.routes.router import router

    return router


def _reasoning_router():
    from app.modules.reasoning.routes import router

    return router


def _agentic_pipelines_router():
    from app.modules.agentic_pipelines.routes import router

    return router


def _agentic_os_router():
    from app.modules.agentic_os.routes import router

    return router


def _document_creator_router():
    from app.modules.document_creator.routes.router import router

    return router


def _knowledge_hub_entries(api_prefix: str) -> list:
    """Build router entries for the knowledge_hub multi-router package."""
    from app.modules.knowledge_hub import (
        sources_router,
        pipelines_router,
        packets_router,
        projects_router as kh_projects_router,
        streaming_router,
        collections_router,
    )

    # NOTE: `module` below is the load-time pruning key. These routers live in the
    # `knowledge_hub` module but the *flag namespace* is `knowledge_engine.*`, so the
    # explicit `feature_flag` is what does the work — `module` alone would never match
    # a registered flag. Submodules of knowledge_engine that merely ship default-False
    # (alerts, audit_ledger, extraction, ontology, ...) are NOT pruned: see
    # module_pruning._is_explicitly_disabled. Only an admin action turns these off.
    return [
        {
            "router": sources_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Sources"],
            "auth": True,
            "module": "knowledge_engine",
            "feature_flag": "knowledge_engine",
        },
        {
            "router": pipelines_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Ingestion"],
            "auth": True,
            "module": "knowledge_engine",
            "feature_flag": "knowledge_engine",
        },
        {
            "router": packets_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Packets"],
            "auth": True,
            "module": "knowledge_engine",
            "feature_flag": "knowledge_engine",
        },
        {
            "router": kh_projects_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Projects"],
            "auth": True,
            "module": "knowledge_engine",
            "feature_flag": "knowledge_engine",
        },
        {
            "router": streaming_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Streaming"],
            "auth": True,
            "module": "knowledge_engine",
            "feature_flag": "knowledge_engine",
        },
        {
            "router": collections_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Collections"],
            "auth": True,
            "module": "knowledge_engine",
            "feature_flag": "knowledge_engine",
        },
    ]


def router_prune_candidates(entry: dict) -> List[str]:
    """Flag candidates for a router entry, most specific first.

    An explicit ``feature_flag`` is used alone; otherwise the candidates are
    ``["<module>"]`` plus its dotted ancestors. Returns ``[]`` when the entry declares
    no module, which means "never prune" (fail-open) — the vast majority of entries
    are in that state today and continue to be mounted unconditionally.
    """
    explicit = entry.get("feature_flag")
    if isinstance(explicit, str) and explicit.strip():
        return [explicit.strip()]

    module = entry.get("module")
    if not isinstance(module, str) or not module.strip():
        return []
    module = module.strip()
    parts = [p for p in module.split(".") if p]
    if not parts:
        return []
    return [".".join(parts[:i]) for i in range(len(parts), 0, -1)]


def is_router_enabled(entry: dict) -> bool:
    """Should this router be mounted? Fail-open on every ambiguity."""
    try:
        from common_lib.modules.common.module_pruning import resolve_flag_path

        return resolve_flag_path(router_prune_candidates(entry)) is None
    except Exception:
        logger.warning(
            "Router pruning check failed for %s — mounting it anyway (fail-open)",
            entry.get("tags"),
            exc_info=True,
        )
        return True


def prune_router_definitions(entries: List[dict]) -> List[dict]:
    """Drop routers whose module is explicitly disabled by a feature flag.

    A pruned router is never passed to ``app.include_router``, so it serves no
    requests and contributes no paths to the OpenAPI schema.
    """
    kept = [e for e in entries if is_router_enabled(e)]
    dropped = len(entries) - len(kept)
    if dropped:
        logger.info(
            "Feature-flag pruning: not mounting %d of %d routers (disabled modules)",
            dropped,
            len(entries),
        )
    return kept


def register_routers(app: FastAPI, api_prefix: str, global_deps: List[Any]) -> None:
    """Include all module routers onto ``app`` using the declarative registry.

    Lazy imports are used for heavy modules so that startup path errors
    surface at the correct location rather than at module load time.

    P2-1: Replaces ~600 lines of imperative include_router() calls in main.py
    with a single declarative list that is easy to audit, diff, and extend.
    """
    # -----------------------------------------------------------------
    # Core imports (already at module level in main.py)
    # These are the routers imported at the top of main.py.
    # -----------------------------------------------------------------
    from app.modules.common.routes.index import router as common_router
    from app.modules.auth.routes.index import router as auth_router
    from app.modules.sessions.routes.index import router as sessions_router
    from app.modules.authorization.routes.roles import router as roles_router
    from app.modules.authorization.routes.permissions import (
        router as permissions_router,
    )
    from app.modules.users.routes.users import router as users_router
    from app.modules.agents.routes.index import router as agents_router
    from app.modules.agents.routes.policy_routes import router as policy_router
    from app.modules.agents.routes.task_routes import router as task_router
    from app.modules.agents.routes.profile_routes import router as profile_router
    from app.modules.agents.routes.skill_routes import router as skill_router
    from app.modules.agents.routes.daemon_routes import router as daemon_router
    from app.modules.site_builder.routes import (
        project_router as site_project_router,
        sitemap_router as site_sitemap_router,
        wireframe_router as site_wireframe_router,
        registry_router as site_registry_router,
        theme_router as site_theme_router,
        export_router as site_export_router,
    )
    from app.modules.entities.routes.registry import router as entities_router
    from app.modules.entities.instance_routes import router as entity_instances_router
    from app.modules.workflows.routes.index import router as workflows_router
    from app.modules.workflows.routes.observability import (
        router as observability_router,
    )
    from app.modules.workflows.routes.configs import router as workflow_configs_router
    from app.modules.workflows.routes.collaboration import (
        router as collaboration_router,
    )
    from app.modules.workflows.routes.combinatorial import (
        router as combinatorial_router,
    )
    from app.modules.workflows.routes.failure_analysis import (
        router as failure_analysis_router,
    )
    from app.modules.workflows.routes.compiler import router as workflow_compiler_router
    from app.modules.tools.routes.index import router as tools_router
    from app.modules.memory.routes import router as cognitive_memory_router
    from app.modules.memories.routes.index import router as memories_router
    from app.modules.decision.routes import router as decision_router
    from app.modules.vectorstores.routes import router as vectorstores_router
    from app.modules.models.routes import router as models_router
    from app.modules.models.external_routes import router as external_models_router
    from app.modules.ai_models.routes import router as ai_models_catalog_router
    from app.modules.data_forge.routes import router as data_forge_router
    from app.modules.grid.routes import router as grid_router
    from app.modules.plugins.routes.router import router as plugins_router
    from app.modules.daw.routes import router as daw_router
    from app.modules.hooks.routes import router as hooks_router
    from app.modules.webhooks import router as webhooks_router
    from app.modules.app_builder.forms import router as forms_router
    from app.modules.app_builder.features import router as features_router
    from app.modules.connection_health import router as connection_health_router
    from app.modules.app_builder.ecosystem import router as ecosystem_router
    from app.modules.app_builder import router as builder_router
    from app.modules.dashboard.routes import router as dashboard_router
    from app.modules.system.routes import router as system_router
    from app.modules.app_ops import router as app_ops_router
    from app.modules.settings.routes import router as settings_router
    from app.modules.dip.routes.ingestion import router as dip_ingestion_router
    from app.modules.dip.routes.pipeline import pipeline_router as dip_pipeline_router
    from app.modules.dip.routes.rag import router as dip_rag_router
    from app.modules.dip.routes.kg import router as dip_kg_router
    from app.modules.dip.routes.storage import router as dip_storage_router
    from app.modules.dip.routes.embeddings import router as dip_embeddings_router
    from app.modules.dip.routes.extraction import router as dip_extraction_router
    from app.modules.file_browser import router as file_browser_router

    try:
        from app.modules.file_browser.macro_routes import router as macro_router
    except ImportError:
        macro_router = None  # macro_service not yet implemented
    from app.modules.notification.routes import router as notification_router
    from app.modules.wildcards.routes import router as wildcards_router
    from app.modules.sam3.routes import router as sam3_router
    from app.modules.keys_management import router as keys_router
    from app.modules.keys_management.credentials_routes import (
        router as credentials_router,
    )
    from app.modules.proxy_routing import router as proxy_router
    from app.modules.collage.routes import router as collage_router
    from app.modules.experiments.routes import router as experiments_router
    from app.modules.ext_apps import router as ext_apps_router
    from app.modules.connectors.routes import connector_router, connection_router
    from app.modules.connectors.mcp.server import router as connectors_mcp_router
    from app.modules.plugins.routes import plugin_router

    # Lazy imports for modules not imported at main.py top level
    from app.modules.edit.routes import router as edit_router
    from app.modules.vision.routes import router as vision_router
    from app.modules.face.routes import router as face_router
    from app.modules.influencer.routes import router as influencer_router
    from app.modules.usecases.routes import router as usecases_router
    from app.modules.filters.routes import router as filters_router
    from app.modules.nodes.routes import router as nodes_router
    from app.modules.prompts.routes import router as prompts_router
    from app.modules.prompts_hero.routes import router as prompts_hero_router
    from app.modules.configs.routes import router as configs_router
    from app.modules.sd_models.routes import router as sd_models_router
    from app.modules.audio.routes import router as audio_router
    from app.modules.open_code_review.routes import router as open_code_review_router
    from app.mcp.routes import router as mcp_router
    from app.modules.debug.routes import router as debug_router
    from app.modules.marketplace.routes import router as marketplace_router
    from app.modules.marketplace.routes.audit_routes import (
        router as entity_audit_router,
    )
    from app.modules.creators.routes.router import router as creators_router
    from app.modules.graph.routes import router as graph_router
    from app.modules.app_builder.schema import router as schema_router
    from app.modules.sync.routes.index import router as sync_router
    from app.modules.integration.routes import router as integration_router
    from app.modules.scheduler.routes import router as scheduler_router
    from app.modules.jobs.routes import router as jobs_router
    from app.modules.sandbox import router as sandbox_router
    from app.modules.doc_processing import router as doc_processing_router
    from app.modules.scheduler.routes.news_routes import router as sd_news_router
    from app.modules.prompt_studio.routes import router as prompt_studio_router
    from app.modules.evolver import router as evolver_router
    from app.modules.writing.routes import router as writing_router
    from app.modules.messaging.routes import router as messaging_router
    from app.modules.document_vault import router as document_vault_router

    def _hitl_router():
        from app.modules.hitl.routes import router

        return router

    def _verification_router():
        from app.modules.verification.routes import router

        return router

    def _control_center_router():
        from app.modules.control_center.routes import router

        return router

    def _admin_db_router():
        from app.modules.admin_db.routes import router

        return router

    def _etl_router():
        from app.modules.multi_source_etl.routes import router

        return router

    def _database_connections_router():
        from app.modules.db_studio.database_connections.routes import router

        return router

    def _query_workbench_router():
        from app.modules.db_studio.query_workbench.routes import router

        return router

    def _schema_browser_router():
        from app.modules.db_studio.schema_browser.routes import router

        return router

    def _data_browser_router():
        from app.modules.db_studio.data_browser.routes import router

        return router

    def _visual_designers_router():
        from app.modules.db_studio.visual_designers.routes import router

        return router

    def _ai_copilot_router():
        from app.modules.db_studio.ai_copilot.routes import router

        return router

    def _query_execution_router():
        from app.modules.db_studio.query_execution.routes import router

        return router

    def _data_exchange_router():
        """Lazy-load Import, Export & Data Exchange router."""
        from app.modules.db_studio.data_exchange.routes.router import get_router

        return get_router()

    def _migration_router():
        """Lazy-load Migration & Schema Versioning router."""
        from app.modules.db_studio.migration.routes.router import get_router

        return get_router()

    def _backup_router():
        """Lazy-load Backup, Restore & Snapshot Manager router."""
        from app.modules.db_studio.backup.routes.router import get_router

        return get_router()

    def _performance_router():
        """Lazy-load Performance Profiler & Query Optimizer router."""
        from app.modules.db_studio.performance.routes.router import get_router

        return get_router()

    def _connector_sdk_router():
        from app.modules.db_studio.connector_sdk.routes import router

        return router

    def _capability_registry_router():
        from app.modules.db_studio.capability_registry.routes.router import get_router

        return get_router()

    def _administration_router():
        from app.modules.db_studio.administration.routes.router import get_router

        return get_router()

    def _etl_platform_router():
        """Lazy-load ETL/ELT/Reverse ETL Platform router."""
        from app.modules.db_studio.etl.routes.router import get_router

        return get_router()

    def _data_quality_router():
        """Lazy-load Data Quality & Profiling router."""
        from app.modules.db_studio.data_quality.routes.router import router

        return router

    def _observability_router():
        """Lazy-load Monitoring & Observability router."""
        from app.modules.db_studio.observability.routes.router import router

        return router

    def _security_router():
        """Lazy-load Security, Auth & Secret Management router."""
        from app.modules.db_studio.security.routes.router import router

        return router

    def _security_audit_router():
        """Lazy-load Security Audit Events, DLP & Compliance router."""
        from app.modules.security.routes.security_routes import router

        return router

    def _collaboration_router():
        """Lazy-load RBAC, Teams & Collaboration router."""
        from app.modules.db_studio.collaboration.routes.router import router

        return router

    def _notebook_router():
        """Lazy-load Notebook & Interactive Workspace router."""
        from app.modules.db_studio.notebook.routes.router import router

        return router

    def _knowledge_library_router():
        """Lazy-load Query History, Snippets & Templates router."""
        from app.modules.db_studio.knowledge_library.routes.router import router

        return router

    def _automation_router():
        """Lazy-load Scheduler, Jobs & Automation router."""
        from app.modules.db_studio.automation.routes.router import router

        return router

    def _plugin_marketplace_router():
        """Lazy-load Plugin Marketplace & Extension SDK router."""
        from app.modules.db_studio.plugin_marketplace.routes.router import router

        return router

    def _workspace_environment_router():
        """Lazy-load Workspace, Projects & Environment Management router."""
        from app.modules.db_studio.workspace_environment.routes.router import router

        return router

    def _discovery_router():
        """Lazy-load Search, Catalog & Data Discovery router."""
        from app.modules.db_studio.discovery.routes.router import router

        return router

    def _db_studio_governance_router():
        """Lazy-load Lineage, Governance & Compliance router.

        Distinct from the module-level `_governance_router()` (agent governance).
        This was previously named `_governance_router` and, being nested inside
        register_routers, silently shadowed the module-level one — so the
        /governance mount was serving the db_studio lineage router and the
        19-router app/modules/governance surface was unreachable. Each call
        site now names the router it actually wants.
        """
        from app.modules.db_studio.governance.routes.router import router

        return router

    def _visualization_router():
        """Lazy-load Visualization, Dashboards & Reporting router."""
        from app.modules.db_studio.visualization.routes.router import router

        return router

    def _api_integration_router():
        """Lazy-load API Layer, WebSocket & MCP Integration router."""
        from app.modules.db_studio.api_integration.routes.router import router

        return router

    def _backend_architecture_router():
        """Lazy-load Backend Architecture & Folder Structure router."""
        from app.modules.db_studio.backend_architecture.routes.router import router

        return router

    def _frontend_design_router():
        """Lazy-load Frontend Architecture & Design System router."""
        from app.modules.db_studio.frontend_design.routes.router import router

        return router

    def _unified_triggers_router():
        from app.modules.triggers.routes import router

        return router

    def _cron_schedules_router():
        """Durable cron schedules — thin router over common_lib.modules.triggers.cron.

        A separate router from ``_unified_triggers_router`` so the cron surface
        can evolve without touching that module's existing routes file.
        """
        from app.modules.triggers.cron_routes import router

        return router

    def _unified_hooks_router():
        from app.modules.hooks.routes import router

        return router

    def _unified_rules_router():
        from app.modules.rules.routes import router

        return router

    def _unified_interceptors_router():
        from app.modules.interceptors.routes import router

        return router

    def _chatgpt_mcp_router():
        from app.modules.chatgpt_mcp.routes import router

        return router

    def _iil_router():
        from app.modules.iil.routes import router

        return router

    def _studio_router():
        from app.modules.gpt_builder.routes import router

        return router

    def _scaffolder_router():
        from app.modules.scaffolder.routes import router

        return router

    def _claude_mem_router():
        from common_lib.modules.memory.claude_mem_features.api.routes import router

        return router

    def _autoresearch_router():
        from common_lib.modules.knowledge_engine.autoresearch.api import router

        return router

    def _response_templates_router():
        from common_lib.modules.orchestration.response_templates.api import router

        return router

    def _section_library_router():
        from common_lib.modules.orchestration.response_templates.section_api import (
            router,
        )

        return router

    def _background_tasks_router():
        from common_lib.modules.system.task_runner.backends.script_api import router

        return router

    def _task_runner_router():
        from common_lib.modules.system.task_runner.api import router

        return router

    def _behaviour_router():
        from common_lib.modules.orchestration.behaviour.api import router

        return router

    def _ai_gateway_router():
        from common_lib.modules.ai_gateway.proxy import router

        return router

    def _platform_controls_router():
        # platform_controls — Phase 0 skeleton
        from app.modules.platform_controls.routes import router

        return router

    def _decision_engine_router():
        # Decision Engine (Nexus Decision Fabric) — thin router layer.
        # All business logic lives in common_lib.modules.decision_engine.
        # The router mounts endpoints at /api/v1/decision-engine/;
        # feature-gated by NEXUS_DECISION_FABRIC_ENABLED flag.
        from app.modules.decision_engine.routes import router

        return router

    def _i2w_router():
        # I2W (Instruction-to-Workflow) — Phase 7 surface.
        # Thin router layer; all business logic lives in
        # common_lib.modules.orchestration.instruction_to_workflow.
        # The router mounts 55 endpoints (REST + WS) at /api/v1/i2w/;
        # see docs/08_api_contract.md for the full surface.
        from app.modules.i2w import router

        return router

    def _project_management_router():
        from app.modules.project_management.routes.index import router

        return router

    def _pm_project_routes_router():
        """Canonical project CRUD (field-secured). Alias mount for /api/v1/projects."""
        from app.modules.project_management.routes.project_routes import router

        return router

    def _toolchain_router():
        from app.modules.toolchain import router

        return router

    def _secrets_manager_routers() -> list:
        """Build router entries for the Secrets Manager multi-router package."""
        from app.modules.secrets_manager.routes import (
            vault_router,
            policy_router as sm_policy_router,
            core_router,
            audit_router,
            dynamic_router,
            rotation_router,
            pki_router,
            ssh_router,
            proxy_router as sm_proxy_router,
            kubernetes_router,
            cloud_router,
            seal_router,
            engine_router,
            event_router,
            scanning_router,
            replication_router,
            plugin_router as sm_plugin_router,
            monitoring_router,
            import_export_router,
        )

        return [
            {
                "router": vault_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Vault"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": sm_policy_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Policy"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": core_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Encryption"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": audit_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Audit"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": dynamic_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Dynamic Secrets"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": rotation_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Rotation"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": pki_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — PKI"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": ssh_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — SSH"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": sm_proxy_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Proxy/SDK"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": kubernetes_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Kubernetes"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": cloud_router,
                "prefix": "/secrets",
                "tags": ["Secrets Manager — Cloud"],
                "auth": True,
                "module": "secrets_manager",
            },
            # Self-baked routers — define full /secrets/* paths themselves,
            # so they must be mounted with prefix="" (NOT "/secrets").
            {
                "router": seal_router,
                "prefix": "",
                "tags": ["Secrets Manager — Seal"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": engine_router,
                "prefix": "",
                "tags": ["Secrets Manager — Engines"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": event_router,
                "prefix": "",
                "tags": ["Secrets Manager — Events"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": scanning_router,
                "prefix": "",
                "tags": ["Secrets Manager — Scanning"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": replication_router,
                "prefix": "",
                "tags": ["Secrets Manager — Replication"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": sm_plugin_router,
                "prefix": "",
                "tags": ["Secrets Manager — Plugins"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": monitoring_router,
                "prefix": "",
                "tags": ["Secrets Manager — Monitoring"],
                "auth": True,
                "module": "secrets_manager",
            },
            {
                "router": import_export_router,
                "prefix": "",
                "tags": ["Secrets Manager — Import/Export"],
                "auth": True,
                "module": "secrets_manager",
            },
        ]

    # ----------------------------------------------------------------
    # Declarative registry
    # Each entry maps to a single app.include_router() call.
    # auth=False means the router manages its own security.
    # ----------------------------------------------------------------
    ROUTER_DEFINITIONS = [
        # ── Core / Authless ────────────────────────────────────────
        {"router": common_router, "prefix": "", "tags": ["Common"], "auth": True},
        {
            "router": auth_router,
            "prefix": "/auth",
            "tags": ["Authentication"],
            "auth": False,
        },
        {
            "router": sessions_router,
            "prefix": "/sessions",
            "tags": ["Sessions"],
            "auth": True,
            "module": "sessions",
        },
        # ── Authorization ─────────────────────────────────────────
        {
            "router": roles_router,
            "prefix": "/roles",
            "tags": ["Roles"],
            "auth": True,
            "module": "authorization",
        },
        {
            "router": permissions_router,
            "prefix": "/permissions",
            "tags": ["Permissions"],
            "auth": True,
            "module": "authorization",
        },
        {
            "router": users_router,
            "prefix": "/users",
            "tags": ["Users"],
            "auth": True,
            "module": "users",
        },
        {
            # Legacy /api/v1/projects alias. Previously mounted
            # app.modules.projects.routes.projects — a 5-endpoint strict subset
            # of project_management's 18-endpoint surface, with no
            # field-security filtering and a different list_projects()
            # signature for the same ProjectService. The frontend had zero
            # callers of /api/v1/projects, but the path is public API, so it
            # now resolves to the richer canonical router instead of dying.
            "router": _pm_project_routes_router(),
            "prefix": "/projects",
            "tags": ["Projects"],
            "auth": True,
            "module": "project_management",
        },
        # ── Scaffolder ─────────────────────────────────────────────
        {
            "router": _scaffolder_router(),
            "prefix": "/scaffolder",
            "tags": ["Scaffolder"],
            "auth": True,
            "module": "scaffolder",
        },
        # ── Hooks / Webhooks ───────────────────────────────────────
        {
            "router": hooks_router,
            "prefix": "/hooks",
            "tags": ["Hooks"],
            "auth": True,
            "module": "hooks",
        },
        {
            "router": webhooks_router,
            "prefix": "/webhooks",
            "tags": ["Webhook Manager"],
            "auth": True,
            "module": "webhooks",
        },
        # ── App Builder ────────────────────────────────────────────
        {
            "router": forms_router,
            "prefix": "/forms",
            "tags": ["Form Builder"],
            "auth": True,
            "module": "app_builder",
        },
        {
            "router": features_router,
            "prefix": "/features",
            "tags": ["Feature Picker"],
            "auth": True,
            "module": "app_builder",
        },
        {
            "router": connection_health_router,
            "prefix": "",
            "tags": ["Connection Health"],
            "auth": True,
            "module": "connection_health",
        },
        {
            "router": ecosystem_router,
            "prefix": "/ecosystem",
            "tags": ["App Ecosystem"],
            "auth": True,
            "module": "app_builder",
        },
        {
            "router": builder_router,
            "prefix": "",
            "tags": ["UI Builder"],
            "auth": True,
            "module": "app_builder",
        },
        {
            "router": schema_router,
            "prefix": "/schema",
            "tags": ["Schema Builder"],
            "auth": True,
            "module": "app_builder",
        },
        # ── Entities & Orchestration ───────────────────────────────
        {
            "router": entities_router,
            "prefix": "/entities/registry",
            "tags": ["Entities Registry"],
            "auth": True,
            "module": "entities",
        },
        {
            "router": entity_instances_router,
            "prefix": "/instances",
            "tags": ["Entity Instances"],
            "auth": True,
            "module": "entities",
        },
        {
            "router": agents_router,
            "prefix": "/agents",
            "tags": ["Agents (Management)"],
            "auth": True,
            "module": "agents",
        },
        # NOTE: pipeline_router, policy_router, task_router, profile_router,
        # skill_router and daemon_router are ALL already included inside
        # agents_router (see app/modules/agents/routes/index.py) under their own
        # sub-prefixes — /pipelines, /tasks, /profiles, /skills, /daemons. The
        # bare `/agents` mounts that used to sit here were duplicate paths.
        #
        # They were not merely redundant: each declared a collection root at
        # "/", so all five landed on `GET /api/v1/agents/` and first-match-wins
        # left exactly one reachable. Worse, index.py's own `@router.get("/{id}")`
        # then swallowed the sub-paths, so `GET /api/v1/agents/policies` and
        # `GET /api/v1/agents/available` returned 404 "Agent not found" because
        # Starlette captured them as an agent id. Only the sub-prefixed twins
        # worked. The pipeline_router case was already fixed and documented
        # here; the other four were simply missed.
        # ── Project Management ─────────────────────────────────────
        # NOTE: the PM router is mounted ONCE at /pm (see below). Do NOT add
        # a second mount here — it duplicates every PM route and shadows the
        # core projects module.
        # ── Site Builder ────────────────────────────────────────
        {
            "router": site_project_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder"],
            "auth": True,
            "module": "site_builder",
        },
        {
            "router": site_sitemap_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Sitemap"],
            "auth": True,
            "module": "site_builder",
        },
        {
            "router": site_wireframe_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Wireframe"],
            "auth": True,
            "module": "site_builder",
        },
        {
            "router": site_registry_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Registry"],
            "auth": True,
            "module": "site_builder",
        },
        {
            "router": site_theme_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Themes"],
            "auth": True,
            "module": "site_builder",
        },
        {
            "router": site_export_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Export"],
            "auth": True,
            "module": "site_builder",
        },
        # ── Workflows ─────────────────────────────────────────────
        {
            "router": workflows_router,
            "prefix": "/workflows",
            "tags": ["Workflows"],
            "auth": True,
            "module": "workflows",
        },
        {
            "router": collaboration_router,
            "prefix": "/workflows",
            "tags": ["Workflow Collaboration"],
            "auth": True,
            "module": "workflows",
        },
        {
            "router": observability_router,
            "prefix": "/workflows/observability",
            "tags": ["Workflow Observability"],
            "auth": True,
            "module": "workflows",
        },
        {
            "router": workflow_configs_router,
            "prefix": "/workflow-configs",
            "tags": ["Workflow Configs"],
            "auth": True,
            "module": "workflows",
        },
        {
            "router": failure_analysis_router,
            "prefix": "/workflows",
            "tags": ["Workflow Failure Analysis"],
            "auth": True,
            "module": "workflows",
        },
        {
            "router": combinatorial_router,
            "prefix": "/workflows/combinatorial",
            "tags": ["Workflow Combinatorial"],
            "auth": True,
            "module": "workflows",
        },
        # ── Workflow Compiler (AAR) ────────────────────────────────
        {
            "router": workflow_compiler_router,
            "prefix": "/workflows",
            "tags": ["Workflow Compiler — AAR"],
            "auth": True,
            "module": "workflows",
        },
        # ── Dynamic Workflow Runner (YAML + data-config) ──────────
        {
            "router": _dynamic_workflow_router(),
            "prefix": "/workflows/dynamic",
            "tags": ["Dynamic Workflow Runner"],
            "auth": True,
            "module": "workflows",
        },
        # ── Data Config CRUD (YAML data-config files) ───────────
        {
            "router": _data_configs_router(),
            "prefix": "/data-configs",
            "tags": ["Data Configs"],
            "auth": True,
            "module": "workflows",
        },
        # ── Tools & Models ─────────────────────────────────────────
        {
            "router": tools_router,
            "prefix": "/tools",
            "tags": ["Tools"],
            "auth": True,
            "module": "tools",
        },
        {
            "router": models_router,
            "prefix": "/models",
            "tags": ["Models Hub"],
            "auth": True,
            "module": "models",
        },
        {
            "router": external_models_router,
            "prefix": "/models/external",
            "tags": ["External Models Discovery"],
            "auth": True,
            "module": "models",
        },
        {
            # KPE (Knowledge Processing Engine) — the extraction /
            # classification / summarization / embedding pipeline. The
            # _kpe_router factory existed but was never added to
            # ROUTER_DEFINITIONS, so all 19 endpoints were unreachable while
            # the frontend called 5+ of them
            # (AgenticOSStudioPage/hooks/useAgenticOSAPI.ts:328,360,393,500,574).
            # The router self-prefixes "/kpe", so the mount prefix is empty.
            "router": _kpe_router(),
            "prefix": "",
            "tags": ["Knowledge Processing Engine"],
            "auth": True,
            "module": "kpe",
        },
        {
            "router": ai_models_catalog_router,
            "prefix": "/ai_models",
            "tags": ["Model Catalog"],
            "auth": True,
            "module": "ai_models",
        },
        {
            "router": sd_models_router,
            "prefix": "",
            "tags": ["SD Models"],
            "auth": True,
            "module": "sd_models",
        },
        # ── Vision & Media ─────────────────────────────────────────
        {
            "router": sam3_router,
            "prefix": "/sam3",
            "tags": ["SAM3 Segmentation"],
            "auth": True,
            "module": "sam3",
        },
        {
            "router": edit_router,
            "prefix": "/edit",
            "tags": ["Image Editing"],
            "auth": True,
            "module": "edit",
        },
        {
            "router": vision_router,
            "prefix": "/vision",
            "tags": ["Vision"],
            "auth": True,
            "module": "vision",
        },
        {
            "router": face_router,
            "prefix": "/face",
            "tags": ["Face Operations"],
            "auth": True,
            "module": "face",
        },
        {
            "router": influencer_router,
            "prefix": "/influencer",
            "tags": ["AI Influencer Studio"],
            "auth": True,
            "module": "influencer",
        },
        {
            "router": usecases_router,
            "prefix": "/usecases",
            "tags": ["Usecase Builder"],
            "auth": True,
            "module": "usecases",
        },
        {
            "router": collage_router,
            "prefix": "/collage",
            "tags": ["Collage & Sticker"],
            "auth": True,
            "module": "collage",
        },
        {
            "router": filters_router,
            "prefix": "/filters",
            "tags": ["Filters"],
            "auth": True,
            "module": "filters",
        },
        {
            "router": wildcards_router,
            "prefix": "/vision",
            "tags": ["Wildcards"],
            "auth": True,
            "module": "wildcards",
        },
        {
            "router": prompts_router,
            "prefix": "/prompts",
            "tags": ["Prompts"],
            "auth": True,
            "module": "prompts",
        },
        {
            "router": prompts_hero_router,
            "prefix": "/prompts-hero",
            "tags": ["PromptHero"],
            "auth": True,
            "module": "prompts_hero",
        },
        {
            "router": audio_router,
            "prefix": "/audio",
            "tags": ["Audio & TTS"],
            "auth": True,
            "module": "audio",
        },
        {
            "router": open_code_review_router,
            "prefix": "/code-review",
            "tags": ["Open Code Review"],
            "auth": True,
            "module": "open_code_review",
        },
        # ── Nodes / Sandbox ──────────────────────────────────────────
        {
            "router": nodes_router,
            "prefix": "",
            "tags": ["Nodes"],
            "auth": True,
            "module": "nodes",
        },
        {
            "router": sandbox_router,
            "prefix": "/sandbox",
            "tags": ["Sandbox"],
            "auth": True,
            "module": "sandbox",
        },
        # ── Memory ─────────────────────────────────────────────────
        # `module` drives load-time pruning: with `set_module_enabled("memory", False)`
        # these two routers are never mounted (no routes, no OpenAPI paths). `memories`
        # is the operational sibling of the cognitive memory router and shares the flag.
        {
            "router": cognitive_memory_router,
            "prefix": "/memory",
            "tags": ["Memory"],
            "auth": True,
            "module": "memory",
        },
        {
            "router": memories_router,
            "prefix": "/memories",
            "tags": ["Memories"],
            "auth": True,
            "module": "memory",
        },
        {
            "router": decision_router,
            "prefix": "/decision",
            "tags": ["Decision Fabric"],
            "auth": True,
            "module": "decision",
        },
        {
            "router": _decision_engine_router(),
            "prefix": "/decision-engine",
            "tags": ["Decision Engine"],
            "auth": True,
            "module": "decision_engine",
        },
        {
            "router": vectorstores_router,
            "prefix": "",
            "tags": ["Vector Stores"],
            "auth": True,
            "module": "vectorstores",
        },
        # ── Data & Storage ─────────────────────────────────────────
        {
            "router": data_forge_router,
            "prefix": "/data-forge",
            "tags": ["DataForge Simulation"],
            "auth": True,
            "module": "data_forge",
        },
        {
            "router": grid_router,
            "prefix": "/grid",
            "tags": ["Grid Customization Persistence"],
            "auth": True,
            "module": "grid",
        },
        {
            "router": dip_ingestion_router,
            "prefix": "",
            "tags": ["dip/ingestion"],
            "auth": True,
            "module": "dip",
        },
        {
            "router": dip_pipeline_router,
            "prefix": "",
            "tags": ["dip/pipeline"],
            "auth": True,
            "module": "dip",
        },
        {
            "router": dip_rag_router,
            "prefix": "",
            "tags": ["dip/rag"],
            "auth": True,
            "module": "dip",
        },
        {
            "router": dip_kg_router,
            "prefix": "",
            "tags": ["dip/kg"],
            "auth": True,
            "module": "dip",
        },
        {
            "router": dip_storage_router,
            "prefix": "",
            "tags": ["dip/storage"],
            "auth": True,
            "module": "dip",
        },
        {
            "router": dip_embeddings_router,
            "prefix": "",
            "tags": ["dip/embeddings"],
            "auth": True,
            "module": "dip",
        },
        {
            "router": dip_extraction_router,
            "prefix": "",
            "tags": ["dip/extraction"],
            "auth": True,
            "module": "dip",
        },
        # ── Plugins & Connectors ───────────────────────────────────
        {
            "router": plugins_router,
            "prefix": "/plugins",
            "tags": ["Plugin Management"],
            "auth": True,
            "module": "plugins",
        },
        {
            # app.modules.plugins.routes.plugin_router — plugin *instances* and
            # *links* (/plugins/instances, /plugins/links). Distinct from
            # plugins_router (Plugin Management) and from the secrets_manager
            # plugin router, so it keeps its own mount. Self-prefixed "/plugins".
            "router": plugin_router,
            "prefix": "",
            "tags": ["Plugins"],
            "auth": True,
            "module": "plugins",
        },
        {
            "router": connector_router,
            "prefix": "",
            "tags": ["Connectors"],
            "auth": True,
            "module": "connectors",
        },
        {
            "router": connection_router,
            "prefix": "",
            "tags": ["Connections"],
            "auth": True,
            "module": "connectors",
        },
        {
            "router": connectors_mcp_router,
            "prefix": "",
            "tags": ["MCP-Connectors"],
            "auth": True,
            "module": "connectors",
        },
        {
            "router": mcp_router,
            "prefix": "/mcp",
            "tags": ["MCP Ecosystem"],
            "auth": True,
            "module": "mcp",
        },
        # ── Configs & Settings ─────────────────────────────────────
        {
            "router": configs_router,
            "prefix": "",
            "tags": ["Configs"],
            "auth": True,
            "module": "configs",
        },
        {
            "router": _agentic_os_router(),
            "prefix": "",
            "tags": ["Agentic OS"],
            "auth": True,
            "module": "agentic_os",
        },
        {
            "router": settings_router,
            "prefix": "",
            "tags": ["Settings"],
            "auth": True,
            "module": "settings",
        },
        {
            # NOTE: namespaced mount. `keys_router` declares a collection root
            # at "@router.get('/')" / "@router.post('/')", so mounting it at ""
            # put it at /api/v1/ — where `_unified_hooks_router()` also mounts,
            # and first-match-wins meant `POST /api/v1/` ran `create_key` instead
            # of `create_hook`. /keys matches the sibling `credentials_router`
            # mount (/keys/credentials) immediately below.
            "router": keys_router,
            "prefix": "/keys",
            "tags": ["Keys Management"],
            "auth": True,
            "module": "keys_management",
        },
        {
            "router": credentials_router,
            "prefix": "/keys/credentials",
            "tags": ["Credentials Management"],
            "auth": True,
            "module": "keys_management",
        },
        {
            "router": proxy_router,
            "prefix": "/proxy",
            "tags": ["Proxy Routing"],
            "auth": True,
            "module": "proxy_routing",
        },
        {
            "router": system_router,
            "prefix": "/system",
            "tags": ["System"],
            "auth": True,
        },
        # Feature-flag write + live router reconcile. Declares no `module`/
        # `feature_flag`, so it is always mounted — including when every prunable
        # module is off. That is deliberate: it is the surface that turns them back
        # on, so gating it would let a bad flag write brick the recovery path.
        {
            "router": _flag_change_listener_router(),
            "prefix": "/system",
            "tags": ["Feature Flags"],
            "auth": True,
        },
        {
            "router": app_ops_router,
            "prefix": "",
            "tags": ["App Ops"],
            "auth": True,
            "module": "app_ops",
        },
        # ── Integration & Events ───────────────────────────────────
        {
            "router": integration_router,
            "prefix": "",
            "tags": ["integration"],
            "auth": True,
            "module": "integration",
        },
        {
            "router": notification_router,
            "prefix": "",
            "tags": ["notifications"],
            "auth": True,
            "module": "notification",
        },
        # ── Background & Scheduling ────────────────────────────────
        {
            "router": scheduler_router,
            "prefix": "",
            "tags": ["scheduler"],
            "auth": True,
            "module": "scheduler",
        },
        {
            "router": jobs_router,
            "prefix": "/jobs",
            "tags": ["Background Jobs"],
            "auth": True,
            "module": "jobs",
        },
        {
            "router": sd_news_router,
            "prefix": "",
            "tags": ["sd-news"],
            "auth": True,
            "module": "scheduler",
        },
        # ── Dashboard / Analytics ──────────────────────────────────
        {
            "router": dashboard_router,
            "prefix": "/dashboard",
            "tags": ["dashboard"],
            "auth": True,
            "module": "dashboard",
        },
        # ── External Apps ──────────────────────────────────────────
        {
            "router": ext_apps_router,
            "prefix": "",
            "tags": ["Ext-Apps"],
            "auth": True,
            "module": "ext_apps",
        },
        # ── Doc Processing (PDF + Excel) ─────────────────────────────
        {
            "router": doc_processing_router,
            "prefix": "/doc-processing",
            "tags": ["Doc Processing"],
            "auth": True,
            "module": "doc_processing",
        },
        # ── File Browser ───────────────────────────────────────────
        {
            "router": file_browser_router,
            "prefix": "",
            "tags": ["file-browser"],
            "auth": True,
            "module": "file_browser",
        },
        *(
            [
                {
                    "router": macro_router,
                    "prefix": "/file-browser",
                    "tags": ["macros"],
                    "auth": True,
                    # Same module as the main /file-browser entry: this is the
                    # macro sub-surface of app.modules.file_browser, mounted on
                    # its own prefix because macro_service may be absent.
                    "module": "file_browser",
                }
            ]
            if macro_router is not None
            else []
        ),
        # ── Marketplace & Graph ────────────────────────────────────
        {
            "router": marketplace_router,
            "prefix": "/marketplace",
            "tags": ["Marketplace"],
            "auth": True,
            "module": "marketplace",
        },
        {
            "router": creators_router,
            "prefix": "/creators",
            "tags": ["Creators"],
            "auth": True,
            "module": "creators",
        },
        {
            "router": entity_audit_router,
            "prefix": "/entities",
            "tags": ["Entity Audit"],
            "auth": True,
            "module": "marketplace",
        },
        {
            "router": graph_router,
            "prefix": "/graph",
            "tags": ["Graph"],
            "auth": True,
            "module": "graph",
        },
        # ── Prompt Studio ──────────────────────────────────────────
        {
            "router": prompt_studio_router,
            "prefix": "",
            "tags": ["Prompt Studio"],
            "auth": True,
            "module": "prompt_studio",
        },
        # ── Dev & Debug ────────────────────────────────────────────
        {
            "router": debug_router,
            "prefix": "/debug",
            "tags": ["Debug Simulator"],
            "auth": True,
            "module": "debug",
        },
        {
            "router": experiments_router,
            "prefix": "/experiments",
            "tags": ["Experiments"],
            "auth": True,
            "module": "experiments",
        },
        # ── SOTA Memory Systems ────────────────────────────────
        {
            "router": _sota_router(),
            "prefix": "/sota",
            "tags": ["SOTA Memory Systems"],
            "auth": True,
            "module": "sota",
        },
        # ── RIP (Retrieval Intelligence Platform) ────────────────
        {
            "router": _rip_router(),
            "prefix": "",
            "tags": ["RIP — Retrieval Intelligence"],
            "auth": True,
            "module": "rip",
        },
        # ── Orchestrator Hub ──────────────────────────────────────
        {
            "router": _orchestration_router(),
            "prefix": "/orchestration",
            "tags": ["Orchestrator Hub"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Pattern Factory ────────────────────────────────────────
        {
            "router": _patterns_router(),
            "prefix": "/orchestration",
            "tags": ["Pattern Factory"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Drift Detection ─────────────────────────────────────────
        {
            "router": _drift_router(),
            "prefix": "/orchestration",
            "tags": ["Drift Detection"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Plugin System ──────────────────────────────────────────
        {
            "router": _plugins_router(),
            "prefix": "/plugins",
            "tags": ["Plugin System"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Search Settings ──────────────────────────────────────
        {
            "router": _search_settings_router(),
            "prefix": "/agents/search-settings",
            "tags": ["Search Settings"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Kimchi (Execution Pipeline) ──────────────────────────
        {
            "router": _kimchi_router(),
            "prefix": "/kimchi",
            "tags": ["Kimchi Pipeline"],
            "auth": True,
            "module": "kimchi",
        },
        # ── Ferment (Multi-agent improvement engine) ──────────────
        {
            "router": _ferment_router(),
            "prefix": "/ferment",
            "tags": ["Ferment"],
            "auth": True,
            "module": "ferment",
        },
        # ── Reasoning Mode (requirements & plan checklist) ─────────
        {
            "router": _reasoning_router(),
            "prefix": "/reasoning",
            "tags": ["Reasoning"],
            "auth": True,
            "module": "reasoning",
        },
        # ── Toolchain Builder (routing visualizer) ──────────────────
        {
            "router": _toolchain_router(),
            "prefix": "/toolchain",
            "tags": ["Toolchain Builder"],
            "auth": True,
            "module": "toolchain",
        },
        # ── Agentic Pipelines (runnable agentic workflows) ──────────
        {
            "router": _agentic_pipelines_router(),
            "prefix": "/agentic-pipelines",
            "tags": ["Agentic Pipelines"],
            "auth": True,
            "module": "agentic_pipelines",
        },
        # ── DAW ────────────────────────────────────────────────────
        {
            "router": daw_router,
            "prefix": "/daw",
            "tags": ["DAW"],
            "auth": True,
            "module": "daw",
        },
        # ── Sync ───────────────────────────────────────────────────
        {
            "router": sync_router,
            "prefix": "/sync",
            "tags": ["Sync"],
            "auth": True,
            "module": "sync",
        },
        # ── Knowledge Engine (heavyweight — registered after observability) ──
        {
            "router": _knowledge_router(),
            "prefix": "",
            "tags": ["Knowledge Engine"],
            "auth": True,
            "module": "knowledge",
        },
        # ── Knowledge Engine Core (entities, claims, commits, branches, snapshots) ──
        {
            "router": _knowledge_engine_router(),
            "prefix": "/knowledge-engine",
            "tags": ["Knowledge Engine Core"],
            "auth": True,
            "module": "knowledge_engine",
        },
        # ── Knowledge World Model (F1 entity/fact ledger) ──
        {
            "router": _world_model_router(),
            "prefix": "",
            "tags": ["Knowledge World Model"],
            "auth": True,
            "module": "knowledge",
        },
        # ── Knowledge Alerts ──
        {
            "router": _alerts_router(),
            "prefix": "",
            "tags": ["Knowledge Alerts"],
            "auth": True,
            "module": "knowledge_engine",
        },
        # ── Nexus Context Acquisition (Cluster 4) ──
        {
            "router": _context_acquisition_router(),
            "prefix": "",
            "tags": ["Nexus Context Acquisition"],
            "auth": True,
            "module": "knowledge_engine",
        },
        # ── Nexus Knowledge Compiler (Cluster 1) ──
        {
            "router": _compiler_router(),
            "prefix": "",
            "tags": ["Nexus Knowledge Compiler"],
            "auth": True,
            "module": "knowledge_engine",
        },
        # ── Nexus Communities / Global Understanding (Cluster 3) ──
        {
            "router": _communities_router(),
            "prefix": "",
            "tags": ["Nexus Communities"],
            "auth": True,
            "module": "knowledge_engine",
        },
        # ── Knowledge Ontology (F2 type trust boundary) ──
        {
            "router": _ontology_router(),
            "prefix": "",
            "tags": ["Knowledge Ontology"],
            "auth": True,
            "module": "knowledge",
        },
        {
            "router": _governance_router(),
            "prefix": "/governance",
            "tags": ["Agent Governance"],
            "auth": True,
            "module": "governance",
        },
        {
            "router": _obs_admin_router(),
            "prefix": "",
            "tags": ["Observability Admin"],
            "auth": True,
            "module": "observability",
        },
        {
            "router": _docs_router(),
            "prefix": "",
            "tags": ["Documentation"],
            "auth": True,
            "module": "docs",
        },
        # ── Knowledge Hub ──────────────────────────────────────────
        *_knowledge_hub_entries(api_prefix),
        # ── Agentic RBAC ───────────────────────────────────────────
        {
            "router": _authz_router(),
            "prefix": "/authz",
            "tags": ["Authorization — Agentic RBAC"],
            "auth": True,
            "module": "authorization",
        },
        # ── Team ───────────────────────────────────────────────────
        {
            "router": _team_router(),
            "prefix": "",
            "tags": ["Team"],
            "auth": True,
            "module": "team",
        },
        # ── Reporting (Universal Reporting Platform) ───────────────
        {
            "router": _reporting_router(),
            "prefix": "/reporting",
            "tags": ["Reporting"],
            "auth": True,
            "module": "reporting",
        },
        # ── HITL Policy Builder ────────────────────────────────────
        {
            "router": _hitl_router(),
            "prefix": "/hitl",
            "tags": ["HITL - Policy Builder"],
            "auth": True,
            "module": "hitl",
        },
        # ── Verification (COGR staged model-output verification) ──
        {
            "router": _verification_router(),
            "prefix": "",
            "tags": ["Verification"],
            "auth": True,
            "module": "verification",
        },
        # ── Writing Studio ───────────────────────────────────────────
        {
            "router": writing_router,
            "prefix": "/writing",
            "tags": ["Writing Studio"],
            "auth": True,
            "module": "writing",
        },
        # ── Messaging Gateway ──────────────────────────────────────────
        {
            "router": messaging_router,
            "prefix": "/messaging",
            "tags": ["Messaging Gateway"],
            "auth": True,
            "module": "messaging",
        },
        # ── Evolver ─────────────────────────────────────────────────
        {
            "router": evolver_router,
            "prefix": "/evolver",
            "tags": ["Evolver — GEP/ATP"],
            "auth": True,
            "module": "evolver",
        },
        # ── Document Vault ──────────────────────────────────────────
        {
            "router": document_vault_router,
            "prefix": "",
            "tags": ["Document Vault"],
            "auth": True,
            "module": "document_vault",
        },
        # ── Document Creator ──────────────────────────────────────────
        {
            "router": _document_creator_router(),
            "prefix": "",
            "tags": ["Document Creator"],
            "auth": True,
            "module": "document_creator",
        },
        # ── Control Center ─────────────────────────────────────────
        {
            "router": _control_center_router(),
            "prefix": "",
            "tags": ["Control Center"],
            "auth": True,
            "module": "control_center",
        },
        # ── Admin Database ─────────────────────────────────────────
        {
            "router": _admin_db_router(),
            "prefix": "",
            "tags": ["Admin Database"],
            "auth": True,
            "module": "admin_db",
        },
        # ── Multi-Source ETL ────────────────────────────────────────
        {
            "router": _etl_router(),
            "prefix": "/etl",
            "tags": ["Multi-Source ETL"],
            "auth": True,
            "module": "multi_source_etl",
        },
        # ── Database Connections ─────────────────────────────────────
        {
            "router": _database_connections_router(),
            "prefix": "/databases",
            "tags": ["Database Connections"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Query Workbench ───────────────────────────────────────────
        {
            "router": _query_workbench_router(),
            "prefix": "/query-workbench",
            "tags": ["Query Workbench"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Schema Browser ──────────────────────────────────────────────
        {
            "router": _schema_browser_router(),
            "prefix": "/schema-browser",
            "tags": ["Schema Browser"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Data Browser ─────────────────────────────────────────────────
        {
            "router": _data_browser_router(),
            "prefix": "/data-browser",
            "tags": ["Data Browser"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Visual Database Designers ────────────────────────────────────
        {
            "router": _visual_designers_router(),
            "prefix": "/designers",
            "tags": ["Visual Database Designers"],
            "auth": True,
            "module": "db_studio",
        },
        # ── AI Database Copilot ───────────────────────────────────────────
        {
            "router": _ai_copilot_router(),
            "prefix": "/ai",
            "tags": ["AI Database Copilot"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Universal Query Execution Engine ───────────────────────────────
        {
            "router": _query_execution_router(),
            "prefix": "/execution",
            "tags": ["Universal Query Execution Engine"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Connector SDK & Driver Framework ────────────────────────────────
        {
            "router": _connector_sdk_router(),
            "prefix": "/connector-sdk",
            "tags": ["Connector SDK & Driver Framework"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Capability Registry & Database Abstraction Layer ─────────────────
        {
            "router": _capability_registry_router(),
            "prefix": "/capabilities",
            "tags": ["Capability Registry & DAL"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Database Administration Center ─────────────────────────────────
        {
            "router": _administration_router(),
            "prefix": "/admin",
            "tags": ["Database Administration Center"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Performance Profiler & Query Optimizer ──────────────────────────
        {
            "router": _performance_router(),
            "prefix": "/performance",
            "tags": ["Performance Profiler & Query Optimizer"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Backup, Restore & Snapshot Manager ───────────────────────────────
        {
            "router": _backup_router(),
            "prefix": "/backup",
            "tags": ["Backup, Restore & Snapshot Manager"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Migration & Schema Versioning ─────────────────────────────────────
        {
            "router": _migration_router(),
            "prefix": "/migrations",
            "tags": ["Migration & Schema Versioning"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Import, Export & Data Exchange ─────────────────────────────────────
        {
            "router": _data_exchange_router(),
            "prefix": "/data-exchange",
            "tags": ["Import, Export & Data Exchange"],
            "auth": True,
            "module": "db_studio",
        },
        # ── ETL/ELT/Reverse ETL Platform ────────────────────────────────────────
        {
            "router": _etl_platform_router(),
            "prefix": "/etl",
            "tags": ["ETL/ELT/Reverse ETL Platform"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Data Quality & Profiling ────────────────────────────────────────────────
        {
            "router": _data_quality_router(),
            "prefix": "/data-quality",
            "tags": ["Data Quality & Profiling"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Monitoring & Observability ─────────────────────────────────────────────────
        {
            "router": _observability_router(),
            "prefix": "/observability",
            "tags": ["Monitoring & Observability"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Security, Auth & Secret Management ──────────────────────────────────────────
        {
            "router": _security_router(),
            "prefix": "/security",
            "tags": ["Security, Auth & Secret Management"],
            "auth": True,
            "module": "security",
        },
        # ── Security Audit Events, DLP & Compliance ──────────────────────────────────────
        {
            "router": _security_audit_router(),
            "prefix": "/security",
            "tags": ["Security Audit"],
            "auth": True,
            "module": "db_studio",
        },
        # ── RBAC, Teams & Collaboration ─────────────────────────────────────────────────
        {
            "router": _collaboration_router(),
            "prefix": "/collaboration",
            "tags": ["RBAC, Teams & Collaboration"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Notebook & Interactive Workspace ─────────────────────────────────────────────
        {
            "router": _notebook_router(),
            "prefix": "/notebooks",
            "tags": ["Notebook & Interactive Workspace"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Query History, Snippets & Templates ───────────────────────────────────────────
        {
            "router": _knowledge_library_router(),
            "prefix": "/knowledge-library",
            "tags": ["Query History, Snippets & Templates"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Scheduler, Jobs & Automation ───────────────────────────────────────────────────
        {
            "router": _automation_router(),
            "prefix": "/automation",
            "tags": ["Scheduler, Jobs & Automation"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Plugin Marketplace & Extension SDK ────────────────────────────────────────────────
        # Namespaced to /plugins/marketplace: the marketplace router claims
        # "/{plugin_id}", which collided head-on with the Plugin System and
        # Plugin Management routers on /plugins. Same shape as the /etl and
        # /security separations — distinct capability, distinct prefix.
        {
            "router": _plugin_marketplace_router(),
            "prefix": "/plugins/marketplace",
            "tags": ["Plugin Marketplace & Extension SDK"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Workspace, Projects & Environment Management ────────────────────────────────────────
        {
            "router": _workspace_environment_router(),
            "prefix": "/workspaces",
            "tags": ["Workspace, Projects & Environment Management"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Search, Catalog & Data Discovery ────────────────────────────────────────────────────
        {
            "router": _discovery_router(),
            "prefix": "",
            "tags": ["Search, Catalog & Data Discovery"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Lineage, Governance & Compliance ────────────────────────────────────────────────────
        {
            "router": _db_studio_governance_router(),
            "prefix": "",
            "tags": ["Lineage, Governance & Compliance"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Visualization, Dashboards & Reporting ────────────────────────────────────────────────
        # NOTE: namespaced mount — root-level paths (/dashboards, /usage,
        # /dashboard/stats) collide with the core dashboard module at "".
        # Matches DatabaseStudio DashboardsSection (/api/v1/visualization).
        {
            "router": _visualization_router(),
            "prefix": "/visualization",
            "tags": ["Visualization, Dashboards & Reporting"],
            "auth": True,
            "module": "db_studio",
        },
        # ── API Layer, WebSocket & MCP Integration ────────────────────────────────────────────────
        # NOTE: namespaced mount — root-level paths (/mcp-tools, /mcp-resources,
        # /usage, /dashboard) collide with core modules at "". Matches
        # DatabaseStudio APIIntegrationSection (/api/v1/api-integration).
        {
            "router": _api_integration_router(),
            "prefix": "/api-integration",
            "tags": ["API Layer, WebSocket & MCP Integration"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Backend Architecture & Folder Structure ────────────────────────────────────────────
        # NOTE: namespaced mount (matches ArchitectureSection:
        # /api/v1/backend-architecture); "" mount shadowed core routes.
        {
            "router": _backend_architecture_router(),
            "prefix": "/backend-architecture",
            "tags": ["Backend Architecture & Folder Structure"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Frontend Architecture & Design System ────────────────────────────────────────────
        # NOTE: namespaced mount (matches DesignSystemSection:
        # /api/v1/frontend-design); "" mount shadowed core routes.
        {
            "router": _frontend_design_router(),
            "prefix": "/frontend-design",
            "tags": ["Frontend Architecture & Design System"],
            "auth": True,
            "module": "db_studio",
        },
        # ── Unified Entity System (Triggers / Hooks / Rules) ──────────
        {
            "router": _unified_triggers_router(),
            "prefix": "",
            "tags": ["Unified Triggers"],
            "auth": True,
            "module": "triggers",
        },
        # Durable cron schedules. Gated at runtime by
        # 'triggers.cron_durable_schedules' (default OFF) — the routes answer 503
        # while the flag is off, so a 200 always means a schedule really persisted.
        {
            "router": _cron_schedules_router(),
            "prefix": "",
            "tags": ["Cron Schedules"],
            "auth": True,
            "module": "triggers",
        },
        {
            # NOTE: namespaced mount. This router is ALREADY mounted correctly at
            # "/hooks" above (see the `hooks_router` entry). Mounting the same
            # router again at "" duplicated its collection root at /api/v1/,
            # where it collided with `keys_router` and shadowed
            # `create_hook` behind `create_key`. The "" mount also served no
            # purpose beyond the duplicate: every path it added is already
            # reachable under /hooks.
            "router": _unified_hooks_router(),
            "prefix": "/unified-hooks",
            "tags": ["Unified Hooks"],
            "auth": True,
            "module": "hooks",
        },
        {
            "router": _unified_rules_router(),
            "prefix": "",
            "tags": ["Unified Rules"],
            "auth": True,
            "module": "rules",
        },
        {
            "router": _unified_interceptors_router(),
            "prefix": "",
            "tags": ["Unified Interceptors"],
            "auth": True,
            "module": "interceptors",
        },
        # ── ChatGPT MCP Integration ────────────────────────────────
        {
            "router": _chatgpt_mcp_router(),
            "prefix": "",
            "tags": ["ChatGPT MCP Integration"],
            "auth": True,
            "module": "chatgpt_mcp",
        },
        # ── Internet Intelligence Layer (IIL) ──────────────────────────
        {
            "router": _iil_router(),
            "prefix": "/iil",
            "tags": ["Internet Intelligence Layer"],
            "auth": True,
            "module": "iil",
        },
        # ── Nexus Studio (Custom GPT Builder) ───────────────────────────
        {
            "router": _studio_router(),
            "prefix": "",
            "tags": ["Nexus Studio"],
            "auth": True,
            "module": "gpt_builder",
        },
        # ── Project Management ───────────────────────────
        {
            "router": _project_management_router(),
            "prefix": "/pm",
            "tags": ["Project Management"],
            "auth": True,
            "module": "project_management",
        },
        # ── Secrets Manager ───────────────────────────
        *_secrets_manager_routers(),
        # ── Image Intelligence Platform ───────────────────────────
        {
            "router": __import__(
                "app.routers.image_router", fromlist=["router"]
            ).router,
            "prefix": "",
            "tags": ["Image Intelligence Platform"],
            "auth": True,
            "module": "image_processing",
        },
        # ── Data Storage ──────────────────────────────────────────
        {
            "router": __import__(
                "app.modules.data_storage.routes.router", fromlist=["router"]
            ).router,
            "prefix": "/data-storage",
            "tags": ["Data Storage"],
            "auth": True,
            "module": "data_storage",
        },
        # ── Education ────────────────────────────────────────────
        {
            "router": __import__(
                "app.modules.education.routes.router", fromlist=["router"]
            ).router,
            "prefix": "/education",
            "tags": ["Education"],
            "auth": True,
            "module": "education",
        },
        # ── DB Provisioning ──────────────────────────────────────
        {
            "router": __import__(
                "app.modules.db_provisioning.routes.router", fromlist=["router"]
            ).router,
            "prefix": "/db-provisioning",
            "tags": ["DB Provisioning"],
            "auth": True,
            "module": "db_provisioning",
        },
        # ── File System ──────────────────────────────────────────
        {
            "router": __import__(
                "app.modules.file_system.routes.router", fromlist=["router"]
            ).router,
            "prefix": "/file-system",
            "tags": ["File System"],
            "auth": True,
            "module": "file_system",
        },
        # ── Claude-Mem Memory Features (Phases 1-10) ─────────────
        {
            "router": _claude_mem_router(),
            "prefix": "",
            "tags": ["Claude-Mem Memory"],
            "auth": True,
            "module": "claude_mem",
        },
        # ── AutoResearch (Autonomous Research Loop) ──────────────
        {
            "router": _autoresearch_router(),
            "prefix": "",
            "tags": ["AutoResearch"],
            "auth": True,
            "module": "knowledge_engine",
        },
        # ── Response Templates (CRUD for MD templates) ──────────
        {
            "router": _response_templates_router(),
            "prefix": "",
            "tags": ["Response Templates"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Section Library (reusable sections for template composition) ──
        {
            "router": _section_library_router(),
            "prefix": "",
            "tags": ["Section Library"],
            "auth": True,
            "module": "orchestration",
        },
        # ── Background Tasks (long-running process management) ──
        {
            "router": _background_tasks_router(),
            "prefix": "",
            "tags": ["Background Tasks"],
            "auth": True,
            "module": "system",
        },
        # ── Universal Task Runner (platform execution substrate) ──
        {
            "router": _task_runner_router(),
            "prefix": "",
            "tags": ["Universal Task Runner"],
            "auth": True,
            "module": "system",
        },
        # ── Agent Behaviour (traits, strategies, policies, budgets, etc.) ──
        {
            "router": _behaviour_router(),
            "prefix": "/orchestration",
            "tags": ["Agent Behaviour"],
            "auth": True,
            "module": "behaviour",
        },
        # ── AI Gateway (universal LLM proxy with 300+ providers) ──
        {
            "router": _ai_gateway_router(),
            "prefix": "",
            "tags": ["AI Gateway"],
            "auth": True,
            "module": "ai_gateway",
        },
        # ── Platform Controls (Universal control plane) ──
        # platform_controls — Phase 0 skeleton. Unauthenticated /health
        # only; every later-phase endpoint added here requires a JWT
        # bearer (and admin / audit endpoints also need the matching
        # RBAC scope). See common_lib/modules/platform_controls/docs/14_observability_security.md §3.
        {
            "router": _platform_controls_router(),
            "prefix": "/platform-controls",
            "tags": ["Platform Controls"],
            "auth": False,  # the /health endpoint manages its own auth (none)
            "module": "platform_controls",
        },
        # ── I2W (Instruction-to-Workflow) — Phase 7 ──
        # 55 endpoints (REST + WS) at /api/v1/i2w/. The /health and
        # /metrics endpoints manage their own auth (none / scrape-job
        # only); every other endpoint requires a JWT bearer plus the
        # appropriate RBAC scope (i2w.read | i2w.write | i2w.execute
        # | i2w.training.admin). Per-endpoint auth is enforced by the
        # i2w_deps(...) dependency stack inside each sub-router; the
        # registry auth=False skips the global auth so the unauth'd
        # /health and /metrics endpoints can be served without a JWT.
        # The router is feature-flag gated inside the dependency
        # stack; when the master flag is off every endpoint returns
        # 404. See
        # common_lib/modules/orchestration/instruction_to_workflow/docs/08_api_contract.md
        # for the full contract.
        {
            "router": _i2w_router(),
            "prefix": "/i2w",
            "tags": ["Instruction-to-Workflow (I2W)"],
            "auth": False,  # per-endpoint auth via i2w_deps()
            "module": "i2w",
        },
        {
            "router": _layouts_router(),
            "prefix": "/layouts",
            "tags": ["Layouts"],
            "auth": True,
        },
        # ── Cognitive Runtime (COGR execution runtime) ──
        {
            "router": _cognitive_runtime_router(),
            "prefix": "/cognitive",
            "tags": ["Cognitive Runtime"],
            "auth": True,
            "module": "cognitive_runtime",
        },
    ]

    orig_lifespan = getattr(app.router, "lifespan_context", None)

    # Load-time feature-flag pruning: a router whose module is explicitly disabled
    # is never mounted (no routes, no OpenAPI paths). Fail-open — on any error the
    # full list is mounted, because an unpruned surface is recoverable and a
    # missing one is not.
    try:
        active_definitions = prune_router_definitions(ROUTER_DEFINITIONS)
    except Exception:  # pragma: no cover - defensive
        logger.warning(
            "Router pruning failed — mounting all %d routers (fail-open)",
            len(ROUTER_DEFINITIONS),
            exc_info=True,
        )
        active_definitions = ROUTER_DEFINITIONS

    # Remember the unpruned list on the app so a runtime feature-flag change can
    # re-evaluate it and hot-mount what became enabled (see app/core/router_hot_mount.py).
    remember_definitions(app, ROUTER_DEFINITIONS)
    remember_mount_context(app, api_prefix, global_deps)

    # Mount by position in the *unpruned* list so the idempotency key matches the one
    # `reconcile_router_mounts` derives later. Identity (not equality) marks membership:
    # `in` on a dict list is an O(n^2) deep compare and two distinct entries could compare
    # equal.
    active_ids = {id(e) for e in active_definitions}
    for position, entry in enumerate(ROUTER_DEFINITIONS):
        if id(entry) not in active_ids:
            continue
        mount_router_entry(
            app, entry, api_prefix, global_deps, live=False, position=position
        )

    # FastAPI wraps `app.router.lifespan_context` on every `include_router`, creating a 225-level
    # deep nested `_merge_lifespan_context` generator chain even though sub-routers only have a
    # default no-op `_DefaultLifespan`. When any startup exception occurs, Python unwinds all 225 frames,
    # spamming ~500 lines of `merged_lifespan` in the traceback and hiding the real error.
    # Sub-routers in this platform do not define custom lifespans, so preserve top-level app lifespan directly.
    if orig_lifespan is not None:
        app.router.lifespan_context = orig_lifespan

    logger.info(
        "Startup: Registered %d routers via declarative registry (P2-1)",
        len(active_definitions),
    )


__all__ = ["register_routers"]

# Export for external access
__all__ = ["register_routers", "ROUTER_DEFINITIONS"]
