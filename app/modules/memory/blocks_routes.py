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
