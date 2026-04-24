from typing import List, Optional, Dict, Any, AsyncGenerator
import json
import asyncio
from fastapi import APIRouter, Query, HTTPException, BackgroundTasks, Form
from fastapi.responses import StreamingResponse
from app.modules.common.types.index import APIResponse
from app.core.common_lib_integration import common_memory
from app.modules.entities.services.vector_search import get_search_service
from common_lib.modules.orchestration.agents.skill.schemas import CapabilityDefinition
from common_lib.modules.workflows.standard.schemas import WorkflowDefinition
from common_lib.modules.orchestration.agents.agent.cognition.resolver import PromptResolver
from app.modules.agents.runtime.core import get_engine_manager
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
from common_lib.modules.orchestration.infrastructure.sd.models import (
    SdWildcardRecord,
    SdWeightedPromptRecord,
    SdKeywordRecord,
)
from sqlalchemy import select
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared RegistryService — available even before an agent is deployed.
# Performs auto-discovery of all common_lib YAML tools once per process.
# ---------------------------------------------------------------------------
_shared_registry = None


def _get_registry_svc():
    """Return a ready RegistryService, preferring the engine manager's if deployed."""
    global _shared_registry
    em = get_engine_manager()
    if em and getattr(em, "registry_svc", None):
        res = em.registry_svc
        # Inject search provider if missing
        if hasattr(res, "search_provider") and res.search_provider is None:
            search_svc = get_search_service()
            res.search_provider = search_svc.search
        return res

    # Lazy-init the shared fallback
    if _shared_registry is None:
        try:
            from common_lib.modules.core_infrastructure.registry import RegistryService
            from app.core.settings import get_settings

            settings = get_settings()
            _shared_registry = RegistryService()

            # Inject search provider immediately
            search_svc = get_search_service()
            _shared_registry.search_provider = search_svc.search

            _shared_registry.auto_register_common_lib_tools(
                exclude_categories=set(settings.EXCLUDE_TOOL_CATEGORIES)
            )
            logger.info(
                "[EntityRegistry] Shared RegistryService initialised (%d tools)",
                len(_shared_registry.list_tools()),
            )
        except Exception as exc:
            logger.warning("[EntityRegistry] RegistryService init failed: %s", exc)
    return _shared_registry


def normalize_description(desc: Any) -> str:
    """Safely extracts a renderable string from various description formats."""
    if not desc:
        return ""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return desc.get("short") or desc.get("long") or str(desc)
    return str(desc)


# is_modern_agent removed: V3 Gold Standard validator now handles all legacy migration.

router = APIRouter()


@router.get("/search", response_model=APIResponse[List[Dict[str, Any]]])
async def search_registry(
    q: str = Query(..., description="Search query"),
    type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(10, description="Max results"),
):
    """
    Search registry entities using vector similarity and keywords.
    """
    try:
        search_svc = get_search_service()
        results = await search_svc.search(query=q, entity_type=type, limit=limit)
        return APIResponse(data=results, message="Search results retrieved")
    except Exception as e:
        logger.error(f"Registry search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/references", response_model=APIResponse[Dict[str, Any]])
