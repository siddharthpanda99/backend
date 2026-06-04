"""Memory Blocks & Marketplace API Routes.

Provides REST endpoints for browsing memory blocks and marketplace items.
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select, text

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.memory.blueprint_models import (
    BlockOverrideRecord,
    CustomBlockRecord,
)

router = APIRouter(tags=["memory-blocks"])

logger = logging.getLogger(__name__)

_migration_checked = False


def ensure_schema_migrations(session: Session):
    global _migration_checked
    if _migration_checked:
        return
    _migration_checked = True
    try:
        session.execute(
            text("ALTER TABLE memory_block_overrides ADD COLUMN metadata_override TEXT")
        )
        session.commit()
        logger.info(
            "Migrated memory_block_overrides table: added metadata_override column."
        )
    except Exception:
        session.rollback()


def get_all_blocks():
    from common_lib.modules.memory.memory_driver import (
        ALL_BLOCKS,
        ensure_registry_initialized,
    )
    import common_lib.modules.memory.memory_driver as md

    ensure_registry_initialized()
    if not md.ALL_BLOCKS:
        md._registry_initialized = False
        ensure_registry_initialized()
    return md.ALL_BLOCKS


# =============================================================================
# Memory Blocks Endpoints
# =============================================================================


@router.get("/blocks")
async def list_blocks(
    category: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """List all memory blocks, optionally filtered by category, with database overrides merged."""
    try:
        import json

        ensure_schema_migrations(session)
        all_blocks = get_all_blocks()

        # Query all overrides from DB
        overrides = session.exec(select(BlockOverrideRecord)).all()
        overrides_dict = {o.block_id: o for o in overrides}

        merged_blocks = []
        for b in all_blocks:
            override = overrides_dict.get(b.id)
            block_dict = _block_to_dict(b)
            if override:
                try:
                    block_dict["config"] = json.loads(override.config)
                except Exception:
                    pass
                if override.priority is not None:
                    block_dict["priority"] = override.priority
                if (
                    hasattr(override, "metadata_override")
                    and override.metadata_override
                ):
                    try:
                        meta = json.loads(override.metadata_override)
                        for k, v in meta.items():
                            block_dict[k] = v
                    except Exception:
                        pass
                block_dict["is_overridden"] = True
            merged_blocks.append(block_dict)

        # Query custom blocks from DB and merge
        custom_blocks = session.exec(select(CustomBlockRecord)).all()
        for cb in custom_blocks:
            merged_blocks.append(_custom_block_to_dict(cb))

        if category:
            merged_blocks = [
                b for b in merged_blocks if b["category"].lower() == category.lower()
            ]

        return {
            "status": "ok",
            "blocks": merged_blocks,
            "count": len(merged_blocks),
        }
    except Exception as e:
        logger.error(f"Failed to list blocks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/categories")
async def list_block_categories(session: Session = Depends(get_session)):
    """List all block categories with counts."""
    try:
        from common_lib.modules.memory.memory_driver import BlockCategory

        ensure_schema_migrations(session)
        all_blocks = get_all_blocks()

        # Count built-in blocks
        categories = {}
        for cat in BlockCategory:
            count = sum(1 for b in all_blocks if b.category == cat)
            categories[cat.value] = {
                "label": cat.value.title(),
                "count": count,
            }

        # Include custom blocks
        custom_blocks = session.exec(select(CustomBlockRecord)).all()
        for cb in custom_blocks:
            cat = cb.category
            if cat not in categories:
                categories[cat] = {"label": cat.title(), "count": 0}
            categories[cat]["count"] += 1

        return {"status": "ok", "categories": categories}
    except Exception as e:
        logger.error(f"Failed to list categories: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blocks/{block_id}")
async def get_block(block_id: str, session: Session = Depends(get_session)):
    """Get a specific memory block by ID, merging DB overrides if present."""
    try:
        import json

        ensure_schema_migrations(session)
        all_blocks = get_all_blocks()

        block = next((b for b in all_blocks if b.id == block_id), None)
        if not block:
            cb = session.get(CustomBlockRecord, block_id)
            if not cb:
                raise HTTPException(
                    status_code=404, detail=f"Block not found: {block_id}"
                )
            return {"status": "ok", "block": _custom_block_to_dict(cb)}

        block_dict = _block_to_dict(block)
        override = session.get(BlockOverrideRecord, block_id)
        if override:
            try:
                block_dict["config"] = json.loads(override.config)
            except Exception:
                pass
            if override.priority is not None:
                block_dict["priority"] = override.priority
            if hasattr(override, "metadata_override") and override.metadata_override:
                try:
                    meta = json.loads(override.metadata_override)
                    for k, v in meta.items():
                        block_dict[k] = v
                except Exception:
                    pass
            block_dict["is_overridden"] = True

        return {"status": "ok", "block": block_dict}
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

from sqlmodel import Session, select, or_
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.memory.blueprint_models import (
    CompositionRecord,
    BlockOverrideRecord,
)


class BlockConfigOverrideRequest(BaseModel):
    config: dict
    priority: Optional[int] = None


@router.put("/blocks/{block_id}/config")
async def save_block_config_override(
    block_id: str,
    request: BlockConfigOverrideRequest,
    session: Session = Depends(get_session),
):
    """Save or update a memory block configuration override in the database."""
    try:
        import json
        from datetime import datetime, timezone

        # Check if the block actually exists in codebase
        all_blocks = get_all_blocks()
        if not any(b.id == block_id for b in all_blocks):
            raise HTTPException(
                status_code=404, detail=f"Memory block {block_id} does not exist."
            )

        record = session.get(BlockOverrideRecord, block_id)
        if not record:
            record = BlockOverrideRecord(
                block_id=block_id,
                config=json.dumps(request.config),
                priority=request.priority,
            )
        else:
            record.config = json.dumps(request.config)
            record.priority = request.priority
            record.updated_at = datetime.now(timezone.utc).isoformat()

        session.add(record)
        session.commit()
        session.refresh(record)

        # Merge override with base block and return it
        base_block = next(b for b in all_blocks if b.id == block_id)
        block_dict = _block_to_dict(base_block)
        block_dict["config"] = request.config
        if request.priority is not None:
            block_dict["priority"] = request.priority
        block_dict["is_overridden"] = True

        return {"status": "ok", "block": block_dict}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Failed to save block config override for {block_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blocks/{block_id}/config")
async def delete_block_config_override(
    block_id: str, session: Session = Depends(get_session)
):
    """Delete a block configuration override to restore default settings."""
    try:
        record = session.get(BlockOverrideRecord, block_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"No config override found for block {block_id}"
            )

        session.delete(record)
        session.commit()

        # Return default block
        all_blocks = get_all_blocks()
        base_block = next(b for b in all_blocks if b.id == block_id)
        return {"status": "ok", "block": _block_to_dict(base_block)}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(
            f"Failed to delete block config override for {block_id}: {e}", exc_info=True
        )
        raise HTTPException(status_code=500, detail=str(e))


def _seed_templates_to_db(session: Session) -> None:
    """Seed DB with YAML memory profile templates and mock compositions if they do not exist."""
    try:
        from common_lib.modules.memory.memory_driver import MEMORY_PROFILES

        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Seed YAML memory profiles
        for profile in MEMORY_PROFILES:
            existing = session.get(CompositionRecord, profile.id)
            if not existing:
                record = CompositionRecord(
                    id=profile.id,
                    name=profile.name,
                    description=profile.description,
                    block_ids=json.dumps(list(profile.blocks)),
                    source="template",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                session.add(record)

        # 2. Seed mock compositions from mockData.ts
        mock_compositions = [
            {
                "id": "comp_1780476000000",
                "name": "Standard Chatbot Profile",
                "description": "Optimal chatbot config with dialogue buffering and safety redaction filters.",
                "block_ids": [
                    "core.store",
                    "core.stats",
                    "context.session",
                    "security.pii",
                    "persona.profile",
                ],
                "source": "template",
            },
            {
                "id": "comp_1780476100000",
                "name": "Advanced Analyst Config",
                "description": "Full semantic links, causal graph processing, and structured multi-hop reasoning capabilities.",
                "block_ids": [
                    "core.store",
                    "core.stats",
                    "semantic.clusters",
                    "causal.graph",
                    "execution.reasoning",
                    "mql.parser",
                ],
                "source": "template",
            },
        ]

        for mock_comp in mock_compositions:
            existing = session.get(CompositionRecord, mock_comp["id"])
            if not existing:
                record = CompositionRecord(
                    id=mock_comp["id"],
                    name=mock_comp["name"],
                    description=mock_comp["description"],
                    block_ids=json.dumps(mock_comp["block_ids"]),
                    source=mock_comp["source"],
                    created_at=now_iso,
                    updated_at=now_iso,
                )
                session.add(record)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(
            f"Failed to seed template and mock compositions: {e}", exc_info=True
        )


@router.get("/compositions")
async def list_compositions(session: Session = Depends(get_session)):
    """List all memory compositions (seeded from YAML templates + user-created)."""
    try:
        _seed_templates_to_db(session)
        records = session.exec(
            select(CompositionRecord).order_by(CompositionRecord.created_at.desc())
        ).all()
        return {
            "status": "ok",
            "compositions": [_comp_to_dict(r) for r in records],
            "count": len(records),
        }
    except Exception as e:
        logger.error(f"Failed to list compositions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compositions/{composition_id}")
async def get_composition(composition_id: str, session: Session = Depends(get_session)):
    """Get a specific composition by ID."""
    try:
        record = session.get(CompositionRecord, composition_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Composition not found: {composition_id}"
            )
        return {"status": "ok", "composition": _comp_to_dict(record)}
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
async def create_composition(
    request: CompositionRequest, session: Session = Depends(get_session)
):
    """Create a new user composition."""
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        comp_id = f"comp_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        record = CompositionRecord(
            id=comp_id,
            name=request.name,
            description=request.description,
            block_ids=json.dumps(request.block_ids),
            source="user",
            created_at=now_iso,
            updated_at=now_iso,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"status": "ok", "composition": _comp_to_dict(record)}
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/compositions/{composition_id}")
async def update_composition(
    composition_id: str,
    request: CompositionRequest,
    session: Session = Depends(get_session),
):
    """Update an existing composition."""
    try:
        record = session.get(CompositionRecord, composition_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Composition not found: {composition_id}"
            )
        record.name = request.name
        record.description = request.description
        record.block_ids = json.dumps(request.block_ids)
        record.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"status": "ok", "composition": _comp_to_dict(record)}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/compositions/{composition_id}")
async def delete_composition(
    composition_id: str, session: Session = Depends(get_session)
):
    """Delete a composition."""
    try:
        record = session.get(CompositionRecord, composition_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Composition not found: {composition_id}"
            )
        session.delete(record)
        session.commit()
        return {"status": "ok", "message": f"Composition {composition_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete composition: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _comp_to_dict(r: CompositionRecord) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "block_ids": json.loads(r.block_ids)
        if isinstance(r.block_ids, str)
        else r.block_ids,
        "source": r.source,
        "blueprint_id": r.blueprint_id,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


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
        "name": getattr(block, "name", ""),
        "description": getattr(block, "description", ""),
        "category": block.category.value
        if hasattr(block.category, "value")
        else str(block.category),
        "capabilities": getattr(block, "capabilities", []),
        "dependencies": getattr(block, "dependencies", []),
        "config": getattr(block, "config", {}),
        "enabled": getattr(block, "enabled", True),
        "priority": getattr(block, "priority", 0),
        "usage_examples": getattr(block, "usage_examples", []),
        "related_blocks": getattr(block, "related_blocks", []),
        "performance_notes": getattr(block, "performance_notes", ""),
        "configuration_guide": getattr(block, "configuration_guide", ""),
        "api_reference": getattr(block, "api_reference", {}),
        "source": getattr(block, "source", "code"),
        "is_overridden": getattr(block, "is_overridden", False),
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


# =============================================================================
# Custom Block E2E Operations Endpoints & Models
# =============================================================================


class CustomBlockCreateRequest(BaseModel):
    id: str
    name: str
    description: str
    category: str
    capabilities: List[str] = []
    dependencies: List[str] = []
    related_blocks: List[str] = []
    config: dict = {}
    priority: int = 0
    performance_notes: str = ""
    configuration_guide: str = ""
    source: str = "user"


class CustomBlockUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    capabilities: Optional[List[str]] = None
    dependencies: Optional[List[str]] = None
    related_blocks: Optional[List[str]] = None
    config: Optional[dict] = None
    priority: Optional[int] = None
    performance_notes: Optional[str] = None
    configuration_guide: Optional[str] = None
    source: Optional[str] = None


class BlockSummarizeRequest(BaseModel):
    level: str = "short"
    tone: str = "professional"


@router.post("/blocks")
async def create_custom_block(
    request: CustomBlockCreateRequest, session: Session = Depends(get_session)
):
    """Create a new custom or cloned block definition in the database."""
    try:
        import json

        ensure_schema_migrations(session)

        # Check if exists in codebase static blocks
        all_blocks = get_all_blocks()
        if any(b.id == request.id for b in all_blocks):
            raise HTTPException(
                status_code=400,
                detail=f"A built-in block with ID '{request.id}' already exists.",
            )

        # Check if exists in db custom blocks
        existing = session.get(CustomBlockRecord, request.id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"A custom block with ID '{request.id}' already exists.",
            )

        record = CustomBlockRecord(
            id=request.id,
            name=request.name,
            description=request.description,
            category=request.category,
            capabilities=json.dumps(request.capabilities),
            dependencies=json.dumps(request.dependencies),
            related_blocks=json.dumps(request.related_blocks),
            config=json.dumps(request.config),
            enabled=True,
            priority=request.priority,
            performance_notes=request.performance_notes,
            configuration_guide=request.configuration_guide,
            source=request.source,
        )

        session.add(record)
        session.commit()
        session.refresh(record)
        return {"status": "ok", "block": _custom_block_to_dict(record)}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create custom block: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/blocks/{block_id}")
async def update_block(
    block_id: str,
    request: CustomBlockUpdateRequest,
    session: Session = Depends(get_session),
):
    """Update a custom block definition or set metadata/config overrides for a built-in block."""
    try:
        import json
        from datetime import datetime, timezone

        ensure_schema_migrations(session)

        # Check if it is a built-in codebase block
        all_blocks = get_all_blocks()
        base_block = next((b for b in all_blocks if b.id == block_id), None)

        if base_block:
            # Update or create override record
            record = session.get(BlockOverrideRecord, block_id)
            if not record:
                record = BlockOverrideRecord(
                    block_id=block_id,
                    config=json.dumps(request.config)
                    if request.config is not None
                    else json.dumps(base_block.config),
                    priority=request.priority
                    if request.priority is not None
                    else base_block.priority,
                    metadata_override="{}",
                )
            else:
                if request.config is not None:
                    record.config = json.dumps(request.config)
                if request.priority is not None:
                    record.priority = request.priority

            # Handle metadata overrides
            meta_override = {}
            if record.metadata_override:
                try:
                    meta_override = json.loads(record.metadata_override)
                except Exception:
                    pass

            # Map request fields into metadata_override
            for field in [
                "name",
                "description",
                "category",
                "capabilities",
                "dependencies",
                "related_blocks",
                "performance_notes",
                "configuration_guide",
                "source",
            ]:
                val = getattr(request, field)
                if val is not None:
                    meta_override[field] = val

            record.metadata_override = json.dumps(meta_override)
            record.updated_at = datetime.now(timezone.utc).isoformat()

            session.add(record)
            session.commit()
            session.refresh(record)

            # Return merged dictionary
            block_dict = _block_to_dict(base_block)
            block_dict["config"] = json.loads(record.config)
            block_dict["priority"] = record.priority
            for k, v in meta_override.items():
                block_dict[k] = v
            block_dict["is_overridden"] = True
            return {"status": "ok", "block": block_dict}

        else:
            # Check if it is a custom block
            record = session.get(CustomBlockRecord, block_id)
            if not record:
                raise HTTPException(
                    status_code=404, detail=f"Memory block '{block_id}' not found."
                )

            if request.name is not None:
                record.name = request.name
            if request.description is not None:
                record.description = request.description
            if request.category is not None:
                record.category = request.category
            if request.capabilities is not None:
                record.capabilities = json.dumps(request.capabilities)
            if request.dependencies is not None:
                record.dependencies = json.dumps(request.dependencies)
            if request.related_blocks is not None:
                record.related_blocks = json.dumps(request.related_blocks)
            if request.config is not None:
                record.config = json.dumps(request.config)
            if request.priority is not None:
                record.priority = request.priority
            if request.performance_notes is not None:
                record.performance_notes = request.performance_notes
            if request.configuration_guide is not None:
                record.configuration_guide = request.configuration_guide
            if request.source is not None:
                record.source = request.source

            record.updated_at = datetime.now(timezone.utc).isoformat()
            session.add(record)
            session.commit()
            session.refresh(record)
            return {"status": "ok", "block": _custom_block_to_dict(record)}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update block {block_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blocks/{block_id}")
async def delete_block(block_id: str, session: Session = Depends(get_session)):
    """Delete a custom block or reset a built-in block override."""
    try:
        ensure_schema_migrations(session)

        # Check codebase blocks
        all_blocks = get_all_blocks()
        base_block = next((b for b in all_blocks if b.id == block_id), None)

        if base_block:
            # Delete override if it exists
            override = session.get(BlockOverrideRecord, block_id)
            if override:
                session.delete(override)
                session.commit()
            return {
                "status": "ok",
                "message": f"Built-in block '{block_id}' reset to system defaults.",
            }

        else:
            # Delete custom block
            record = session.get(CustomBlockRecord, block_id)
            if not record:
                raise HTTPException(
                    status_code=404, detail=f"Memory block '{block_id}' not found."
                )
            session.delete(record)

            # Also clean up any overrides that might exist for this custom block ID
            override = session.get(BlockOverrideRecord, block_id)
            if override:
                session.delete(override)

            session.commit()
            return {"status": "ok", "message": f"Custom block '{block_id}' deleted."}

    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete block {block_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blocks/{block_id}/summarize")
async def summarize_block(
    block_id: str,
    request: BlockSummarizeRequest,
    session: Session = Depends(get_session),
):
    """Generate an AI cognitive summary of a memory block's capabilities and config."""
    try:
        ensure_schema_migrations(session)

        # Get the block dict
        res = await get_block(block_id, session)
        block_dict = res["block"]

        # Generate summary using generator function
        summary = generate_block_summary(block_dict, request.level, request.tone)
        return {"status": "ok", "summary": summary}
    except Exception as e:
        logger.error(f"Summarize block {block_id} failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def generate_block_summary(block_dict: dict, level: str, tone: str) -> str:
    tone_label = tone.title()
    name = block_dict.get("name", "Unknown")
    cat = block_dict.get("category", "Unknown")
    caps = ", ".join(block_dict.get("capabilities", [])) or "none"
    deps = ", ".join(block_dict.get("dependencies", [])) or "none"
    priority = block_dict.get("priority", 0)

    if level == "short":
        return f"[AI Summary: {tone_label} synopsis: Defines cognitive capability parameters for memory block '{name}' in category '{cat}' with priority {priority}.]"
    elif level == "detailed":
        return f"[AI Summary: {tone_label} detailed overview: Memory block '{name}' is categorized under '{cat}' and enables capabilities: [{caps}]. It has dependencies: [{deps}] and runs at priority {priority}. Fits enterprise agent context-management paradigms.]"
    elif level == "summaries":
        return f"[AI Summary: {tone_label} summary of summaries: Name: {name} | Category: {cat} | Capabilities: {caps} | Priority: {priority}. Collated from system schema blueprints.]"
    else:  # 'all' or 'global'
        return f"[AI Summary: {tone_label} global system summary: Represents structural memory layer configuration '{name}' under '{cat}'. Resolves core capabilities [{caps}] against dependencies [{deps}] with dynamic priority {priority} sorting.]"


def _custom_block_to_dict(r: CustomBlockRecord) -> dict:
    import json

    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "category": r.category,
        "capabilities": json.loads(r.capabilities)
        if isinstance(r.capabilities, str)
        else r.capabilities,
        "dependencies": json.loads(r.dependencies)
        if isinstance(r.dependencies, str)
        else r.dependencies,
        "related_blocks": json.loads(r.related_blocks)
        if isinstance(r.related_blocks, str)
        else r.related_blocks,
        "config": json.loads(r.config) if isinstance(r.config, str) else r.config,
        "enabled": r.enabled,
        "priority": r.priority,
        "usage_examples": [],
        "performance_notes": r.performance_notes,
        "configuration_guide": r.configuration_guide,
        "api_reference": {},
        "source": r.source,
        "is_overridden": True,
    }
