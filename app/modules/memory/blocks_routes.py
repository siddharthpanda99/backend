"""Memory Blocks & Marketplace API Routes.

Provides REST endpoints for browsing memory blocks and marketplace items.
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(tags=["memory-blocks"])

logger = logging.getLogger(__name__)


# =============================================================================
# Memory Blocks Endpoints
# =============================================================================


@router.get("/blocks")
async def list_blocks(category: Optional[str] = Query(None)):
    """List all memory blocks, optionally filtered by category."""
    try:
        from common_lib.modules.memory.memory_driver import (
            CORE_BLOCKS,
            CONTEXT_BLOCKS,
            SEMANTIC_BLOCKS,
            SECURITY_BLOCKS,
            ADAPTATION_BLOCKS,
            STRATEGY_BLOCKS,
            EXECUTION_BLOCKS,
            FORECASTING_BLOCKS,
            ECONOMICS_BLOCKS,
            CAUSAL_BLOCKS,
            TESTING_BLOCKS,
            FEDERATION_BLOCKS,
            OBSERVABILITY_BLOCKS,
            VERSIONING_BLOCKS,
            PERSONA_BLOCKS,
            MULTIMODAL_BLOCKS,
            MQL_BLOCKS,
            STORES_BLOCKS,
            WORKING_BLOCKS,
        )

        all_blocks = (
            CORE_BLOCKS
            + CONTEXT_BLOCKS
            + SEMANTIC_BLOCKS
            + SECURITY_BLOCKS
            + ADAPTATION_BLOCKS
            + STRATEGY_BLOCKS
            + EXECUTION_BLOCKS
            + FORECASTING_BLOCKS
            + ECONOMICS_BLOCKS
            + CAUSAL_BLOCKS
            + TESTING_BLOCKS
            + FEDERATION_BLOCKS
            + OBSERVABILITY_BLOCKS
            + VERSIONING_BLOCKS
            + PERSONA_BLOCKS
            + MULTIMODAL_BLOCKS
            + MQL_BLOCKS
            + STORES_BLOCKS
            + WORKING_BLOCKS
        )

        if category:
            all_blocks = [b for b in all_blocks if b.category.value == category.lower()]

        return {
            "status": "ok",
            "blocks": [_block_to_dict(b) for b in all_blocks],
            "count": len(all_blocks),
        }
    except Exception as e:
        logger.error(f"Failed to list blocks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/categories")
async def list_block_categories():
    """List all block categories with counts."""
    try:
        from common_lib.modules.memory.memory_driver import (
            CORE_BLOCKS,
            CONTEXT_BLOCKS,
            SEMANTIC_BLOCKS,
            SECURITY_BLOCKS,
            ADAPTATION_BLOCKS,
            STRATEGY_BLOCKS,
            EXECUTION_BLOCKS,
            FORECASTING_BLOCKS,
            ECONOMICS_BLOCKS,
            CAUSAL_BLOCKS,
            TESTING_BLOCKS,
            FEDERATION_BLOCKS,
            OBSERVABILITY_BLOCKS,
            VERSIONING_BLOCKS,
            PERSONA_BLOCKS,
            MULTIMODAL_BLOCKS,
            MQL_BLOCKS,
            STORES_BLOCKS,
            WORKING_BLOCKS,
            BlockCategory,
        )

        all_blocks = (
            CORE_BLOCKS
            + CONTEXT_BLOCKS
            + SEMANTIC_BLOCKS
            + SECURITY_BLOCKS
            + ADAPTATION_BLOCKS
            + STRATEGY_BLOCKS
            + EXECUTION_BLOCKS
            + FORECASTING_BLOCKS
            + ECONOMICS_BLOCKS
            + CAUSAL_BLOCKS
            + TESTING_BLOCKS
            + FEDERATION_BLOCKS
            + OBSERVABILITY_BLOCKS
            + VERSIONING_BLOCKS
            + PERSONA_BLOCKS
            + MULTIMODAL_BLOCKS
            + MQL_BLOCKS
            + STORES_BLOCKS
            + WORKING_BLOCKS
        )

        categories = {}
        for cat in BlockCategory:
            count = sum(1 for b in all_blocks if b.category == cat)
            categories[cat.value] = {
                "label": cat.value.title(),
                "count": count,
            }

        return {"status": "ok", "categories": categories}
    except Exception as e:
        logger.error(f"Failed to list categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}")
async def get_block(block_id: str):
    """Get a specific memory block by ID."""
    try:
        from common_lib.modules.memory.memory_driver import (
            CORE_BLOCKS,
            CONTEXT_BLOCKS,
            SEMANTIC_BLOCKS,
            SECURITY_BLOCKS,
            ADAPTATION_BLOCKS,
            STRATEGY_BLOCKS,
            EXECUTION_BLOCKS,
            FORECASTING_BLOCKS,
            ECONOMICS_BLOCKS,
            CAUSAL_BLOCKS,
            TESTING_BLOCKS,
            FEDERATION_BLOCKS,
            OBSERVABILITY_BLOCKS,
            VERSIONING_BLOCKS,
            PERSONA_BLOCKS,
            MULTIMODAL_BLOCKS,
            MQL_BLOCKS,
            STORES_BLOCKS,
            WORKING_BLOCKS,
        )

        all_blocks = (
            CORE_BLOCKS
            + CONTEXT_BLOCKS
            + SEMANTIC_BLOCKS
            + SECURITY_BLOCKS
            + ADAPTATION_BLOCKS
            + STRATEGY_BLOCKS
            + EXECUTION_BLOCKS
            + FORECASTING_BLOCKS
            + ECONOMICS_BLOCKS
            + CAUSAL_BLOCKS
            + TESTING_BLOCKS
            + FEDERATION_BLOCKS
            + OBSERVABILITY_BLOCKS
            + VERSIONING_BLOCKS
            + PERSONA_BLOCKS
            + MULTIMODAL_BLOCKS
            + MQL_BLOCKS
            + STORES_BLOCKS
            + WORKING_BLOCKS
        )

        block = next((b for b in all_blocks if b.id == block_id), None)
        if not block:
            raise HTTPException(status_code=404, detail=f"Block not found: {block_id}")

        return {"status": "ok", "block": _block_to_dict(block)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get block: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/profiles")
async def list_profiles():
    """List all pre-built memory profiles."""
    try:
        from common_lib.modules.memory.memory_driver import MEMORY_PROFILES

        return {
            "status": "ok",
            "profiles": [_profile_to_dict(p) for p in MEMORY_PROFILES],
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

        return {"status": "ok", "profile": _profile_to_dict(profile)}
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
            "profile": {
                "blocks": result,
                "block_count": len(result),
            },
        }
    except Exception as e:
        logger.error(f"Failed to compose profile: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Compositions Endpoints
# (User-created compositions backed by YAML profile templates as defaults)
# =============================================================================

import json
from datetime import datetime, timezone

# In-process store for user-created/edited compositions.
# Keys are composition IDs.  On first request, the YAML profiles are injected
# as the initial seed so the UI always starts with real backend data.
_COMPOSITIONS: dict = {}
_COMPOSITIONS_SEEDED: bool = False


def _seed_compositions_from_profiles() -> None:
    """Populate _COMPOSITIONS from the YAML memory profile templates once."""
    global _COMPOSITIONS, _COMPOSITIONS_SEEDED
    if _COMPOSITIONS_SEEDED:
        return
    try:
        from common_lib.modules.memory.memory_driver import MEMORY_PROFILES

        now_iso = datetime.now(timezone.utc).isoformat()
        for profile in MEMORY_PROFILES:
            _COMPOSITIONS[profile.id] = {
                "id": profile.id,
                "name": profile.name,
                "description": profile.description,
                "block_ids": list(profile.blocks),
                "created_at": now_iso,
                "updated_at": now_iso,
                "source": "template",
            }
    except Exception as e:
        logger.error(f"Failed to seed compositions from profiles: {e}", exc_info=True)
    _COMPOSITIONS_SEEDED = True


@router.get("/compositions")
async def list_compositions():
    """List all memory compositions (seeded from YAML templates + user-created)."""
    try:
        _seed_compositions_from_profiles()
        return {
            "status": "ok",
            "compositions": list(_COMPOSITIONS.values()),
            "count": len(_COMPOSITIONS),
        }
    except Exception as e:
        logger.error(f"Failed to list compositions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compositions/{composition_id}")
async def get_composition(composition_id: str):
    """Get a specific composition by ID."""
    try:
        _seed_compositions_from_profiles()
        comp = _COMPOSITIONS.get(composition_id)
        if not comp:
            raise HTTPException(status_code=404, detail=f"Composition not found: {composition_id}")
        return {"status": "ok", "composition": comp}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class CompositionRequest(BaseModel):
    name: str
    description: str = ""
    block_ids: list


@router.post("/compositions")
async def create_composition(request: CompositionRequest):
    """Create a new user composition."""
    try:
        _seed_compositions_from_profiles()
        now_iso = datetime.now(timezone.utc).isoformat()
        comp_id = f"comp_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        comp = {
            "id": comp_id,
            "name": request.name,
            "description": request.description,
            "block_ids": request.block_ids,
            "created_at": now_iso,
            "updated_at": now_iso,
            "source": "user",
        }
        _COMPOSITIONS[comp_id] = comp
        return {"status": "ok", "composition": comp}
    except Exception as e:
        logger.error(f"Failed to create composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/compositions/{composition_id}")
async def update_composition(composition_id: str, request: CompositionRequest):
    """Update an existing composition."""
    try:
        _seed_compositions_from_profiles()
        existing = _COMPOSITIONS.get(composition_id)
        if not existing:
            raise HTTPException(status_code=404, detail=f"Composition not found: {composition_id}")
        existing.update({
            "name": request.name,
            "description": request.description,
            "block_ids": request.block_ids,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        _COMPOSITIONS[composition_id] = existing
        return {"status": "ok", "composition": existing}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/compositions/{composition_id}")
async def delete_composition(composition_id: str):
    """Delete a composition."""
    try:
        _seed_compositions_from_profiles()
        if composition_id not in _COMPOSITIONS:
            raise HTTPException(status_code=404, detail=f"Composition not found: {composition_id}")
        del _COMPOSITIONS[composition_id]
        return {"status": "ok", "message": f"Composition {composition_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Marketplace Endpoints
# =============================================================================


@router.get("/marketplace")
async def list_marketplace(
    category: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    platform: Optional[str] = Query("all"),
    agent: Optional[str] = Query("all"),
    harness: Optional[str] = Query("all"),
):
    """List marketplace items with optional filters."""
    try:
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

        registry = MarketplaceRegistry()

        if query:
            cat = MarketplaceCategory(category.lower()) if category else None
            items = registry.search(query, cat)
        elif category:
            cat = MarketplaceCategory(category.lower())
            items = registry.list_items(cat)
        else:
            items = registry.get_compatible(platform, agent, harness)

        return {
            "status": "ok",
            "items": [_item_to_dict(i) for i in items],
            "count": len(items),
        }
    except Exception as e:
        logger.error(f"Failed to list marketplace: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/categories")
async def list_marketplace_categories():
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
            categories[cat.value] = {
                "label": cat.value.title(),
                "count": len(items),
            }

        return {"status": "ok", "categories": categories}
    except Exception as e:
        logger.error(f"Failed to list marketplace categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/{item_id}")
async def get_marketplace_item(item_id: str):
    """Get a specific marketplace item by ID."""
    try:
        from common_lib.modules.memory.memory_marketplace import MarketplaceRegistry

        registry = MarketplaceRegistry()
        item = registry.get_item(item_id)
        if not item:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}")

        return {"status": "ok", "item": _item_to_dict(item)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get marketplace item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/hardware")
async def list_hardware():
    """List memory hardware adapters."""
    try:
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.HARDWARE)
        return {"status": "ok", "hardware": [_item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list hardware: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/algorithms")
async def list_algorithms():
    """List memory algorithms."""
    try:
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.ALGORITHM)
        return {"status": "ok", "algorithms": [_item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list algorithms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/optimizers")
async def list_optimizers():
    """List memory optimizers."""
    try:
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.OPTIMIZATION)
        return {"status": "ok", "optimizers": [_item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list optimizers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/utilities")
async def list_utilities():
    """List memory utilities."""
    try:
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.UTILITY)
        return {"status": "ok", "utilities": [_item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list utilities: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/marketplace/connectors")
async def list_connectors():
    """List memory connectors."""
    try:
        from common_lib.modules.memory.memory_marketplace import (
            MarketplaceRegistry,
            MarketplaceCategory,
        )

        registry = MarketplaceRegistry()
        items = registry.list_items(MarketplaceCategory.CONNECTOR)
        return {"status": "ok", "connectors": [_item_to_dict(i) for i in items]}
    except Exception as e:
        logger.error(f"Failed to list connectors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Helpers
# =============================================================================


def _block_to_dict(block) -> dict:
    return {
        "id": block.id,
        "name": block.name,
        "description": block.description,
        "category": block.category.value,
        "capabilities": block.capabilities,
        "dependencies": block.dependencies,
        "config": block.config,
        "enabled": block.enabled,
        "priority": block.priority,
        "usage_examples": getattr(block, "usage_examples", []),
        "related_blocks": getattr(block, "related_blocks", []),
        "performance_notes": getattr(block, "performance_notes", ""),
        "configuration_guide": getattr(block, "configuration_guide", ""),
        "api_reference": getattr(block, "api_reference", {}),
    }


def _profile_to_dict(profile) -> dict:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "blocks": profile.blocks,
        "block_ids": profile.blocks,
        "agent_type": profile.agent_type,
        "use_cases": profile.use_cases,
        "recommended": profile.recommended,
    }


def _item_to_dict(item) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "description": item.description,
        "category": item.category.value,
        "version": item.version,
        "author": item.author,
        "license": item.license,
        "tags": item.tags,
        "config": item.config,
        "dependencies": item.dependencies,
        "compatible_platforms": item.compatible_platforms,
        "compatible_agents": item.compatible_agents,
        "compatible_harnesses": item.compatible_harnesses,
        "rating": item.rating,
        "downloads": item.downloads,
        "metadata": item.metadata,
    }