async def list_references(
    category: Optional[str] = Query(
        None,
        description="Filter by category: shared, templates, skills, tools, workflows, prompts",
    ),
    q: Optional[str] = Query(None, description="Semantic search query"),
    limit: int = Query(20, description="Max results"),
):
    """
    List available entity references for @ autocomplete in JSON editor.
    Supports semantic search to find the right entity faster.

    Categories:
    - shared: Shared sections (interaction, governance, lifecycle, etc.)
    - templates: Agent templates
    - skills: Available skills
    - tools: Available tools
    - workflows: Available workflows
    - prompts: Available prompts
    """
    from app.core.common_lib_integration import common_memory

    results = {"categories": [], "items": []}

    try:
        memory = common_memory

        # Get category list if no specific category requested
        if not category:
            results["categories"] = [
                {
                    "id": "shared",
                    "name": "Shared Sections",
                    "description": "Reusable agent capability sections",
                },
                {
                    "id": "templates",
                    "name": "Templates",
                    "description": "Agent templates for cloning",
                },
                {"id": "skills", "name": "Skills", "description": "Available skills"},
                {"id": "tools", "name": "Tools", "description": "Available tools"},
                {
                    "id": "workflows",
                    "name": "Workflows",
                    "description": "Workflow definitions",
                },
                {"id": "prompts", "name": "Prompts", "description": "Prompt templates"},
            ]

        # Fetch items based on category
        items = []

        if category == "shared" or not category:
            # Shared sections
            sections = memory.list_shared_sections()
            for s in sections:
                items.append(
                    {
                        "id": s.get("id", ""),
                        "name": s.get("id", "").replace("_", " ").title(),
                        "type": "shared",
                        "description": f"Shared {s.get('type', 'section')}",
                        "content_preview": str(s.get("content", ""))[:100]
                        if s.get("content")
                        else "",
                    }
                )

        if category == "templates" or not category:
            # Agent templates (agents with template_id set)
            agents = memory.list_agent_definitions()
            for a in agents:
                if a.get("template_id") or a.get("data_config"):
                    items.append(
                        {
                            "id": a.get("id", ""),
                            "name": a.get("name", ""),
                            "type": "template",
                            "description": a.get("description", "")[:100]
                            if a.get("description")
                            else "",
                        }
                    )

        if category == "skills" or not category:
            skills = memory.list_skill_definitions()
            for s in skills:
                items.append(
                    {
                        "id": s.get("id", ""),
                        "name": s.get("name", ""),
                        "type": "skill",
                        "description": s.get("description", "")[:100]
                        if s.get("description")
                        else "",
                    }
                )

        if category == "tools" or not category:
            tools = memory.list_tool_definitions()
            for t in tools:
                items.append(
                    {
                        "id": t.get("id", ""),
                        "name": t.get("name", ""),
                        "type": "tool",
                        "description": t.get("description", "")[:100]
                        if t.get("description")
                        else "",
                    }
                )

        if category == "workflows" or not category:
            workflows = memory.list_workflow_definitions()
            for w in workflows:
                items.append(
                    {
                        "id": w.get("id", ""),
                        "name": w.get("name", ""),
                        "type": "workflow",
                        "description": w.get("description", "")[:100]
                        if w.get("description")
                        else "",
                    }
                )

        if category == "prompts" or not category:
            prompts = memory.list_prompt_definitions()
            for p in prompts:
                items.append(
                    {
                        "id": p.get("id", ""),
                        "name": p.get("name", ""),
                        "type": "prompt",
                        "description": p.get("description", "")[:100]
                        if p.get("description")
                        else "",
                    }
                )

        # If search query provided, do semantic search
        if q and items:
            try:
                search_svc = get_search_service()
                # Search across items using semantic search
                # Build combined text for each item
                for item in items:
                    item["_search_text"] = (
                        f"{item['name']} {item.get('description', '')} {item.get('type', '')}"
                    )

                # Use the registry search service
                search_results = await search_svc.search(
                    query=q, entity_type=category, limit=limit
                )

                # Map search results back to items
                if search_results:
                    matched_ids = {r.get("id") for r in search_results}
                    # Prioritize matched items, then add others
                    matched = [i for i in items if i["id"] in matched_ids]
                    others = [i for i in items if i["id"] not in matched_ids]
                    items = matched + others[: limit - len(matched)]
                else:
                    items = items[:limit]
            except Exception as search_err:
                logger.warning(
                    f"Semantic search failed, using text match: {search_err}"
                )
                # Fallback to simple text match
                q_lower = q.lower()
                matched = [
                    i
                    for i in items
                    if q_lower in i.get("name", "").lower()
                    or q_lower in i.get("description", "").lower()
                ]
                others = [i for i in items if i not in matched]
                items = matched + others[: limit - len(matched)]
        else:
            items = items[:limit]

        results["items"] = items

        return APIResponse(data=results, message="References retrieved")

    except Exception as e:
        logger.error(f"Failed to get references: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/progress")
