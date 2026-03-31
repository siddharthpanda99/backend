from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from app.modules.common.types.index import APIResponse
from app.core.common_lib_integration import common_memory
from app.modules.entities.services.vector_search import get_search_service
from common_lib.modules.orchestration.skill.schemas import CapabilityDefinition
from common_lib.modules.orchestration.workflow.schemas import WorkflowDefinition
from common_lib.modules.orchestration.agent.prompt_resolver import PromptResolver
from app.modules.agents.runtime.core import get_engine_manager
from app.modules.agents.runtime.tools.registry import BUILTIN_TOOL_REGISTRY
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
    if em and getattr(em, 'registry_svc', None):
        return em.registry_svc
    # Lazy-init the shared fallback
    if _shared_registry is None:
        try:
            from common_lib.modules.core_infrastructure.registry import RegistryService
            _shared_registry = RegistryService()
            _shared_registry.auto_register_common_lib_tools()
            logger.info("[EntityRegistry] Shared RegistryService initialised (%d tools)",
                        len(_shared_registry.list_tools()))
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

def is_modern_agent(agent_dict: Dict[str, Any]) -> bool:
    """Checks if an agent definition satisfies the 16+ section architectural standard."""
    definition = agent_dict.get("definition") or {}
    if not definition:
        return False
    
    # Heuristic: Modern agents have specific architectural blocks + significant section count
    core_sections = {"memory", "planning", "policies", "runtime", "routing", "registry"}
    keys = set(definition.keys())
    
    # Must have at least 12 keys and some core architectural blocks
    return len(keys) >= 12 and core_sections.intersection(keys)

router = APIRouter()

