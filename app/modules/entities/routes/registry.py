from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException
from app.modules.common.types.index import APIResponse
from app.core.common_lib_integration import common_memory
from common_lib.modules.orchestration.agent.schemas import AgentDefinition
from common_lib.modules.orchestration.skill.schemas import CapabilityDefinition
from common_lib.modules.orchestration.workflow.schemas import WorkflowDefinition
from app.modules.demo.routes.react_agent import _engine_manager, DEMO_TOOL_REGISTRY, get_available_workflows
import logging

logger = logging.getLogger(__name__)

def normalize_description(desc: Any) -> str:
    """Safely extracts a renderable string from various description formats."""
    if not desc:
        return ""
    if isinstance(desc, str):
        return desc
    if isinstance(desc, dict):
        return desc.get("short") or desc.get("long") or str(desc)
    return str(desc)

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
        # 1. TOOLS (459 total expected)
        if not entity_type or entity_type == "tools":
            tool_groups = {}
            # Add hardcoded
            for t in DEMO_TOOL_REGISTRY:
                cat = t.get("category", "demo")
                if cat not in tool_groups: tool_groups[cat] = []
                tool_groups[cat].append({"id": t["id"], "name": t["name"], "description": t["description"]})
            
            # Add dynamic
            if _engine_manager and _engine_manager.registry_svc:
                dynamic_tools = _engine_manager.registry_svc.get_tools_by_category()
                for cat, tools in dynamic_tools.items():
                    if cat not in tool_groups: tool_groups[cat] = []
                    for t in tools:
                        if any(ext["id"] == t["id"] for ext in tool_groups[cat]): continue
                        if (t.get("metadata") or {}).get("entity_type") == "workflow": continue
                        tool_groups[cat].append({"id": t["id"], "name": t["name"], "description": t["description"]})
            
            # Format as groups for UI parity
            formatted_tools = []
            for cat_id, tools in tool_groups.items():
                formatted_tools.append({
                    "id": cat_id,
                    "name": cat_id.replace("_", " ").title(),
                    "tools": tools
                })
            results["tools"] = sorted(formatted_tools, key=lambda x: x["name"])

        # 2. WORKFLOWS (71+ total expected)
        if not entity_type or entity_type == "workflows":
            # Consolidate engine discovery with memory definitions
            engine_groups = await get_available_workflows()
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
            
            engine_agents = []
            if _engine_manager:
                engine_agents = _engine_manager.list_available_agents()

            # UNIFY AGENTS
            agent_map = {a["id"]: a for a in engine_agents}
            for a in db_agents:
                if a.get("artifacts", {}).get("entity_type") == "skill": continue
                agent_map[a["id"]] = a
            
            for a in agent_map.values():
                a["description"] = normalize_description(a.get("description"))
                # Coordinate formats
                meta = a.get("metadata") or {}
                # Agents are always format: config, subtype: agent
                if "format" not in meta: meta["format"] = "config"
                if "subtype" not in meta: meta["subtype"] = "agent"
                a["metadata"] = meta
            
            results["agents"] = sorted(agent_map.values(), key=lambda x: x.get("name", x.get("id", "")))
            
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
            results["instructions"] = [p for p in all_prompts if p.get("logical_category") == "instructions"]
            results["guardrails"] = [p for p in all_prompts if p.get("logical_category") == "guardrails"]
            results["preferences"] = [p for p in all_prompts if p.get("logical_category") == "preferences"]
            results["knowledge"] = [p for p in all_prompts if p.get("logical_category") == "knowledge"]
            results["examples"] = [p for p in all_prompts if p.get("logical_category") == "examples"]
            
        # 4. MODELS
        if not entity_type or entity_type == "models":
            if _engine_manager:
                results["models"] = _engine_manager.list_available_models()
            else:
                results["models"] = []

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
            result = common_memory.save_agent_definition(
                e_id, 
                definition.get("identity", {}), 
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description
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
            result = common_memory.save_agent_definition(
                entity_id, 
                definition.get("identity", {}), 
                definition,
                category=category,
                tags=tags,
                metadata_json=metadata,
                description=description
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