async def sync_progress_stream():
    """
    SSE stream for registry synchronization and vector indexing progress.
    Used by the SyncProgressBadge in the UI.
    """

    async def progress_generator() -> AsyncGenerator[str, None]:
        search_svc = get_search_service()
        tracker = search_svc.tracker

        last_sent = None

        while True:
            # Build current state
            state = {
                "current": tracker.current,
                "total": tracker.total,
                "status": tracker.status,
                "description": tracker.description,
            }

            # Only send if state changed or periodically
            if state != last_sent:
                yield f"data: {json.dumps(state)}\n\n"
                last_sent = state

            # Stop stream if completed or idle for a bit
            if tracker.status in ["completed", "error"]:
                # Send one last completion message then wait
                await asyncio.sleep(2)
                if tracker.status in ["completed", "error"]:
                    # Reset after a cooldown so badge can fade out
                    tracker.reset()
                    break

            await asyncio.sleep(0.5)

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.get("/{entity_type}/{entity_id}", response_model=APIResponse[Dict[str, Any]])
async def get_entity(entity_type: str, entity_id: str):
    """
    Get a single entity by its type and ID.
    Supports agents, skills, workflows, and prompts.
    """
    try:
        data = None
        if entity_type == "agent":
            data = common_memory.get_agent_definition(entity_id)
        elif entity_type == "skill":
            data = common_memory.get_skill_definition(entity_id)
        elif entity_type == "workflow":
            data = common_memory.get_workflow_definition(entity_id)
        elif entity_type == "prompt":
            data = common_memory.get_prompt_definition(entity_id)

        if not data:
            raise HTTPException(
                status_code=404,
                detail=f"{entity_type.capitalize()} '{entity_id}' not found",
            )

        # Convert to dict if it's a Pydantic model
        if hasattr(data, "model_dump"):
            data_dict = data.model_dump()
        elif hasattr(data, "dict"):
            data_dict = data.dict()
        else:
            data_dict = data

        return APIResponse(
            data=data_dict, message=f"{entity_type.capitalize()} retrieved successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=APIResponse[Dict[str, Any]])
async def list_entities(
    entity_type: Optional[str] = Query(
        None,
        description="Filter by entity type: tools, workflows, agents, skills, instructions, etc.",
    ),
):
    """
    Unified registry for all system entities (Tools, Workflows, Agents, Skills, Prompts).
    Consolidates data from memory stores and active registries.
    """
    results = {}

    try:
        # 1. TOOLS — always use the shared RegistryService; prefer engine manager when deployed
        if not entity_type or entity_type == "tools":
            tool_groups = {}

            # Add the static builtin metadata stubs first
            for t in BUILTIN_TOOL_REGISTRY:
                cat = t.get("category", "general")
                tool_groups.setdefault(cat, []).append(
                    {"id": t["id"], "name": t["name"], "description": t["description"]}
                )

            # Overlay with all dynamic tools from the registry
            registry_svc = _get_registry_svc()
            if registry_svc:
                try:
                    dynamic_tools = registry_svc.get_tools_by_category()
                    for cat, tools in dynamic_tools.items():
                        tool_groups.setdefault(cat, [])
                        seen = {t["id"] for t in tool_groups[cat]}
                        for t in tools:
                            if t["id"] in seen:
                                continue
                            if (t.get("metadata") or {}).get(
                                "entity_type"
                            ) == "workflow":
                                continue
                            tool_groups[cat].append(
                                {
                                    "id": t["id"],
                                    "name": t["name"],
                                    "description": t["description"],
                                }
                            )
                except Exception as exc:
                    logger.warning(
                        "[EntityRegistry] dynamic tool listing failed: %s", exc
                    )

            results["tools"] = sorted(
                [
                    {
                        "id": cat_id,
                        "name": cat_id.replace("_", " ").title(),
                        "tools": tools,
                    }
                    for cat_id, tools in tool_groups.items()
                ],
                key=lambda x: x["name"],
            )

        # 2. WORKFLOWS (71+ total expected)
        if not entity_type or entity_type == "workflows":
            try:
                # Consolidate engine discovery with memory definitions
                from app.modules.agents.runtime.routes import available_workflows

                engine_groups = await available_workflows()
                db_workflows = common_memory.list_workflow_definitions()

                # 1. Flatten everything for deduplication
                all_workflows_flat = {}
                for group in engine_groups:
                    for item in group.get("items", []):
                        if isinstance(item, dict) and "id" in item:
                            all_workflows_flat[item["id"]] = item

                for wf in db_workflows:
                    w_id = wf.get("id")
                    if w_id and w_id not in all_workflows_flat:
                        # Look for metadata inside the definition column if top-level is empty
                        definition = wf.get("definition") or {}
                        metadata = (
                            wf.get("metadata") or definition.get("metadata") or {}
                        )

                        all_workflows_flat[w_id] = {
                            "id": w_id,
                            "name": wf.get("name") or w_id,
                            "description": normalize_description(wf.get("description")),
                            "input_schema": wf.get("input_schema"),
                            "output_schema": wf.get("output_schema"),
                            "metadata": metadata,
                            "artifacts": wf.get("artifacts", {}),
                        }

                # 2. Group by Metadata Category
                final_groups = {}
                for wf in all_workflows_flat.values():
                    meta = wf.get("metadata") or {}
                    # Prioritize internal metadata
                    cat = meta.get("category") or wf.get("category") or "General"

                    # Coordination Correction: If it's a "Config" format and has a subtype, use the subtype as the category
                    sub = meta.get("subtype")
                    if (
                        meta.get("format") == "config" or cat == "Configuration"
                    ) and sub:
                        cat = sub.upper()

                    if cat not in final_groups:
                        final_groups[cat] = []

                    # Ensure description is normalized string and metadata is present
                    wf["description"] = normalize_description(wf.get("description"))
                    wf["metadata"] = meta
                    final_groups[cat].append(wf)

                # 3. Format into Group Objects
                results["workflows"] = sorted(
                    [
                        {
                            "id": f"wf_{cat.lower().replace(' ', '_')}",
                            "name": f"{cat} (Workflows)",
                            "items": sorted(items, key=lambda x: x.get("name", "")),
                            "type": "workflow",
                        }
                        for cat, items in final_groups.items()
                    ],
                    key=lambda x: x["name"],
                )
            except Exception as e:
                logger.error(f"Workflow consolidation failed: {e}")
                results["workflows"] = []

        # 3. AGENTS & SKILLS
        if not entity_type or entity_type in [
            "agents",
            "skills",
            "instructions",
            "guardrails",
            "preferences",
            "knowledge",
            "examples",
            "base_agents",
        ]:
            db_agents = common_memory.list_agent_definitions()
            db_skills = common_memory.list_skill_definitions()

            em = get_engine_manager()
            engine_agents = []
            if em:
                engine_agents = em.list_available_agents()

            # UNIFY AGENTS
            agent_map = {a["id"]: a for a in engine_agents}
            for a in db_agents:
                if a.get("artifacts", {}).get("entity_type") == "skill":
                    continue
                agent_map[a["id"]] = a

            from common_lib.modules.orchestration.agents.agent.core.schemas import (
                AgentDefinition,
            )

            # Use resolved_definition for Pydantic validation (has fully resolved sections)
            # Fall back to definition if resolved not available
            validated_agents = []
            for a in agent_map.values():
                try:
                    # Try resolved_definition first (fully populated)
                    if a.get("resolved_definition"):
                        validated = AgentDefinition.model_validate(
                            a["resolved_definition"]
                        ).model_dump()
                    elif a.get("definition"):
                        # Fall back to definition - may have string references that fail validation
                        # Try with original, if fails use raw dump
                        try:
                            validated = AgentDefinition.model_validate(
                                a["definition"]
                            ).model_dump()
                        except Exception:
                            validated = a["definition"]
                    else:
                        validated = a

                    # Ensure root compatibility
                    if not validated.get("id") and validated.get("identity", {}).get(
                        "id"
                    ):
                        validated["id"] = validated["identity"]["id"]
                    if not validated.get("name") and validated.get("identity", {}).get(
                        "name"
                    ):
                        validated["name"] = validated["identity"]["name"]

                    validated_agents.append(validated)
                except Exception as e:
                    logger.warning(f"Agent validation failed for {a.get('id')}: {e}")
                    # Return raw data on validation failure
                    validated_agents.append(a.get("definition") or a)

            results["agents"] = sorted(
                validated_agents,
                key=lambda x: x.get("name", x.get("id", "")),
            )

            # UNIFY SKILLS
            from common_lib.modules.orchestration.agents.skill.schemas import (
                CapabilityDefinition,
            )

            validated_skills = []
            for s in db_skills:
                try:
                    # 1. Normalize (Safe Block)
                    s["description"] = normalize_description(s.get("description"))
                    meta = s.get("metadata") or {}
                    if "format" not in meta:
                        meta["format"] = "config"
                    if "subtype" not in meta:
                        meta["subtype"] = "skill"
                    s["metadata"] = meta

                    # 2. Validate
                    validated = CapabilityDefinition.model_validate(s).model_dump()

                    # Ensure root compatibility for UI (V3 often hides ID in identity)
                    if not validated.get("id") and validated.get("identity", {}).get(
                        "id"
                    ):
                        validated["id"] = validated["identity"]["id"]
                    if not validated.get("name") and validated.get("identity", {}).get(
                        "name"
                    ):
                        validated["name"] = validated["identity"]["name"]

                    validated_skills.append(validated)
                except Exception as e:
                    s_id = s.get("id") if isinstance(s, dict) else "unknown"
                    logger.warning(f"Skill processing failed for {s_id}: {e}")
                    # Return raw data on failure as long as it's a dict
                    if isinstance(s, dict):
                        validated_skills.append(s)

            results["skills"] = sorted(
                validated_skills,
                key=lambda x: x.get("name", x.get("id", "")),
            )

            from app.core.common_lib_integration import sync_manager

            # Additional prompt-based entities — Unified DB + Filesystem
            all_prompts = []

            # 1. Standard Prompts
            db_prompts = common_memory.list_prompt_definitions()
            for p in db_prompts:
                p["type"] = "prompt"
                all_prompts.append(p)

            # 2. Template Prompts
            try:
                db_templates = common_memory.list_template_definitions()
                for t in db_templates:
                    t["type"] = "template"
                    all_prompts.append(t)
            except Exception as _t_err:
                logger.warning(f"Failed to fetch templates: {_t_err}")

            # 3. Knowledgebase Entries
            try:
                kb_entries = common_memory.list_kb_entries()
                for kb in kb_entries:
                    kb["type"] = "knowledgebase"
                    kb["logical_category"] = "knowledge"
                    all_prompts.append(kb)
                results["knowledgebase"] = kb_entries
            except Exception as _kb_err:
                logger.warning(f"Failed to fetch KB entries: {_kb_err}")

            # 4. Snippets & Profiles (Shared Sections)
            try:
                snippets = common_memory.list_shared_sections(section_type="snippet")
                for s in snippets:
                    s["type"] = "snippet"
                    all_prompts.append(s)
                results["snippets"] = snippets

                profiles = common_memory.list_shared_sections(section_type="persona")
                for p in profiles:
                    p["type"] = "profile"
                    all_prompts.append(p)
                results["profiles"] = profiles
            except Exception as _sec_err:
                logger.warning(f"Failed to fetch shared sections: {_sec_err}")

            # 3. SD Artifacts (Direct Query)
            try:
                with common_memory._get_session() as session:
                    # Wildcards
                    wildcards = (
                        session.execute(select(SdWildcardRecord)).scalars().all()
                    )
                    for w in wildcards:
                        all_prompts.append(
                            {
                                "id": w.id,
                                "name": w.name or w.id,
                                "content": ", ".join(w.choices)
                                if isinstance(w.choices, list)
                                else str(w.choices),
                                "type": "wildcard",
                                "logical_category": "prompts",
                                "metadata": {
                                    "type": "sd_wildcard",
                                    "is_nested": w.is_nested,
                                },
                            }
                        )

                    # Weighted Prompts
                    weighted = (
                        session.execute(select(SdWeightedPromptRecord)).scalars().all()
                    )
                    for wp in weighted:
                        all_prompts.append(
                            {
                                "id": wp.id,
                                "name": wp.id,
                                "content": wp.positive_fragment,
                                "negative_fragment": wp.negative_fragment,
                                "type": "weighted_prompt",
                                "logical_category": "prompts",
                                "metadata": {
                                    "type": "sd_weighted",
                                    "category": wp.category,
                                },
                            }
                        )
            except Exception as _sd_err:
                logger.warning(f"Failed to query SD entities: {_sd_err}")

            # Normalize for frontend (it expects 'content' or 'text')
            for p in all_prompts:
                p["description"] = normalize_description(p.get("description"))
                if "system_prompt" in p and "content" not in p:
                    p["content"] = p["system_prompt"]

                # Ensure type is explicitly set for grouping
                if "logical_category" not in p:
                    # Default categorized mapping
                    cat = p.get("category", "")
                    if "instruction" in cat.lower() or "role" in cat.lower():
                        p["logical_category"] = "instructions"
                    elif "guardrail" in cat.lower():
                        p["logical_category"] = "guardrails"
                    elif "test" in cat.lower() or "example" in cat.lower():
                        p["logical_category"] = "examples"
                    elif "memory" in cat.lower() or "knowledge" in cat.lower():
                        p["logical_category"] = "knowledge"
                    else:
                        p["logical_category"] = "prompts"

            # Return all prompts as a master list for the UI (Resolves 500+ mismatch)
            results["prompts"] = all_prompts

            # Explicit sub-categories
            results["instructions"] = [
                p
                for p in all_prompts
                if p.get("logical_category") == "instructions"
                or p.get("type") == "instructions"
            ]
            results["guardrails"] = [
                p
                for p in all_prompts
                if p.get("logical_category") == "guardrails"
                or p.get("type") == "guardrails"
            ]
            results["preferences"] = [
                p for p in all_prompts if p.get("logical_category") == "preferences"
            ]
            results["memories"] = [
                p
                for p in all_prompts
                if p.get("logical_category") == "knowledge"
                or p.get("logical_category") == "memories"
            ]
            results["examples"] = [
                p for p in all_prompts if p.get("logical_category") == "examples"
            ]

            # 3.5 SLASH COMMANDS
            db_commands = common_memory.list_command_definitions()
            results["commands"] = db_commands

        # 4. MODELS — always available, even before an agent is deployed
        if not entity_type or entity_type == "models":
            try:
                from common_lib.modules.ai_models.container import AIModelsContainer

                model_container = AIModelsContainer()
                # Ensure health is checked first
                model_container.health_monitor.verify_all_models()
                models = model_container.registry_service.list_models()
                results["models"] = [m.model_dump() for m in models]
            except Exception as _m_err:
                logger.warning(
                    "Failed to fetch models from AIModelsContainer: %s", _m_err
                )
                # Fallback to old EngineManager scan if absolute disaster
                try:
                    from common_lib.modules.orchestration.inference.manager import (
                        EngineManager,
                    )

                    class _DummyCtx:
                        adapter = service = None

                    em = EngineManager(_DummyCtx())
                    results["models"] = em.list_available_models()
                except Exception:
                    results["models"] = []

        return APIResponse(
            data=results, message="Unified entity registry retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Failed to fetch unified registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/definitions", response_model=APIResponse[List[Dict[str, Any]]])
async def get_node_definitions():
    """
    Returns a flat list of all registerable nodes (tools, agents, skills)
    formatted for the Workflow Canvas NodeRegistry.
    """
    try:
        definitions = []
        registry_svc = _get_registry_svc()

        # 1. Tools
        if registry_svc:
            tool_groups = registry_svc.get_tools_by_category()
            for cat, tools in tool_groups.items():
                for tool in tools:
                    definitions.append({
                        "type": tool.get("id"),
                        "label": tool.get("name"),
                        "category": f"Tools/{cat.replace('_', ' ').title()}",
                        "description": tool.get("description"),
                        "inputs": tool.get("inputs", []),
                        "outputs": tool.get("outputs", []),
                        "defaultProperties": tool.get("default_properties", {}),
                        "propertyDefinitions": tool.get("property_definitions", []),
                        "version": tool.get("version", "1.0.0"),
                        "color": "#10b981" # Default tool color
                    })

        # 2. Agents
        db_agents = common_memory.list_agent_definitions()
        for agent in db_agents:
            definitions.append({
                "type": f"agent.{agent.get('id')}",
                "label": agent.get('name'),
                "category": f"Agents/{agent.get('category', 'General')}",
                "description": agent.get('description'),
                "inputs": [{"id": "input", "label": "User Input", "type": "string"}],
                "outputs": [{"id": "output", "label": "Response", "type": "string"}],
                "version": agent.get('version', '1.0.0'),
                "color": "#3b82f6" # Default agent color
            })

        # 3. Skills
        db_skills = common_memory.list_skill_definitions()
        for skill in db_skills:
            definitions.append({
                "type": f"skill.{skill.get('id')}",
                "label": skill.get('name'),
                "category": f"Skills/{skill.get('category', 'General')}",
                "description": skill.get('description'),
                "inputs": skill.get('inputs', []),
                "outputs": skill.get('outputs', []),
                "version": skill.get('version', '1.0.0'),
                "color": "#f59e0b" # Default skill color
            })

        return APIResponse(data=definitions, message="Node definitions retrieved successfully")
    except Exception as e:
        logger.error(f"Failed to fetch node definitions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=APIResponse[Dict[str, Any]])
async def get_registry_stats():
    """
    Get categorical statistics for all registry entities.
    Returns counts for Agents, Skills, Tools, Workflows, Prompts, etc.
    """
    try:
        stats = {
            "agents": {"total": 0},
            "skills": {"total": 0},
            "tools": {"total": 0, "categories": {}},
            "workflows": {"total": 0, "categories": {}},
            "prompts": {"total": 0, "categories": {}},
            "commands": {"total": 0},
            "models": {"total": 0},
            "templates": {"total": 0},
            "knowledgebase": {"total": 0},
            "snippets": {"total": 0},
            "profiles": {"total": 0},
        }

        # 1. Agents
        db_agents = common_memory.list_agent_definitions()
        stats["agents"]["total"] = len(db_agents)

        # 2. Skills
        db_skills = common_memory.list_skill_definitions()
        stats["skills"]["total"] = len(db_skills)

        # 3. Tools
        registry_svc = _get_registry_svc()
        if registry_svc:
            tool_groups = registry_svc.get_tools_by_category()
            total_tools = 0
            for cat, tools in tool_groups.items():
                cat_count = len(tools)
                stats["tools"]["categories"][cat] = cat_count
                total_tools += cat_count
            stats["tools"]["total"] = total_tools

        # 4. Workflows
        from app.modules.agents.runtime.routes import available_workflows

        engine_groups = await available_workflows()
        db_workflows = common_memory.list_workflow_definitions()

        # Consolidation logic similar to list_entities but just for counts
        wf_ids = set()
        wf_categories = {}
        for group in engine_groups:
            cat = group.get("name", "General")
            for item in group.get("items", []):
                if item["id"] not in wf_ids:
                    wf_ids.add(item["id"])
                    wf_categories[cat] = wf_categories.get(cat, 0) + 1

        for wf in db_workflows:
            w_id = wf.get("id")
            if w_id and w_id not in wf_ids:
                wf_ids.add(w_id)
                meta = (
                    wf.get("metadata") or wf.get("definition", {}).get("metadata") or {}
                )
                cat = meta.get("category") or wf.get("category") or "General"
                wf_categories[cat] = wf_categories.get(cat, 0) + 1

        stats["workflows"]["total"] = len(wf_ids)
        stats["workflows"]["categories"] = wf_categories

        # 5. Prompts (Logical Categories)
        db_prompts = common_memory.list_prompt_definitions()
        stats["prompts"]["total"] = len(db_prompts)
        prompt_categories = {}
        for p in db_prompts:
            # Handle potential None value for category
            raw_cat = (p.get("category") or "General").lower()

            # Logic grouping based on keywords
            if "instruction" in raw_cat or "role" in raw_cat:
                logic_cat = "Instructions"
            elif "guardrail" in raw_cat:
                logic_cat = "Guardrails"
            elif "test" in raw_cat or "example" in raw_cat:
                logic_cat = "Examples"
            elif "memory" in raw_cat or "knowledge" in raw_cat:
                logic_cat = "Knowledge"
            else:
                logic_cat = "General"
            prompt_categories[logic_cat] = prompt_categories.get(logic_cat, 0) + 1
        stats["prompts"]["categories"] = prompt_categories

        # 6. Commands
        db_commands = common_memory.list_command_definitions()
        stats["commands"]["total"] = len(db_commands)

        # 7. Models
        try:
            from common_lib.modules.ai_models.container import AIModelsContainer

            model_container = AIModelsContainer()
            models = model_container.registry_service.list_models()
            stats["models"]["total"] = len(models)
        except Exception:
            stats["models"]["total"] = 0

        # 8. Templates
        try:
            db_templates = common_memory.list_template_definitions()
            stats["templates"]["total"] = len(db_templates)
        except Exception:
            stats["templates"]["total"] = 0

        # 9. Knowledgebase
        try:
            kb_entries = common_memory.list_kb_entries()
            stats["knowledgebase"]["total"] = len(kb_entries)
        except Exception:
            stats["knowledgebase"]["total"] = 0

        # 10. Snippets & Profiles
        try:
            stats["snippets"]["total"] = len(
                common_memory.list_shared_sections(section_type="snippet")
            )
            stats["profiles"]["total"] = len(
                common_memory.list_shared_sections(section_type="persona")
            )
        except Exception:
            stats["snippets"]["total"] = 0
            stats["profiles"]["total"] = 0

        return APIResponse(data=stats, message="Registry statistics retrieved")
    except Exception as e:
        logger.error(f"Failed to get registry stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sync", response_model=APIResponse[Dict[str, Any]])
async def sync_registry(
    background_tasks: BackgroundTasks,
    force: bool = False,
    force_sync: bool = False,
    force_reindex: bool = False,
):
    """
    Triggers a full background synchronization lifecycle (Filesystem -> DB -> Vector Index).
    Supports granular bypassing of checksums for both DB sync and Vector indexing.
    """
    try:
        search_svc = get_search_service()
        registry_svc = _get_registry_svc()

        # Handle backward compatibility: if force is True, both specialized flags become True
        effective_force_sync = force or force_sync
        effective_force_reindex = force or force_reindex

        # Offload the entire lifecycle to background
        background_tasks.add_task(
            search_svc.run_full_lifecycle,
            registry_svc=registry_svc,
            force_sync=effective_force_sync,
            force_reindex=effective_force_reindex,
        )

        return APIResponse(
            data={"status": "started"},
            message="Registry synchronization and indexing started in background.",
        )
    except Exception as e:
        logger.error(f"Registry sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync/progress")
async def sync_progress_stream():
    """
    SSE stream for registry synchronization and vector indexing progress.
    Used by the SyncProgressBadge in the UI.
    """

    async def progress_generator() -> AsyncGenerator[str, None]:
        search_svc = get_search_service()
        tracker = search_svc.tracker

        last_sent = None

        while True:
            # Build current state
            state = {
                "current": tracker.current,
                "total": tracker.total,
                "status": tracker.status,
                "description": tracker.description,
            }

            # Only send if state changed or periodically
            if state != last_sent:
                yield f"data: {json.dumps(state)}\n\n"
                last_sent = state

            # Stop stream if completed or idle for a bit
            if tracker.status in ["completed", "error"]:
                # Send one last completion message then wait
                await asyncio.sleep(2)
                if tracker.status in ["completed", "error"]:
                    # Reset after a cooldown so badge can fade out
                    tracker.reset()
                    break

            await asyncio.sleep(0.5)

    return StreamingResponse(progress_generator(), media_type="text/event-stream")


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_entity(
    entity_type: str = Form(...), definition: Dict[str, Any] = Form(...)
):
    """
    Unified creation endpoint for all system entities.
    Validates against Gold Standard Pydantic schemas.
    """
    try:
        e_id = definition.get("id")
        if not e_id:
            raise HTTPException(status_code=400, detail="Entity ID is required")

        # Strip redundant, backend-only or legacy keys
        definition.pop("skill_yaml", None)
        definition.pop("fs_artifact", None)

        # Common extraction
        category = definition.get("category")
        tags = definition.get("tags")
        metadata = definition.get("metadata") or definition.get("metadata_json") or {}
        description = normalize_description(definition.get("description"))

        if entity_type == "agent":
            # Validate & Hydrate via V3 Gold Standard
            agent_obj = AgentDefinition.model_validate(definition)
            definition = agent_obj.model_dump()

            # Extract raw prompt template and resolve it for Live Preview
            prompt_template = agent_obj.logic.system_prompt or definition.get(
                "system_prompt_override"
            )
            resolved_prompt = None
            if prompt_template:
                try:
                    resolver = PromptResolver(common_memory)
                    resolved_prompt = resolver.resolve(definition, prompt_template)
                except Exception as exc:
                    logger.warning(
                        "[Registry] PromptResolver failed for %s: %s", e_id, exc
                    )

            result = common_memory.save_agent_definition(
                e_id,
                definition.get("identity", {}),
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description,
                prompt_template=prompt_template,
                resolved_prompt=resolved_prompt,
            )
        elif entity_type == "skill":
            skill_obj = CapabilityDefinition.model_validate(definition)
            definition = skill_obj.model_dump()
            result = common_memory.save_skill_definition(
                e_id,
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description,
            )
        elif entity_type == "workflow":
            WorkflowDefinition(**definition)
            result = common_memory.save_workflow_definition(
                e_id,
                definition,
                category=category,
                tags=tags,
                description=description,
                metadata_json=metadata,
            )
        elif entity_type == "prompt":
            result = common_memory.save_prompt_definition(
                e_id,
                definition.get("system_prompt", ""),
                category=category,
                logical_category=definition.get("logical_category") or category,
                tags=tags,
                description=description,
                metadata_json=metadata,
            )
        elif entity_type == "command":
            result = common_memory.save_command_definition(
                command_id=e_id,
                name=definition.get("name", e_id),
                trigger=definition.get("trigger", f"/{e_id}"),
                prompt_template=definition.get("prompt_template", ""),
                description=description,
                documentation_md=definition.get("documentation_md", ""),
                is_global=definition.get("is_global", True),
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported entity type: {entity_type}"
            )

        return APIResponse(
            data=result, message=f"{entity_type.title()} created successfully"
        )
    except Exception as e:
        logger.error(f"Failed to create {entity_type}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{entity_type}/{entity_id}", response_model=APIResponse[Dict[str, Any]])
async def update_entity(entity_type: str, entity_id: str, definition: Dict[str, Any]):
    """Updates an existing entity in the database."""
    try:
        definition["id"] = entity_id  # Enforce ID consistency

        # Strip redundant, backend-only or legacy keys
        definition.pop("skill_yaml", None)
        definition.pop("fs_artifact", None)

        # Common extraction
        category = definition.get("category")
        tags = definition.get("tags")
        metadata = definition.get("metadata") or definition.get("metadata_json") or {}
        description = normalize_description(definition.get("description"))

        if entity_type == "agent":
            # Validate & Hydrate via V3 Gold Standard
            agent_obj = AgentDefinition.model_validate(definition)
            definition = agent_obj.model_dump()

            # Extract raw prompt template and resolve it for Live Preview
            prompt_template = agent_obj.logic.system_prompt or definition.get(
                "system_prompt_override"
            )
            resolved_prompt = None
            if prompt_template:
                try:
                    resolver = PromptResolver(common_memory)
                    resolved_prompt = resolver.resolve(definition, prompt_template)
                except Exception as exc:
                    logger.warning(
                        "[Registry] PromptResolver failed for %s: %s", entity_id, exc
                    )
            result = common_memory.save_agent_definition(
                entity_id,
                definition.get("identity", {}),
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description,
                prompt_template=prompt_template,
                resolved_prompt=resolved_prompt,
            )
        elif entity_type == "skill":
            skill_obj = CapabilityDefinition.model_validate(definition)
            definition = skill_obj.model_dump()
            result = common_memory.save_skill_definition(
                entity_id,
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description,
            )
        elif entity_type == "workflow":
            WorkflowDefinition(**definition)
            result = common_memory.save_workflow_definition(
                entity_id,
                definition,
                category=category,
                tags=tags,
                description=description,
                metadata_json=metadata,
            )
        elif entity_type == "prompt":
            result = common_memory.save_prompt_definition(
                entity_id,
                definition.get("system_prompt", ""),
                category=category,
                logical_category=definition.get("logical_category") or category,
                tags=tags,
                description=description,
                metadata_json=metadata,
            )
        elif entity_type == "command":
            result = common_memory.save_command_definition(
                id=entity_id,
                name=definition.get("name", entity_id),
                prompt_template=definition.get("prompt_template", ""),
                description=description,
                documentation_md=definition.get("documentation_md", ""),
                is_global=definition.get("is_global", True),
                tags=tags,
                metadata=metadata,
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported entity type: {entity_type}"
            )

        return APIResponse(
            data=result, message=f"{entity_type.title()} updated successfully"
        )
    except Exception as e:
        logger.error(f"Failed to update {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{entity_type}/{entity_id}", response_model=APIResponse[bool])
async def delete_entity(entity_type: str, entity_id: str):
    """Deletes an entity from the database."""
    try:
        if entity_type == "agent":
            result = common_memory.delete_agent_definition(entity_id)
        elif entity_type == "skill":
            result = common_memory.delete_skill_definition(entity_id)
        elif entity_type == "workflow":
            result = common_memory.delete_workflow_definition(entity_id)
        elif entity_type == "prompt":
            result = common_memory.delete_prompt_definition(entity_id)
        elif entity_type == "command":
            # Assuming delete_command_definition exists or we add it
            try:
                result = common_memory.delete_command_definition(entity_id)
            except AttributeError:
                # Fallback if I forgot to add it to services.py (I'll add it now)
                from common_lib.modules.orchestration.command.models import (
                    CommandDefinitionRecord,
                )
                from sqlalchemy import delete

                with common_memory._get_session() as session:
                    stmt = delete(CommandDefinitionRecord).where(
                        CommandDefinitionRecord.id == entity_id
                    )
                    res = session.execute(stmt)
                    session.commit()
                    result = res.rowcount > 0
        else:
            raise HTTPException(
                status_code=400, detail=f"Unsupported entity type: {entity_type}"
            )

        return APIResponse(
            data=result, message=f"{entity_type.title()} deleted successfully"
        )
    except Exception as e:
        logger.error(f"Failed to delete {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Shared Capability Sections
# ---------------------------------------------------------------------------


@router.get("/sections", response_model=APIResponse[list])
async def list_sections(
    section_type: Optional[str] = Query(
        None, description="Filter by section type, e.g. 'lifecycle', 'reasoning'"
    ),
):
    """List all shared capability sections (seeded from YAML templates)."""
    try:
        sections = common_memory.list_shared_sections(section_type=section_type)
        return APIResponse(data=sections, message=f"Found {len(sections)} section(s)")
    except Exception as e:
        logger.error("Failed to list sections: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sections", response_model=APIResponse[Dict[str, Any]])
async def upsert_section(body: Dict[str, Any]):
    """
    Create or update a shared capability section.
    Updating a section does NOT automatically re-resolve all agents that reference it;
    use POST /registry/agent/{id}/resolve to re-resolve individually.
    """
    try:
        section_id = body.get("section_id")
        section_type = body.get("section_type")
        content = body.get("content")
        if not section_id or not section_type or content is None:
            raise HTTPException(
                status_code=400,
                detail="section_id, section_type, and content are required",
            )
        result = common_memory.save_shared_section(
            section_id=section_id,
            section_type=section_type,
            content=content,
            is_system=bool(body.get("is_system", False)),
            is_default=bool(body.get("is_default", False)),
        )
        return APIResponse(data={"section_id": result}, message="Section saved")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to save section: %s", e)
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Live Agent Preview — resolved_prompt endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/agent/{agent_id}/resolved_prompt", response_model=APIResponse[Dict[str, Any]]
)
async def get_resolved_prompt(agent_id: str):
    """
    Return the fully-expanded prompt for *agent_id*, as shown in the Live Agent Preview UI.
    Uses the cached resolved_prompt. To force re-resolution, use POST /…/resolve.
    """
    try:
        agent = common_memory.get_agent_definition(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
        return APIResponse(
            data={
                "agent_id": agent_id,
                "prompt_template": agent.get("prompt_template"),
                "resolved_prompt": agent.get("resolved_prompt"),
                "prompt_resolved_at": agent.get("prompt_resolved_at"),
            },
            message="Resolved prompt retrieved",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get resolved_prompt for %s: %s", agent_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agent/{agent_id}/resolve", response_model=APIResponse[Dict[str, Any]])
async def resolve_agent_prompt(agent_id: str):
    """
    Force re-resolution of the agent's prompt template from the current DB state of
    all shared sections. Useful after updating a shared section.
    Returns the freshly-resolved prompt (also persists it to the DB).
    """
    try:
        agent = common_memory.get_agent_definition(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        definition = agent.get("definition") or {}
        prompt_template = agent.get("prompt_template") or (
            definition.get("system_prompt_override")
        )

        resolver = PromptResolver(common_memory)
        resolved = resolver.resolve(definition, prompt_template)

        common_memory.save_agent_definition(
            agent_id,
            agent.get("identity", {}),
            definition,
            resolved_prompt=resolved,
        )

        return APIResponse(
            data={"agent_id": agent_id, "resolved_prompt": resolved},
            message="Prompt resolved and persisted",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to resolve prompt for %s: %s", agent_id, e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agent/{agent_id}/export")
async def export_agent_markdown(agent_id: str):
    """
    Export an agent definition as a high-fidelity Markdown file.
    Includes metadata, resolved system prompt, and full configuration.
    """
    try:
        agent = common_memory.get_agent_definition(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

        definition = agent.get("definition") or {}
        identity = definition.get("identity", {})

        # Build the MD content
        import yaml

        frontmatter = {
            "id": agent_id,
            "name": identity.get("display_name", agent.get("name")),
            "version": identity.get("version", "1.0.0"),
            "category": agent.get("category", "General"),
            "tags": agent.get("tags", []),
            "agent_type": agent.get("agent_type", "specialist"),
        }

        fm_block = "---\n" + yaml.dump(frontmatter, sort_keys=False) + "---\n\n"

        header = f"# {frontmatter['name']}\n\n"
        desc = normalize_description(agent.get("description"))
        if desc:
            header += f"{desc}\n\n"

        system_prompt = (
            agent.get("resolved_prompt") or "*(No resolved prompt available)*"
        )
        prompt_block = f"## 🤖 System Persona\n\n```markdown\n{system_prompt}\n```\n\n"

        # Include full architectural definition as a collapsible/detailed section
        import json

        config_block = "## ⚙️ Architectural Configuration\n\n"
        config_block += "The following configuration represents the 16+ architectural sections of this agent.\n\n"
        config_block += "```json\n" + json.dumps(definition, indent=2) + "\n```\n"

        md_content = f"{fm_block}{header}{prompt_block}{config_block}"

        return APIResponse(
            data={
                "agent_id": agent_id,
                "filename": f"{agent_id}.md",
                "content": md_content,
            },
            message="Agent exported successfully as markdown",
        )
    except Exception as e:
        logger.error(f"Failed to export agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
