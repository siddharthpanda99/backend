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
            raise HTTPException(
                status_code=404, detail=f"Profile not found: {profile_id}"
            )
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
        return {
            "status": "ok",
            "profile": {"blocks": result, "block_count": len(result)},
        }
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
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

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
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

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
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

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
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

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
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

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
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

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


@router.get("/prompts")
async def list_prompts():
    """List marketplace prompts from DB (source=marketplace only)."""
    try:
        from app.core.common_lib_integration import common_memory as mem

        all_prompts = mem.list_prompt_definitions()
        marketplace_prompts = [
            p for p in all_prompts if p.get("source") == "marketplace"
        ]
        return {
            "status": "ok",
            "items": marketplace_prompts,
            "count": len(marketplace_prompts),
        }
    except Exception as e:
        logger.error(f"Failed to list prompts: {e}", exc_info=True)
        return {"status": "error", "items": [], "count": 0}


@router.get("/prompts/browse")
async def browse_prompts(
    modality: Optional[str] = Query(None),
    model_family: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
):
    """Browse prompts filtered by modality and model family.

    Returns grouped counts per modality and model_family for the UI filter chips,
    plus the filtered item list.
    """
    try:
        from common_lib.modules.orchestration.agents.prompt.models import PromptRecord
        from app.core.common_lib_integration import common_memory as mem

        full_set = mem.list_prompt_definitions()
        marketplace_prompts = [p for p in full_set if p.get("source") == "marketplace"]

        # Filter by modality
        if modality:
            marketplace_prompts = [
                p
                for p in marketplace_prompts
                if (p.get("modality") or "other") == modality
            ]

        # Filter by model_family
        if model_family:
            marketplace_prompts = [
                p
                for p in marketplace_prompts
                if (p.get("model_family") or "unknown") == model_family
            ]

        # Search in name/description/tags
        if search:
            q = search.lower()
            marketplace_prompts = [
                p
                for p in marketplace_prompts
                if q in (p.get("name") or "").lower()
                or q in (p.get("description") or "").lower()
                or any(q in t.lower() for t in (p.get("tags") or []))
            ]

        # Compute facet counts from all marketplace prompts (unfiltered)
        modality_counts: Dict[str, int] = {}
        model_family_counts: Dict[str, int] = {}
        all_marketplace = [p for p in full_set if p.get("source") == "marketplace"]
        for p in all_marketplace:
            m = p.get("modality") or "other"
            mf = p.get("model_family") or "unknown"
            modality_counts[m] = modality_counts.get(m, 0) + 1
            model_family_counts[mf] = model_family_counts.get(mf, 0) + 1

        # Flatten config into top-level for frontend consumption
        flattened = []
        for p in marketplace_prompts:
            cfg = p.get("config") or {}
            meta = p.get("metadata_json") or {}
            item = {
                **p,
                "image_url": cfg.get("image_url", ""),
                "image_base64": cfg.get("image_base64", ""),
                "image_width": cfg.get("image_width", 0),
                "image_height": cfg.get("image_height", 0),
                "prompt": p.get("system_prompt", ""),
                "negative_prompt": cfg.get("negative_prompt", ""),
                "model": cfg.get("model", ""),
                "model_version": cfg.get("model_version", ""),
                "parameters": cfg.get("parameters", {}),
                "views": meta.get("views", 0),
                "favorites": meta.get("favorites", 0),
                "price": cfg.get("price", 2.99),
                "sales": cfg.get("sales", 0),
                "features": cfg.get(
                    "features", ["Instant access", "Commercial use", "Money-back"]
                ),
                "word_count": len((p.get("system_prompt") or "").split()),
                "author": meta.get("author", p.get("author", "Unknown")),
            }
            flattened.append(item)

        return {
            "status": "ok",
            "items": flattened,
            "count": len(flattened),
            "facets": {
                "modalities": modality_counts,
                "model_families": model_family_counts,
            },
        }
    except Exception as e:
        logger.error(f"Failed to browse prompts: {e}", exc_info=True)
        return {"status": "error", "items": [], "count": 0, "facets": {}}


