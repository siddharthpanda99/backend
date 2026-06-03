"""Memory Blueprints API Routes.

Provides REST endpoints for blueprint CRUD and deployment.
Blueprints are configuration snapshots from MemoryCreatorPage.
"""

import json
import logging
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.memory.blueprint_models import (
    BlueprintRecord,
    CompositionRecord,
)

router = APIRouter(tags=["memory-blueprints"])

logger = logging.getLogger(__name__)


class BlueprintCreateRequest(BaseModel):
    id: Optional[str] = None
    name: str
    description: str = ""
    entity_type: str = "memory"
    sections: str = "{}"


class BlueprintDeployRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


# ── Section → Block Category mapping ─────────────────────────────────────
# Maps MemoryCreatorPage section IDs to memory_driver BlockCategory values.
_SECTION_TO_CATEGORY = {
    "core": "core",
    "context": "context",
    "storage": "storage",
    "retrieval": "retrieval",
    "semantics": "semantic",
    "security": "security",
    "forecasting": "forecasting",
    "adaptation": "adaptation",
    "strategy": "strategy",
    "execution": "execution",
    "economics": "economics",
    "causal": "causal",
    "testing": "testing",
    "federation": "federation",
    "observability": "observability",
    "versioning": "versioning",
    "persona": "persona",
    "multimodal": "multimodal",
    "mql": "mql",
    "stores": "stores",
    "working": "working",
}


def _get_blocks_for_enabled_sections(sections: dict) -> list:
    """Resolve enabled blueprint sections to matching memory block IDs."""
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
    except Exception as e:
        logger.warning(f"Could not load memory blocks: {e}")
        return []

    enabled_ids = []
    for section_id, section_cfg in sections.items():
        if not isinstance(section_cfg, dict):
            continue
        if not section_cfg.get("enabled", True):
            continue
        cat = _SECTION_TO_CATEGORY.get(section_id)
        if not cat:
            continue
        for block in all_blocks:
            if block.category.value == cat:
                enabled_ids.append(block.id)

    return list(set(enabled_ids))


def _seed_blueprints_if_empty(session: Session) -> None:
    """Auto-seed blueprints if the database table is empty."""
    try:
        check = session.exec(
            select(BlueprintRecord).where(BlueprintRecord.id.like("bp_%"))
        ).first()
        if not check:
            logger.info("No seeded blueprints found. Running auto-seeding...")
            import sys
            import os
            routes_dir = os.path.dirname(__file__)  # Backend/app/modules/memory
            backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(routes_dir)))  # Backend
            scripts_dir = os.path.join(backend_dir, "scripts")
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)
            from seed_all_scenarios import seed
            seed()
    except Exception as e:
        logger.error(f"Failed to auto-seed blueprints: {e}", exc_info=True)


@router.get("/blueprints")
async def list_blueprints(session: Session = Depends(get_session)):
    """List all saved blueprints."""
    try:
        _seed_blueprints_if_empty(session)
        records = session.exec(
            select(BlueprintRecord).order_by(BlueprintRecord.created_at.desc())
        ).all()
        return {
            "status": "ok",
            "blueprints": [_bp_to_dict(r) for r in records],
            "count": len(records),
        }
    except Exception as e:
        logger.error(f"Failed to list blueprints: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/blueprints")
async def create_blueprint(
    request: BlueprintCreateRequest, session: Session = Depends(get_session)
):
    """Create a new blueprint from MemoryCreatorPage."""
    try:
        now = datetime.now(timezone.utc).isoformat()
        bp_id = request.id or f"bp_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        record = BlueprintRecord(
            id=bp_id,
            name=request.name,
            description=request.description,
            entity_type=request.entity_type,
            sections=request.sections,
            created_at=now,
            updated_at=now,
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return {"status": "ok", "blueprint": _bp_to_dict(record)}
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to create blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/blueprints/{blueprint_id}")
async def get_blueprint(blueprint_id: str, session: Session = Depends(get_session)):
    """Get a specific blueprint by ID."""
    try:
        record = session.get(BlueprintRecord, blueprint_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Blueprint not found: {blueprint_id}"
            )
        return {"status": "ok", "blueprint": _bp_to_dict(record)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/blueprints/{blueprint_id}")
async def delete_blueprint(blueprint_id: str, session: Session = Depends(get_session)):
    """Delete a blueprint."""
    try:
        record = session.get(BlueprintRecord, blueprint_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Blueprint not found: {blueprint_id}"
            )
        session.delete(record)
        session.commit()
        return {"status": "ok", "message": f"Blueprint {blueprint_id} deleted"}
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to delete blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Blueprint Deploy ──────────────────────────────────────────────────────


@router.post("/blueprints/{blueprint_id}/deploy")
async def deploy_blueprint(
    blueprint_id: str,
    request: BlueprintDeployRequest = BlueprintDeployRequest(),
    session: Session = Depends(get_session),
):
    """Deploy a blueprint → auto-create a composition from its enabled sections."""
    try:
        record = session.get(BlueprintRecord, blueprint_id)
        if not record:
            raise HTTPException(
                status_code=404, detail=f"Blueprint not found: {blueprint_id}"
            )

        sections = (
            json.loads(record.sections)
            if isinstance(record.sections, str)
            else record.sections
        )
        block_ids = _get_blocks_for_enabled_sections(sections)

        now = datetime.now(timezone.utc).isoformat()
        comp_id = f"comp_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        comp = CompositionRecord(
            id=comp_id,
            name=request.name or f"Deployed: {record.name}",
            description=request.description or record.description,
            block_ids=json.dumps(block_ids),
            source="blueprint",
            blueprint_id=blueprint_id,
            created_at=now,
            updated_at=now,
        )
        session.add(comp)
        session.commit()
        session.refresh(comp)

        return {
            "status": "ok",
            "composition": _comp_to_dict(comp),
            "block_count": len(block_ids),
        }
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to deploy blueprint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ── Helpers ───────────────────────────────────────────────────────────────


def _bp_to_dict(r: BlueprintRecord) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "description": r.description,
        "entity_type": r.entity_type,
        "sections": json.loads(r.sections)
        if isinstance(r.sections, str)
        else r.sections,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


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
