"""Marketplace API Routes — thin routes delegating to MarketplaceService."""

import logging
import os
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, UploadFile, File

import yaml

from common_lib.modules.marketplace.service import MarketplaceService
from common_lib.paths import TEMPLATES_ROOT

router = APIRouter(tags=["marketplace"])

logger = logging.getLogger(__name__)

_svc = MarketplaceService()


# =============================================================================
# Memory Blocks Marketplace
# =============================================================================


@router.get("/blocks")
async def list_blocks(category: Optional[str] = Query(None)):
    """List all memory blocks, optionally filtered by category."""
    try:
        all_blocks = _svc.get_all_blocks()
        from common_lib.modules.memory.memory_driver import BlockCategory
        if category:
            all_blocks = [b for b in all_blocks if b.category.value == category.lower()]
        return {
            "status": "ok",
            "blocks": [_svc.block_to_dict(b) for b in all_blocks],
            "count": len(all_blocks),
        }
    except Exception as e:
        logger.error(f"Failed to list blocks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/categories")
async def list_block_categories():
    """List all block categories with counts."""
    try:
        all_blocks = _svc.get_all_blocks()
        from common_lib.modules.memory.memory_driver import BlockCategory
        categories = {}
        for cat in BlockCategory:
            count = sum(1 for b in all_blocks if b.category == cat)
            categories[cat.value] = {"label": cat.value.title(), "count": count}
        return {"status": "ok", "categories": categories}
    except Exception as e:
        logger.error(f"Failed to list categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}")