@router.post("/upload")
async def upload_template(file: UploadFile = File(...)):
    """Upload a new marketplace entity.

    For skills/agents/workflows: writes YAML to filesystem (legacy).
    For prompts: saves directly to DB — fully DB-driven.
    """
    if not (file.filename.endswith(".yaml") or file.filename.endswith(".yml")):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .yaml or .yml files are accepted.",
        )

    try:
        content = await file.read()
        try:
            data = yaml.safe_load(content.decode("utf-8"))
        except yaml.YAMLError as ye:
            raise HTTPException(status_code=400, detail=f"Malformed YAML content: {ye}")

        if not data or not isinstance(data, dict):
            raise HTTPException(
                status_code=400,
                detail="YAML content must represent a key-value object.",
            )

        required_keys = ["id", "name", "type"]
        missing = [k for k in required_keys if k not in data]
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Missing mandatory fields: {', '.join(missing)}",
            )

        normalized_type = _svc.normalize_entity_type(data["type"])
        if not normalized_type:
            raise HTTPException(
                status_code=400,
                detail="Invalid entity type. Must be 'skill', 'agent', 'workflow', or 'prompt'.",
            )

        clean_id = _svc.make_clean_id(data["id"])
        if not clean_id:
            raise HTTPException(status_code=400, detail="Invalid entity ID.")

        # ── PROMPTS: fully DB-driven ──
        if normalized_type == "prompts":
            from common_lib.modules.marketplace.prompt_categories import classify_prompt
            from app.core.common_lib_integration import common_memory as mem

            modality, model_family = classify_prompt(
                model_name=data.get("model", ""),
                logical_category=data.get("logical_category", ""),
                category=data.get("category", ""),
                model_tags=data.get("model_tags"),
            )

            success = mem.save_prompt_definition(
                entity_id=clean_id,
                system_prompt=data.get("prompt", ""),
                config={
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "category": data.get("category", "marketplace"),
                    "logical_category": data.get("logical_category", "prompts"),
                    "tags": data.get("tags", []),
                    "model": data.get("model", ""),
                    "model_version": data.get("model_version", ""),
                    "model_id": data.get("model_id", ""),
                    "prompt_type": data.get("prompt_type", ""),
                    "negative_prompt": data.get("negative_prompt", ""),
                    "image_url": data.get("image_url", ""),
                    "image_base64": data.get("image_base64", ""),
                    "image_width": data.get("image_width", 0),
                    "image_height": data.get("image_height", 0),
                    "parameters": data.get("parameters", {}),
                    "execution": data.get("execution", {}),
                },
                name=data.get("name", clean_id),
                description=data.get("description", ""),
                category="marketplace",
                logical_category="prompts",
                tags=data.get("tags", []),
                modality=modality,
                model_family=model_family,
                metadata_json={**data.get("metadata", {}), "source": "marketplace"},
                source="marketplace",
            )

            if not success:
                raise HTTPException(
                    status_code=500, detail="Failed to save prompt to database"
                )

            item = {
                "id": clean_id,
                "name": data.get("name", clean_id),
                "type": "prompt",
                "modality": modality,
                "model_family": model_family,
                "model": data.get("model", ""),
                "source": "marketplace",
            }

            logger.info(
                f"Uploaded marketplace prompt to DB: {clean_id} ({modality}/{model_family})"
            )
            return {
                "status": "ok",
                "message": f"Successfully uploaded {data['name']}",
                "item": item,
            }

        # ── SKILLS/AGENTS/WORKFLOWS: legacy filesystem ──
        target_dir = os.path.join(TEMPLATES_ROOT, "marketplace", normalized_type)
        os.makedirs(target_dir, exist_ok=True)

        target_path = os.path.join(target_dir, f"{clean_id}.yaml")
        data["type"] = normalized_type[:-1]  # singular
        data.setdefault("rating", 5.0)
        data.setdefault("downloads", 0)
        data.setdefault("category", "utility")
        data.setdefault("tags", [])

        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        logger.info(f"Uploaded marketplace {normalized_type[:-1]}: {clean_id}")
        return {
            "status": "ok",
            "message": f"Successfully uploaded {data['name']}",
            "item": data,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload template: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to upload template: {str(e)}"
        )


