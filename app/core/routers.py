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
    }
"""

from __future__ import annotations

import logging
from typing import Any, List

from fastapi import FastAPI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy loader helpers for heavyweight / late-registered routers
# ---------------------------------------------------------------------------


def _knowledge_router():
    from app.modules.knowledge.routes import router

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


def _orchestration_router():
    from app.modules.orchestration import router

    return router


def _patterns_router():
    from app.modules.orchestration.patterns_routes import router

    return router


def _drift_router():
    from app.modules.orchestration.drift_routes import router

    return router


def _kpe_router():
    from app.modules.kpe.routes import router

    return router


def _kimchi_router():
    from app.modules.kimchi import router

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

    return [
        {
            "router": sources_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Sources"],
            "auth": True,
        },
        {
            "router": pipelines_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Ingestion"],
            "auth": True,
        },
        {
            "router": packets_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Packets"],
            "auth": True,
        },
        {
            "router": kh_projects_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Projects"],
            "auth": True,
        },
        {
            "router": streaming_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Streaming"],
            "auth": True,
        },
        {
            "router": collections_router,
            "prefix": "",
            "tags": ["Knowledge Hub — Collections"],
            "auth": True,
        },
    ]


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
    from app.modules.projects.routes.projects import router as projects_router
    from app.modules.agents.routes.index import router as agents_router
    from app.modules.agents.routes.pipeline_routes import router as pipeline_router
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
    from app.modules.vectorstores.routes import router as vectorstores_router
    from app.modules.models.routes import router as models_router
    from app.modules.models.external_routes import router as external_models_router
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
    from app.modules.settings.routes import router as settings_router
    from app.modules.dip.routes.ingestion import router as dip_ingestion_router
    from app.modules.dip.routes.pipeline import pipeline_router as dip_pipeline_router
    from app.modules.dip.routes.rag import router as dip_rag_router
    from app.modules.dip.routes.kg import router as dip_kg_router
    from app.modules.dip.routes.storage import router as dip_storage_router
    from app.modules.dip.routes.embeddings import router as dip_embeddings_router
    from app.modules.dip.routes.extraction import router as dip_extraction_router
    from app.modules.file_browser import router as file_browser_router
    from app.modules.file_browser.macro_routes import router as macro_router
    from app.modules.notification.routes import router as notification_router
    from app.modules.wildcards.routes import router as wildcards_router
    from app.modules.sam3.routes import router as sam3_router
    from app.modules.keys_management import router as keys_router
    from app.modules.proxy_routing import router as proxy_router
    from app.modules.collage.routes import router as collage_router
    from app.modules.experiments.routes import router as experiments_router
    from app.modules.ext_apps import router as ext_apps_router
    from app.modules.connectors.routes import connector_router, connection_router
    from app.modules.connectors.mcp.server import router as connectors_mcp_router
    from app.modules.plugins.routes import plugin_router

    # Lazy imports for modules not imported at main.py top level
    from app.modules.vision.routes import router as vision_router
    from app.modules.filters.routes import router as filters_router
    from app.modules.nodes.routes import router as nodes_router
    from app.modules.prompts.routes import router as prompts_router
    from app.modules.prompts_hero.routes import router as prompts_hero_router
    from app.modules.configs.routes import router as configs_router
    from app.modules.sd_models.routes import router as sd_models_router
    from app.modules.audio.routes import router as audio_router
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
    from app.modules.sandbox import router as sandbox_router
    from app.modules.scheduler.routes.news_routes import router as sd_news_router
    from app.modules.prompt_studio.routes import router as prompt_studio_router
    from app.modules.evolver import router as evolver_router
    from app.modules.writing.routes import router as writing_router
    from app.modules.messaging.routes import router as messaging_router
    from app.modules.document_vault import router as document_vault_router

    def _hitl_router():
        from app.modules.hitl.routes import router

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
        from app.modules.database_connections.routes import router

        return router

    def _unified_triggers_router():
        from app.modules.triggers.routes import router

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
        },
        # ── Authorization ─────────────────────────────────────────
        {"router": roles_router, "prefix": "/roles", "tags": ["Roles"], "auth": True},
        {
            "router": permissions_router,
            "prefix": "/permissions",
            "tags": ["Permissions"],
            "auth": True,
        },
        {"router": users_router, "prefix": "/users", "tags": ["Users"], "auth": True},
        {
            "router": projects_router,
            "prefix": "/projects",
            "tags": ["Projects"],
            "auth": True,
        },
        # ── Hooks / Webhooks ───────────────────────────────────────
        {"router": hooks_router, "prefix": "/hooks", "tags": ["Hooks"], "auth": True},
        {
            "router": webhooks_router,
            "prefix": "/webhooks",
            "tags": ["Webhook Manager"],
            "auth": True,
        },
        # ── App Builder ────────────────────────────────────────────
        {
            "router": forms_router,
            "prefix": "/forms",
            "tags": ["Form Builder"],
            "auth": True,
        },
        {
            "router": features_router,
            "prefix": "/features",
            "tags": ["Feature Picker"],
            "auth": True,
        },
        {
            "router": connection_health_router,
            "prefix": "",
            "tags": ["Connection Health"],
            "auth": True,
        },
        {
            "router": ecosystem_router,
            "prefix": "/ecosystem",
            "tags": ["App Ecosystem"],
            "auth": True,
        },
        {"router": builder_router, "prefix": "", "tags": ["UI Builder"], "auth": True},
        {
            "router": schema_router,
            "prefix": "/schema",
            "tags": ["Schema Builder"],
            "auth": True,
        },
        # ── Entities & Orchestration ───────────────────────────────
        {
            "router": entities_router,
            "prefix": "/entities/registry",
            "tags": ["Entities Registry"],
            "auth": True,
        },
        {
            "router": entity_instances_router,
            "prefix": "/instances",
            "tags": ["Entity Instances"],
            "auth": True,
        },
        {
            "router": agents_router,
            "prefix": "/agents",
            "tags": ["Agents (Management)"],
            "auth": True,
        },
        {
            "router": pipeline_router,
            "prefix": "/agents/pipelines",
            "tags": ["Pipelines"],
            "auth": True,
        },
        {
            "router": policy_router,
            "prefix": "/agents",
            "tags": ["Policy & Multi-Agent"],
            "auth": True,
        },
        {
            "router": task_router,
            "prefix": "/agents",
            "tags": ["Task Queue"],
            "auth": True,
        },
        {
            "router": profile_router,
            "prefix": "/agents",
            "tags": ["Agent Profiles"],
            "auth": True,
        },
        {
            "router": skill_router,
            "prefix": "/agents",
            "tags": ["Skill Bridge"],
            "auth": True,
        },
        {
            "router": daemon_router,
            "prefix": "/agents",
            "tags": ["Agent Daemons"],
            "auth": True,
        },
        # ── Site Builder ────────────────────────────────────────
        {
            "router": site_project_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder"],
            "auth": True,
        },
        {
            "router": site_sitemap_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Sitemap"],
            "auth": True,
        },
        {
            "router": site_wireframe_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Wireframe"],
            "auth": True,
        },
        {
            "router": site_registry_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Registry"],
            "auth": True,
        },
        {
            "router": site_theme_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Themes"],
            "auth": True,
        },
        {
            "router": site_export_router,
            "prefix": "/site-builder",
            "tags": ["Site Builder Export"],
            "auth": True,
        },
        # ── Workflows ─────────────────────────────────────────────
        {
            "router": workflows_router,
            "prefix": "/workflows",
            "tags": ["Workflows"],
            "auth": True,
        },
        {
            "router": collaboration_router,
            "prefix": "/workflows",
            "tags": ["Workflow Collaboration"],
            "auth": True,
        },
        {
            "router": observability_router,
            "prefix": "/workflows/observability",
            "tags": ["Workflow Observability"],
            "auth": True,
        },
        {
            "router": workflow_configs_router,
            "prefix": "/workflow-configs",
            "tags": ["Workflow Configs"],
            "auth": True,
        },
        {
            "router": failure_analysis_router,
            "prefix": "/workflows",
            "tags": ["Workflow Failure Analysis"],
            "auth": True,
        },
        {
            "router": combinatorial_router,
            "prefix": "/workflows/combinatorial",
            "tags": ["Workflow Combinatorial"],
            "auth": True,
        },
        # ── Workflow Compiler (AAR) ────────────────────────────────
        {
            "router": workflow_compiler_router,
            "prefix": "/workflows",
            "tags": ["Workflow Compiler — AAR"],
            "auth": True,
        },
        # ── Tools & Models ─────────────────────────────────────────
        {"router": tools_router, "prefix": "/tools", "tags": ["Tools"], "auth": True},
        {
            "router": models_router,
            "prefix": "/models",
            "tags": ["Models Hub"],
            "auth": True,
        },
        {
            "router": external_models_router,
            "prefix": "/models/external",
            "tags": ["External Models Discovery"],
            "auth": True,
        },
        {"router": sd_models_router, "prefix": "", "tags": ["SD Models"], "auth": True},
        # ── Vision & Media ─────────────────────────────────────────
        {
            "router": sam3_router,
            "prefix": "/sam3",
            "tags": ["SAM3 Segmentation"],
            "auth": True,
        },
        {
            "router": vision_router,
            "prefix": "/vision",
            "tags": ["Vision"],
            "auth": True,
        },
        {
            "router": collage_router,
            "prefix": "/collage",
            "tags": ["Collage & Sticker"],
            "auth": True,
        },
        {
            "router": filters_router,
            "prefix": "/filters",
            "tags": ["Filters"],
            "auth": True,
        },
        {
            "router": wildcards_router,
            "prefix": "/vision",
            "tags": ["Wildcards"],
            "auth": True,
        },
        {
            "router": prompts_router,
            "prefix": "/prompts",
            "tags": ["Prompts"],
            "auth": True,
        },
        {
            "router": prompts_hero_router,
            "prefix": "/prompts-hero",
            "tags": ["PromptHero"],
            "auth": True,
        },
        {
            "router": audio_router,
            "prefix": "/audio",
            "tags": ["Audio & TTS"],
            "auth": True,
        },
        # ── Nodes / Sandbox ──────────────────────────────────────────
        {"router": nodes_router, "prefix": "", "tags": ["Nodes"], "auth": True},
        {
            "router": sandbox_router,
            "prefix": "/sandbox",
            "tags": ["Sandbox"],
            "auth": True,
        },
        # ── Memory ─────────────────────────────────────────────────
        {
            "router": cognitive_memory_router,
            "prefix": "/memory",
            "tags": ["Memory"],
            "auth": True,
        },
        {
            "router": memories_router,
            "prefix": "/memories",
            "tags": ["Memories"],
            "auth": True,
        },
        {
            "router": vectorstores_router,
            "prefix": "",
            "tags": ["Vector Stores"],
            "auth": True,
        },
        # ── Data & Storage ─────────────────────────────────────────
        {
            "router": data_forge_router,
            "prefix": "/data-forge",
            "tags": ["DataForge Simulation"],
            "auth": True,
        },
        {
            "router": grid_router,
            "prefix": "/grid",
            "tags": ["Grid Customization Persistence"],
            "auth": True,
        },
        {
            "router": dip_ingestion_router,
            "prefix": "",
            "tags": ["dip/ingestion"],
            "auth": True,
        },
        {
            "router": dip_pipeline_router,
            "prefix": "",
            "tags": ["dip/pipeline"],
            "auth": True,
        },
        {"router": dip_rag_router, "prefix": "", "tags": ["dip/rag"], "auth": True},
        {"router": dip_kg_router, "prefix": "", "tags": ["dip/kg"], "auth": True},
        {
            "router": dip_storage_router,
            "prefix": "",
            "tags": ["dip/storage"],
            "auth": True,
        },
        {
            "router": dip_embeddings_router,
            "prefix": "",
            "tags": ["dip/embeddings"],
            "auth": True,
        },
        {
            "router": dip_extraction_router,
            "prefix": "",
            "tags": ["dip/extraction"],
            "auth": True,
        },
        # ── Plugins & Connectors ───────────────────────────────────
        {
            "router": plugins_router,
            "prefix": "/plugins",
            "tags": ["Plugin Management"],
            "auth": True,
        },
        {"router": plugin_router, "prefix": "", "tags": ["Plugins"], "auth": True},
        {
            "router": connector_router,
            "prefix": "",
            "tags": ["Connectors"],
            "auth": True,
        },
        {
            "router": connection_router,
            "prefix": "",
            "tags": ["Connections"],
            "auth": True,
        },
        {
            "router": connectors_mcp_router,
            "prefix": "",
            "tags": ["MCP-Connectors"],
            "auth": True,
        },
        {
            "router": mcp_router,
            "prefix": "/mcp",
            "tags": ["MCP Ecosystem"],
            "auth": True,
        },
        # ── Configs & Settings ─────────────────────────────────────
        {"router": configs_router, "prefix": "", "tags": ["Configs"], "auth": True},
        {
            "router": _agentic_os_router(),
            "prefix": "",
            "tags": ["Agentic OS"],
            "auth": True,
        },
        {"router": settings_router, "prefix": "", "tags": ["Settings"], "auth": True},
        {
            "router": keys_router,
            "prefix": "",
            "tags": ["Keys Management"],
            "auth": True,
        },
        {
            "router": proxy_router,
            "prefix": "/proxy",
            "tags": ["Proxy Routing"],
            "auth": True,
        },
        {"router": system_router, "prefix": "", "tags": ["System"], "auth": True},
        # ── Integration & Events ───────────────────────────────────
        {
            "router": integration_router,
            "prefix": "",
            "tags": ["integration"],
            "auth": True,
        },
        {
            "router": notification_router,
            "prefix": "",
            "tags": ["notifications"],
            "auth": True,
        },
        # ── Background & Scheduling ────────────────────────────────
        {"router": scheduler_router, "prefix": "", "tags": ["scheduler"], "auth": True},
        {"router": sd_news_router, "prefix": "", "tags": ["sd-news"], "auth": True},
        # ── Dashboard / Analytics ──────────────────────────────────
        {
            "router": dashboard_router,
            "prefix": "/dashboard",
            "tags": ["dashboard"],
            "auth": True,
        },
        # ── External Apps ──────────────────────────────────────────
        {"router": ext_apps_router, "prefix": "", "tags": ["Ext-Apps"], "auth": True},
        # ── File Browser ───────────────────────────────────────────
        {
            "router": file_browser_router,
            "prefix": "",
            "tags": ["file-browser"],
            "auth": True,
        },
        {
            "router": macro_router,
            "prefix": "/file-browser",
            "tags": ["macros"],
            "auth": True,
        },
        # ── Marketplace & Graph ────────────────────────────────────
        {
            "router": marketplace_router,
            "prefix": "/marketplace",
            "tags": ["Marketplace"],
            "auth": True,
        },
        {
            "router": creators_router,
            "prefix": "/creators",
            "tags": ["Creators"],
            "auth": True,
        },
        {
            "router": entity_audit_router,
            "prefix": "/entities",
            "tags": ["Entity Audit"],
            "auth": True,
        },
        {"router": graph_router, "prefix": "/graph", "tags": ["Graph"], "auth": True},
        # ── Prompt Studio ──────────────────────────────────────────
        {
            "router": prompt_studio_router,
            "prefix": "",
            "tags": ["Prompt Studio"],
            "auth": True,
        },
        # ── Dev & Debug ────────────────────────────────────────────
        {
            "router": debug_router,
            "prefix": "/debug",
            "tags": ["Debug Simulator"],
            "auth": True,
        },
        {
            "router": experiments_router,
            "prefix": "/experiments",
            "tags": ["Experiments"],
            "auth": True,
        },
        # ── SOTA Memory Systems ────────────────────────────────
        {
            "router": _sota_router(),
            "prefix": "/sota",
            "tags": ["SOTA Memory Systems"],
            "auth": True,
        },
        # ── RIP (Retrieval Intelligence Platform) ────────────────
        {
            "router": _rip_router(),
            "prefix": "",
            "tags": ["RIP — Retrieval Intelligence"],
            "auth": True,
        },
        # ── Orchestrator Hub ──────────────────────────────────────
        {
            "router": _orchestration_router(),
            "prefix": "/orchestration",
            "tags": ["Orchestrator Hub"],
            "auth": True,
        },
        # ── Pattern Factory ────────────────────────────────────────
        {
            "router": _patterns_router(),
            "prefix": "/orchestration",
            "tags": ["Pattern Factory"],
            "auth": True,
        },
        # ── Drift Detection ─────────────────────────────────────────
        {
            "router": _drift_router(),
            "prefix": "/orchestration",
            "tags": ["Drift Detection"],
            "auth": True,
        },
        # ── Kimchi (Execution Pipeline) ──────────────────────────
        {
            "router": _kimchi_router(),
            "prefix": "/kimchi",
            "tags": ["Kimchi Pipeline"],
            "auth": True,
        },
        # ── DAW ────────────────────────────────────────────────────
        {"router": daw_router, "prefix": "/daw", "tags": ["DAW"], "auth": True},
        # ── Sync ───────────────────────────────────────────────────
        {"router": sync_router, "prefix": "/sync", "tags": ["Sync"], "auth": True},
        # ── Knowledge Engine (heavyweight — registered after observability) ──
        {
            "router": _knowledge_router(),
            "prefix": "",
            "tags": ["Knowledge Engine"],
            "auth": True,
        },
        {
            "router": _governance_router(),
            "prefix": "/governance",
            "tags": ["Agent Governance"],
            "auth": True,
        },
        {
            "router": _obs_admin_router(),
            "prefix": "",
            "tags": ["Observability Admin"],
            "auth": True,
        },
        {
            "router": _docs_router(),
            "prefix": "",
            "tags": ["Documentation"],
            "auth": True,
        },
        # ── Knowledge Hub ──────────────────────────────────────────
        *_knowledge_hub_entries(api_prefix),
        # ── Agentic RBAC ───────────────────────────────────────────
        {
            "router": _authz_router(),
            "prefix": "/authz",
            "tags": ["Authorization — Agentic RBAC"],
            "auth": True,
        },
        # ── Team ───────────────────────────────────────────────────
        {"router": _team_router(), "prefix": "", "tags": ["Team"], "auth": True},
        # ── HITL Policy Builder ────────────────────────────────────
        {
            "router": _hitl_router(),
            "prefix": "/hitl",
            "tags": ["HITL - Policy Builder"],
            "auth": True,
        },
        # ── Writing Studio ───────────────────────────────────────────
        {
            "router": writing_router,
            "prefix": "/writing",
            "tags": ["Writing Studio"],
            "auth": True,
        },
        # ── Messaging Gateway ──────────────────────────────────────────
        {
            "router": messaging_router,
            "prefix": "/messaging",
            "tags": ["Messaging Gateway"],
            "auth": True,
        },
        # ── Evolver ─────────────────────────────────────────────────
        {
            "router": evolver_router,
            "prefix": "/evolver",
            "tags": ["Evolver — GEP/ATP"],
            "auth": True,
        },
        # ── Document Vault ──────────────────────────────────────────
        {
            "router": document_vault_router,
            "prefix": "",
            "tags": ["Document Vault"],
            "auth": True,
        },
        # ── Document Creator ──────────────────────────────────────────
        {
            "router": _document_creator_router(),
            "prefix": "",
            "tags": ["Document Creator"],
            "auth": True,
        },
        # ── Control Center ─────────────────────────────────────────
        {
            "router": _control_center_router(),
            "prefix": "",
            "tags": ["Control Center"],
            "auth": True,
        },
        # ── Admin Database ─────────────────────────────────────────
        {
            "router": _admin_db_router(),
            "prefix": "",
            "tags": ["Admin Database"],
            "auth": True,
        },
        # ── Multi-Source ETL ────────────────────────────────────────
        {
            "router": _etl_router(),
            "prefix": "/etl",
            "tags": ["Multi-Source ETL"],
            "auth": True,
        },
        # ── Database Connections ─────────────────────────────────────
        {
            "router": _database_connections_router(),
            "prefix": "/databases",
            "tags": ["Database Connections"],
            "auth": True,
        },
        # ── Unified Entity System (Triggers / Hooks / Rules) ──────────
        {
            "router": _unified_triggers_router(),
            "prefix": "",
            "tags": ["Unified Triggers"],
            "auth": True,
        },
        {
            "router": _unified_hooks_router(),
            "prefix": "",
            "tags": ["Unified Hooks"],
            "auth": True,
        },
        {
            "router": _unified_rules_router(),
            "prefix": "",
            "tags": ["Unified Rules"],
            "auth": True,
        },
        {
            "router": _unified_interceptors_router(),
            "prefix": "",
            "tags": ["Unified Interceptors"],
            "auth": True,
        },
        # ── ChatGPT MCP Integration ────────────────────────────────
        {
            "router": _chatgpt_mcp_router(),
            "prefix": "",
            "tags": ["ChatGPT MCP Integration"],
            "auth": True,
        },
    ]

    for entry in ROUTER_DEFINITIONS:
        router = entry["router"]
        prefix = f"{api_prefix}{entry['prefix']}"
        tags = entry.get("tags", [])
        deps = global_deps if entry.get("auth", True) else []

        app.include_router(router, prefix=prefix, tags=tags, dependencies=deps)

    logger.info(
        "Startup: Registered %d routers via declarative registry (P2-1)",
        len(ROUTER_DEFINITIONS),
    )


__all__ = ["register_routers"]