async def get_block(block_id: str):
    """Get a specific memory block by ID."""
    try:
        all_blocks = _svc.get_all_blocks()
        block = next((b for b in all_blocks if b.id == block_id), None)
        if not block:
            raise HTTPException(status_code=404, detail=f"Block not found: {block_id}")
        return {"status": "ok", "block": _svc.block_to_dict(block)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get block: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Profiles
# =============================================================================


@router.get("/profiles")
async def list_profiles():
    """List all pre-built memory profiles."""
    try:
        from common_lib.modules.memory.memory_driver import MEMORY_PROFILES
        return {
            "status": "ok",
            "profiles": [_svc.profile_to_dict(p) for p in MEMORY_PROFILES],
            "count": len(MEMORY_PROFILES),
        }
    except Exception as e:
        logger.error(f"Failed to list profiles: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str):
    """Get a specific memory profile by ID."""
    try:
        from common_lib.modules.memory.memory_driver import MEMORY_PROFILES
        profile = next((p for p in MEMORY_PROFILES if p.id == profile_id), None)
        if not profile:
            raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
        return {"status": "ok", "profile": _svc.profile_to_dict(profile)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/profiles/compose")
async def compose_profile(request: dict):
    """Compose a custom profile from blocks."""
    try:
        from common_lib.modules.memory.memory_driver import MemoryDriver
        block_ids = request.get("block_ids", [])
        driver = MemoryDriver()
        result = driver.compose_profile("custom", block_ids)
        return {"status": "ok", "profile": {"blocks": result, "block_count": len(result)}}
    except Exception as e:
        logger.error(f"Failed to compose profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Memory Hardware Marketplace
# =============================================================================


@router.get("/hardware")
async def list_hardware():
    """List memory hardware adapters."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry, MarketplaceCategory
        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.HARDWARE)
        return {"status": "ok", "items": [_svc.item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list hardware: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/algorithms")
async def list_algorithms():
    """List memory algorithms."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry, MarketplaceCategory
        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.ALGORITHM)
        return {"status": "ok", "items": [_svc.item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list algorithms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimizers")
async def list_optimizers():
    """List memory optimizers."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry, MarketplaceCategory
        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.OPTIMIZATION)
        return {"status": "ok", "items": [_svc.item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list optimizers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/utilities")
async def list_utilities():
    """List memory utilities."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry, MarketplaceCategory
        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.UTILITY)
        return {"status": "ok", "items": [_svc.item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list utilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/connectors")
async def list_connectors():
    """List memory connectors."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry, MarketplaceCategory
        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.CONNECTOR)
        return {"status": "ok", "items": [_svc.item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list connectors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_categories():
    """List marketplace categories with counts."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry, MarketplaceCategory
        registry = MarketplaceRegistry()
        categories = {}
        for cat in MarketplaceCategory:
            items = registry.list_items(cat)
            categories[cat.value] = {"label": cat.value.title(), "count": len(items)}
        return {"status": "ok", "categories": categories}
    except Exception as e:
        logger.error(f"Failed to list categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Entity Marketplace (Agents, Skills, Workflows)
# =============================================================================


@router.get("/agents")
async def list_agents():
    """List marketplace agents from templates."""
    try:
        items = _svc.scan_templates("agents")
        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Failed to list agents: {e}", exc_info=True)
        return {"status": "error", "items": [], "count": 0}


@router.get("/skills")
async def list_skills():
    """List marketplace skills from templates."""
    try:
        items = _svc.scan_templates("skills")
        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Failed to list skills: {e}", exc_info=True)
        return {"status": "error", "items": [], "count": 0}


@router.get("/workflows")
async def list_workflows():
    """List marketplace workflows from templates."""
    try:
        items = _svc.scan_templates("workflows")
        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Failed to list workflows: {e}", exc_info=True)
        return {"status": "error", "items": [], "count": 0}


@router.post("/upload")
async def upload_template(file: UploadFile = File(...)):
    """Upload a new marketplace entity YAML template."""
    if not (file.filename.endswith(".yaml") or file.filename.endswith(".yml")):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .yaml or .yml files are accepted.")

    try:
        content = await file.read()
        try:
            data = yaml.safe_load(content.decode("utf-8"))
        except yaml.YAMLError as ye:
            raise HTTPException(status_code=400, detail=f"Malformed YAML content: {ye}")

        if not data or not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="YAML content must represent a key-value object.")

        required_keys = ["id", "name", "type"]
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing mandatory fields: {', '.join(missing)}")

        normalized_type = _svc.normalize_entity_type(data["type"])
        if not normalized_type:
            raise HTTPException(status_code=400, detail="Invalid entity type. Must be 'skill', 'agent', or 'workflow'.")

        target_dir = os.path.join(TEMPLATES_ROOT, "marketplace", normalized_type)
        os.makedirs(target_dir, exist_ok=True)

        clean_id = _svc.make_clean_id(data["id"])
        if not clean_id:
            raise HTTPException(status_code=400, detail="Invalid entity ID.")

        target_path = os.path.join(target_dir, f"{clean_id}.yaml")
        data["type"] = normalized_type[:-1]  # singular
        data.setdefault("rating", 5.0)
        data.setdefault("downloads", 0)
        data.setdefault("category", "utility")
        data.setdefault("tags", [])

        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        logger.info(f"Uploaded marketplace {normalized_type[:-1]}: {clean_id}")
        return {"status": "ok", "message": f"Successfully uploaded {data['name']}", "item": data}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload template: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload template: {str(e)}")


@router.post("/install")
async def install_marketplace_item(request: dict):
    """Install a marketplace item by copying it to the active templates and running a DB sync."""
    item_id = request.get("id")
    item_type = request.get("type")

    if not item_id or not item_type:
        raise HTTPException(
            status_code=400, detail="Missing mandatory fields: 'id' and 'type'."
        )

    entity_type = item_type.lower()
    if entity_type in ["skill", "skills"]:
        normalized_type = "skills"
    elif entity_type in ["agent", "agents"]:
        normalized_type = "agents"
    elif entity_type in ["workflow", "workflows"]:
        normalized_type = "workflows"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid entity type. Must be 'skill', 'agent', or 'workflow'."
        )

    from common_lib.paths import TEMPLATES_ROOT
    # The ID of the template is typically the clean YAML filename (excluding standard prefixes if mapped, but matching clean_id in scan)
    clean_id = "".join(c for c in item_id if c.isalnum() or c in ("_", "-")).lower()
    source_path = os.path.join(TEMPLATES_ROOT, "marketplace", normalized_type, f"{clean_id}.yaml")
    if not os.path.exists(source_path):
        # Fallback to direct ID match if prefix was already included
        source_path = os.path.join(TEMPLATES_ROOT, "marketplace", normalized_type, f"{clean_id.replace('skill_', '').replace('agent_', '').replace('workflow_', '')}.yaml")
        if not os.path.exists(source_path):
            raise HTTPException(
                status_code=404, detail=f"Marketplace item template file not found: {clean_id}.yaml"
            )

    target_dir = os.path.join(TEMPLATES_ROOT, normalized_type)
    os.makedirs(target_dir, exist_ok=True)

    # Enforce platform extension: *.skill.yaml, *.agent.yaml, *.workflow.yaml
    singular_type = normalized_type[:-1]
    target_filename = f"{clean_id}.{singular_type}.yaml"
    target_path = os.path.join(target_dir, target_filename)

    try:
        # Load blueprint and translate to platform entity schema signature
        with open(source_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            data = {}

        # Set mandatory platform signature fields
        data["entity_type"] = singular_type
        # In importer, skill_id or agent_id is preferred
        data[f"{singular_type}_id"] = clean_id
        data["id"] = clean_id

        # Map default implementation blocks for runtime engines
        if singular_type in ("skill", "agent") and "implementation" not in data:
            class_name = "".join(word.title() for word in clean_id.replace("_", "-").split("-"))
            data["implementation"] = {
                "class": f"{class_name}{singular_type.title()}",
                "type": "python"
            }

        # Write translated file to live templates registry
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        # 2. Run the database sync using the existing sync_manager
        from app.core.common_lib_integration import sync_manager
        sync_manager.sync_all_from_files(force=True)

        logger.info(f"Successfully installed and synced marketplace item {item_id} of type {normalized_type}")
        return {
            "status": "ok",
            "message": f"Successfully installed and registered '{item_id}' into active database."
        }
    except Exception as e:
        logger.error(f"Failed to install marketplace item {item_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Installation failed: {str(e)}"
        )