@router.post("/install")
async def install_marketplace_item(request: dict):
    """Install a marketplace item.

    For prompts: reads from DB, writes to live templates, syncs.
    For skills/agents/workflows: reads from filesystem, writes to live templates, syncs.
    """
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
    elif entity_type in ["prompt", "prompts"]:
        normalized_type = "prompts"
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid entity type. Must be 'skill', 'agent', 'workflow', or 'prompt'.",
        )

    from common_lib.paths import TEMPLATES_ROOT

    clean_id = "".join(c for c in item_id if c.isalnum() or c in ("_", "-")).lower()

    # ── PROMPTS: DB-driven install ──
    if normalized_type == "prompts":
        from app.core.common_lib_integration import common_memory as mem

        record = mem.get_prompt_definition(clean_id)
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"Marketplace prompt not found in DB: {clean_id}",
            )

        singular_type = "prompt"
        target_dir = os.path.join(TEMPLATES_ROOT, singular_type)
        os.makedirs(target_dir, exist_ok=True)

        cfg = record.get("config", {}) or {}
        live_data = {
            "id": clean_id,
            "entity_type": singular_type,
            f"{singular_type}_id": clean_id,
            "name": record.get("name") or cfg.get("name", clean_id),
            "description": record.get("description") or cfg.get("description", ""),
            "category": cfg.get("category", "marketplace"),
            "logical_category": cfg.get("logical_category", "prompts"),
            "tags": record.get("tags") or cfg.get("tags", []),
            "text": record.get("system_prompt", ""),
            "model_tags": [cfg.get("model", ""), cfg.get("model_version", "")],
            "prompt_text": record.get("system_prompt", ""),
            "negative_prompt": cfg.get("negative_prompt", ""),
            "modality": record.get("modality", ""),
            "model_family": record.get("model_family", ""),
            "model": cfg.get("model", ""),
            "model_version": cfg.get("model_version", ""),
            "model_id": cfg.get("model_id", ""),
            "parameters": cfg.get("parameters", {}),
            "metadata": record.get("metadata_json", {}),
            "execution": cfg.get("execution", {}),
            "source": "marketplace",
        }

        target_filename = f"{clean_id}.{singular_type}.yaml"
        target_path = os.path.join(target_dir, target_filename)
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(live_data, f, allow_unicode=True, sort_keys=False)

        from app.core.common_lib_integration import sync_manager

        sync_manager.sync_all_from_files(force=True)

        logger.info(f"Installed marketplace prompt from DB: {clean_id}")
        return {
            "status": "ok",
            "message": f"Successfully installed prompt '{clean_id}' into active database.",
        }

    # ── SKILLS/AGENTS/WORKFLOWS: legacy filesystem install ──
    source_path = os.path.join(
        TEMPLATES_ROOT, "marketplace", normalized_type, f"{clean_id}.yaml"
    )
    if not os.path.exists(source_path):
        source_path = os.path.join(
            TEMPLATES_ROOT,
            "marketplace",
            normalized_type,
            f"{clean_id.replace('skill_', '').replace('agent_', '').replace('workflow_', '')}.yaml",
        )
        if not os.path.exists(source_path):
            raise HTTPException(
                status_code=404,
                detail=f"Marketplace item template file not found: {clean_id}.yaml",
            )

    target_dir = os.path.join(TEMPLATES_ROOT, normalized_type)
    os.makedirs(target_dir, exist_ok=True)

    singular_type = normalized_type[:-1]
    target_filename = f"{clean_id}.{singular_type}.yaml"
    target_path = os.path.join(target_dir, target_filename)

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            data = {}

        data["entity_type"] = singular_type
        data[f"{singular_type}_id"] = clean_id
        data["id"] = clean_id

        if singular_type in ("skill", "agent") and "implementation" not in data:
            class_name = "".join(
                word.title() for word in clean_id.replace("_", "-").split("-")
            )
            data["implementation"] = {
                "class": f"{class_name}{singular_type.title()}",
                "type": "python",
            }

        # Write translated file to live templates registry
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        # 2. Run the database sync using the existing sync_manager
        from app.core.common_lib_integration import sync_manager

        sync_manager.sync_all_from_files(force=True)

        logger.info(
            f"Successfully installed and synced marketplace item {item_id} of type {normalized_type}"
        )
        return {
            "status": "ok",
            "message": f"Successfully installed and registered '{item_id}' into active database.",
        }
    except Exception as e:
        logger.error(
            f"Failed to install marketplace item {item_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")


# =============================================================================
# Marketplace Prompt CRUD (DB-driven)
# =============================================================================


@router.delete("/prompts/{prompt_id}")
async def delete_marketplace_prompt(prompt_id: str):
    """Delete a marketplace prompt from DB."""
    try:
        from app.core.common_lib_integration import common_memory as mem

        record = mem.get_prompt_definition(prompt_id)
        if not record or record.get("source") != "marketplace":
            raise HTTPException(
                status_code=404, detail=f"Marketplace prompt not found: {prompt_id}"
            )

        mem.delete_prompt_definition(prompt_id)
        logger.info(f"Deleted marketplace prompt: {prompt_id}")
        return {"status": "ok", "message": f"Deleted prompt '{prompt_id}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete prompt: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to delete prompt: {str(e)}"
        )


# =============================================================================
# Per-item Metadata (DB-backed custom fields: notes, warnings, versioning, etc.)
# =============================================================================


@router.get("/metadata/{item_id}")
async def get_item_metadata(item_id: str):
    """Get custom metadata for a marketplace item."""
    try:
        meta = _svc.get_metadata(item_id)
        return {"status": "ok", "item_id": item_id, "metadata": meta}
    except Exception as e:
        logger.error(f"Failed to get metadata for {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/metadata/{item_id}")
async def upsert_item_metadata(item_id: str, request: dict):
    """Create or update custom metadata for a marketplace item."""
    metadata = request.get("metadata", {})
    item_type = request.get("item_type", "skill")
    if not isinstance(metadata, dict):
        raise HTTPException(status_code=400, detail="metadata must be a JSON object")

    try:
        ok = _svc.upsert_metadata(item_id, metadata, item_type=item_type)
        if ok:
            return {
                "status": "ok",
                "message": f"Metadata saved for {item_id}",
                "metadata": metadata,
            }
        raise HTTPException(status_code=500, detail="Failed to save metadata")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upsert metadata for {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/metadata/{item_id}")
async def delete_item_metadata(item_id: str):
    """Delete custom metadata for a marketplace item."""
    try:
        ok = _svc.delete_metadata(item_id)
        if ok:
            return {"status": "ok", "message": f"Metadata deleted for {item_id}"}
        raise HTTPException(status_code=500, detail="Failed to delete metadata")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete metadata for {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metadata")
async def list_all_metadata(item_type: Optional[str] = Query(None)):
    """List all custom metadata records across marketplace items."""
    try:
        items = _svc.list_metadata(item_type=item_type)
        return {"status": "ok", "items": items, "count": len(items)}
    except Exception as e:
        logger.error(f"Failed to list metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