@router.get("/", response_model=APIResponse[Dict[str, Any]])
async def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type: tools, workflows, agents, skills, instructions, etc.")
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
                            if t["id"] in seen: continue
                            if (t.get("metadata") or {}).get("entity_type") == "workflow": continue
                            tool_groups[cat].append(
                                {"id": t["id"], "name": t["name"], "description": t["description"]}
                            )
                except Exception as exc:
                    logger.warning("[EntityRegistry] dynamic tool listing failed: %s", exc)

            results["tools"] = sorted(
                [{"id": cat_id, "name": cat_id.replace("_", " ").title(), "tools": tools}
                 for cat_id, tools in tool_groups.items()],
                key=lambda x: x["name"]
            )

        # 2. WORKFLOWS (71+ total expected)
        if not entity_type or entity_type == "workflows":
            # Consolidate engine discovery with memory definitions
            from app.modules.agents.runtime.routes import available_workflows
            engine_groups = await available_workflows()
            db_workflows = common_memory.list_workflow_definitions()
            
            # 1. Flatten everything for deduplication
            all_workflows_flat = {}
            for group in engine_groups:
                for item in group.get("items", []):
                    all_workflows_flat[item["id"]] = item
            
            for wf in db_workflows:
                w_id = wf.get("id")
                if w_id and w_id not in all_workflows_flat:
                    # Look for metadata inside the definition column if top-level is empty
                    definition = wf.get("definition") or {}
                    metadata = wf.get("metadata") or definition.get("metadata") or {}
                    
                    all_workflows_flat[w_id] = {
                        "id": w_id,
                        "name": wf.get("name") or w_id,
                        "description": normalize_description(wf.get("description")),
                        "metadata": metadata,
                        "artifacts": wf.get("artifacts", {})
                    }
            
            # 2. Group by Metadata Category
            final_groups = {}
            for wf in all_workflows_flat.values():
                meta = wf.get("metadata") or {}
                # Prioritize internal metadata
                cat = meta.get("category") or wf.get("category") or "General"
                
                # Coordination Correction: If it's a "Config" format and has a subtype, use the subtype as the category
                sub = meta.get("subtype")
                if (meta.get("format") == "config" or cat == "Configuration") and sub:
                    cat = sub.upper()
                
                if cat not in final_groups:
                    final_groups[cat] = []
                
                # Ensure description is normalized string and metadata is present
                wf["description"] = normalize_description(wf.get("description"))
                wf["metadata"] = meta
                final_groups[cat].append(wf)
            
            # 3. Format into Group Objects
            results["workflows"] = sorted([
                {
                    "id": f"wf_{cat.lower().replace(' ', '_')}",
                    "name": f"{cat} (Workflows)",
                    "items": sorted(items, key=lambda x: x.get("name", "")),
                    "type": "workflow"
                }
                for cat, items in final_groups.items()
            ], key=lambda x: x["name"])

        # 3. AGENTS & SKILLS
        if not entity_type or entity_type in ["agents", "skills", "instructions", "guardrails", "preferences", "knowledge", "examples", "base_agents"]:
            db_agents = common_memory.list_agent_definitions()
            db_skills = common_memory.list_skill_definitions()
            
            em = get_engine_manager()
            engine_agents = []
            if em:
                engine_agents = em.list_available_agents()

            # UNIFY AGENTS
            agent_map = {a["id"]: a for a in engine_agents}
            for a in db_agents:
                if a.get("artifacts", {}).get("entity_type") == "skill": continue
                agent_map[a["id"]] = a
            
            results["agents"] = sorted(
                [a for a in agent_map.values() if is_modern_agent(a)], 
                key=lambda x: x.get("name", x.get("id", ""))
            )
            
            # UNIFY SKILLS
            for s in db_skills:
                s["description"] = normalize_description(s.get("description"))
                meta = s.get("metadata") or {}
                # Skills are format: config, subtype: skill
                if "format" not in meta: meta["format"] = "config"
                if "subtype" not in meta: meta["subtype"] = "skill"
                s["metadata"] = meta
                
            results["skills"] = sorted(db_skills, key=lambda x: x.get("name", x.get("id", "")))
            
            # Additional prompt-based entities
            all_prompts = common_memory.list_prompt_definitions()
            # Normalize for frontend (it expects 'content' or 'text')
            for p in all_prompts:
                if 'system_prompt' in p and 'content' not in p:
                    p['content'] = p['system_prompt']

            results["instructions"] = [p for p in all_prompts if p.get("logical_category") == "instructions"]
            results["guardrails"] = [p for p in all_prompts if p.get("logical_category") == "guardrails"]
            results["preferences"] = [p for p in all_prompts if p.get("logical_category") == "preferences"]
            results["knowledge"] = [p for p in all_prompts if p.get("logical_category") == "knowledge"]
            results["examples"] = [p for p in all_prompts if p.get("logical_category") == "examples"]
            
        # 4. MODELS — always available, even before an agent is deployed
        if not entity_type or entity_type == "models":
            em = get_engine_manager()
            if not em:
                # No active agent yet — spin up a bare EngineManager just for
                # the filesystem scan. list_available_models() only needs
                # __init__; it never calls setup(), so this is safe and fast.
                try:
                    from inference_platform.core.engine_manager import EngineManager
                    class _DummyCtx:
                        adapter = service = None
                    em = EngineManager(_DummyCtx())
                except Exception as _em_err:
                    logger.warning("Could not create bare EngineManager for model scan: %s", _em_err)
            results["models"] = em.list_available_models() if em else []

        return APIResponse(data=results, message="Unified entity registry retrieved successfully")
    except Exception as e:
        logger.error(f"Failed to fetch unified registry: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=APIResponse[Dict[str, Any]])
async def create_entity(
    entity_type: str,
    definition: Dict[str, Any]
):
    """
    Unified creation endpoint for all system entities.
    Validates against Gold Standard Pydantic schemas.
    """
    try:
        e_id = definition.get("id")
        if not e_id:
            raise HTTPException(status_code=400, detail="Entity ID is required")

        # Common extraction
        category = definition.get("category")
        tags = definition.get("tags")
        metadata = definition.get("metadata") or definition.get("metadata_json") or {}
        description = normalize_description(definition.get("description"))

        if entity_type == "agent":
            # Validate
            AgentDefinition(**definition)
            # Extract raw prompt template and resolve it for Live Preview
            prompt_template = definition.get("system_prompt_override")
            resolved_prompt = None
            if prompt_template:
                try:
                    resolver = PromptResolver(common_memory)
                    resolved_prompt = resolver.resolve(definition, prompt_template)
                except Exception as exc:
                    logger.warning("[Registry] PromptResolver failed for %s: %s", e_id, exc)
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
            CapabilityDefinition(**definition)
            result = common_memory.save_skill_definition(
                e_id, 
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description
            )
        elif entity_type == "workflow":
            WorkflowDefinition(**definition)
            result = common_memory.save_workflow_definition(
                e_id, 
                definition,
                category=category,
                tags=tags,
                description=description,
                metadata_json=metadata
            )
        elif entity_type == "prompt":
            result = common_memory.save_prompt_definition(
                e_id, 
                definition.get("system_prompt", ""),
                category=category,
                logical_category=definition.get("logical_category") or category,
                tags=tags,
                description=description,
                metadata_json=metadata
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type: {entity_type}")
            
        return APIResponse(data=result, message=f"{entity_type.title()} created successfully")
    except Exception as e:
        logger.error(f"Failed to create {entity_type}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.put("/{entity_type}/{entity_id}", response_model=APIResponse[Dict[str, Any]])
async def update_entity(
    entity_type: str,
    entity_id: str,
    definition: Dict[str, Any]
):
    """Updates an existing entity in the database."""
    try:
        definition["id"] = entity_id # Enforce ID consistency
        
        # Common extraction
        category = definition.get("category")
        tags = definition.get("tags")
        metadata = definition.get("metadata") or definition.get("metadata_json") or {}
        description = normalize_description(definition.get("description"))

        if entity_type == "agent":
            AgentDefinition(**definition)
            # Extract raw prompt template and resolve it for Live Preview
            prompt_template = definition.get("system_prompt_override")
            resolved_prompt = None
            if prompt_template:
                try:
                    resolver = PromptResolver(common_memory)
                    resolved_prompt = resolver.resolve(definition, prompt_template)
                except Exception as exc:
                    logger.warning("[Registry] PromptResolver failed for %s: %s", entity_id, exc)
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
            CapabilityDefinition(**definition)
            result = common_memory.save_skill_definition(
                entity_id, 
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description
            )
        elif entity_type == "workflow":
            WorkflowDefinition(**definition)
            result = common_memory.save_workflow_definition(
                entity_id, 
                definition,
                category=category,
                tags=tags,
                description=description,
                metadata_json=metadata
            )
        elif entity_type == "prompt":
            result = common_memory.save_prompt_definition(
                entity_id, 
                definition.get("system_prompt", ""),
                category=category,
                logical_category=definition.get("logical_category") or category,
                tags=tags,
                description=description,
                metadata_json=metadata
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type: {entity_type}")
            
        return APIResponse(data=result, message=f"{entity_type.title()} updated successfully")
    except Exception as e:
        logger.error(f"Failed to update {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/{entity_type}/{entity_id}", response_model=APIResponse[bool])
async def delete_entity(
    entity_type: str,
    entity_id: str
):
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
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported entity type: {entity_type}")
            
        return APIResponse(data=result, message=f"{entity_type.title()} deleted successfully")
    except Exception as e:
        logger.error(f"Failed to delete {entity_type} {entity_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Shared Capability Sections
# ---------------------------------------------------------------------------

@router.get("/sections", response_model=APIResponse[list])
async def list_sections(
    section_type: Optional[str] = Query(None, description="Filter by section type, e.g. 'lifecycle', 'reasoning'")
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
            raise HTTPException(status_code=400, detail="section_id, section_type, and content are required")
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

@router.get("/agent/{agent_id}/resolved_prompt", response_model=APIResponse[Dict[str, Any]])
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
            message="Resolved prompt retrieved"
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
        prompt_template = agent.get("prompt_template") or (definition.get("system_prompt_override"))

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
            message="Prompt resolved and persisted"
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
            "agent_type": agent.get("agent_type", "specialist")
        }
        
        fm_block = "---\n" + yaml.dump(frontmatter, sort_keys=False) + "---\n\n"
        
        header = f"# {frontmatter['name']}\n\n"
        desc = normalize_description(agent.get("description"))
        if desc:
            header += f"{desc}\n\n"
            
        system_prompt = agent.get("resolved_prompt") or "*(No resolved prompt available)*"
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
                "content": md_content
            },
            message="Agent exported successfully as markdown"
        )
    except Exception as e:
        logger.error(f"Failed to export agent {agent_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
