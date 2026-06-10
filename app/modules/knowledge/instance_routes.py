"""
Self-Learning Config Store — API Routes.

Single table with category discriminator:
  'full'        → instance bundle (name, desc, tags, variant, all configs)
  'qualityLog'  → quality log config
  'autoEvolve'  → strategy evolver config
  'scorer'      → scorer config
  'failure'     → failure analyzer config
  'reasoner'    → meta reasoner config
  'belief'      → belief reviser config
  'conflict'    → conflict resolver config
  'branching'   → evolution branching config
  'pruner'      → knowledge pruner config
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from sqlmodel import Session, delete, select

from app.modules.knowledge.models import ComponentConfigRecord
from common_lib.modules.data_storage.database.connection import get_session

logger = logging.getLogger(__name__)

CATEGORIES = frozenset(
    {
        "full",
        "qualityLog",
        "autoEvolve",
        "scorer",
        "failure",
        "reasoner",
        "belief",
        "conflict",
        "branching",
        "pruner",
    }
)

router = APIRouter()


# ── Request Schemas ─────────────────────────────────────────


class ConfigWriteRequest(BaseModel):
    config_data: dict[str, Any] = Field(
        ..., description="Config data for this category"
    )


class InstanceCreateRequest(BaseModel):
    name: str = Field(..., description="Instance name", min_length=1)
    description: str = Field("", description="Instance description")
    tags: list[str] = Field(default_factory=list)
    variant: str = Field("v1", description="UI variant (v1-v5)")
    configs: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-component configs keyed by category",
    )


class InstanceUpdateRequest(BaseModel):
    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)
    tags: Optional[list[str]] = Field(None)
    variant: Optional[str] = Field(None)
    configs: Optional[dict[str, Any]] = Field(None)


class CategoryConfigCreateRequest(BaseModel):
    category: str = Field(..., description="Config category")
    config_data: dict[str, Any] = Field(..., description="Config data")
    name: str = Field(..., description="Friendly name of this config preset", min_length=1)
    description: str = Field("", description="Description")


class CategoryConfigUpdateRequest(BaseModel):
    config_data: dict[str, Any] = Field(..., description="Config data")
    name: Optional[str] = Field(None)
    description: Optional[str] = Field(None)


# ── Helpers ────────────────────────────────────────────────────


def _gen_instance_id() -> str:
    return f"sl_{uuid4().hex[:12]}"


def _row_to_dict(row: ComponentConfigRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "instance_id": row.instance_id,
        "category": row.category,
        "config_data": row.config_data or {},
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _instance_from_rows(rows: list[ComponentConfigRecord]) -> dict[str, Any]:
    """Assemble a full instance response from its category rows."""
    full_row = next((r for r in rows if r.category == "full"), None)
    cfg: dict[str, Any] = {}
    for r in rows:
        if r.category != "full":
            cfg[r.category] = r.config_data or {}

    meta = (full_row.config_data or {}) if full_row else {}
    return {
        "id": full_row.instance_id if full_row else rows[0].instance_id,
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
        "tags": meta.get("tags", []),
        "variant": meta.get("variant", "v1"),
        "configs": cfg,
        "createdAt": (
            full_row.created_at.isoformat()
            if full_row and full_row.created_at
            else None
        ),
        "updatedAt": (
            full_row.updated_at.isoformat()
            if full_row and full_row.updated_at
            else None
        ),
    }


# ── Category-filtered Config List ──────────────────────────────
# GET /learning/configs?category=scorer  →  all scorer configs
# GET /learning/configs                  →  all configs (optionally by instance_id)


@router.get("/learning/configs")
async def list_configs(
    category: Optional[str] = Query(None, description="Filter by config category"),
    instance_id: Optional[str] = Query(None, description="Filter by instance_id"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List config rows with optional category/instance_id filters.

    UI uses this to show per-component config lists (e.g. ?category=scorer).
    """
    q = select(ComponentConfigRecord)

    if category:
        if category not in CATEGORIES:
            raise HTTPException(400, f"Invalid category: {category}")
        q = q.where(ComponentConfigRecord.category == category)
    if instance_id:
        q = q.where(ComponentConfigRecord.instance_id == instance_id)

    total_q = q
    records = session.exec(q.offset(offset).limit(limit)).all()
    total = len(session.exec(total_q).all())

    # Build a flat per-row list and merge instance name/desc
    results = []
    for r in records:
        d = _row_to_dict(r)
        if r.category != "full":
            parent = session.exec(
                select(ComponentConfigRecord).where(
                    ComponentConfigRecord.instance_id == r.instance_id,
                    ComponentConfigRecord.category == "full"
                )
            ).first()
            if parent and parent.config_data:
                d["name"] = parent.config_data.get("name", "")
                d["description"] = parent.config_data.get("description", "")
            else:
                d["name"] = f"Unnamed ({r.instance_id})"
                d["description"] = ""
        else:
            d["name"] = r.config_data.get("name", "")
            d["description"] = r.config_data.get("description", "")
        results.append(d)

    # If filtering by instance_id, also assemble as a full instance
    instance = _instance_from_rows(records) if instance_id and records else None

    return {
        "success": True,
        "data": {
            "configs": results,
            "instance": instance,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        "message": f"Found {total} configs",
    }


@router.post("/learning/configs", status_code=201)
async def create_category_config(
    request: CategoryConfigCreateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create an individual component configuration with a parent instance bundle."""
    try:
        if request.category not in CATEGORIES or request.category == "full":
            raise HTTPException(400, f"Invalid category: {request.category}")

        instance_id = _gen_instance_id()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Create 'full' parent row to hold name and description
        full_row = ComponentConfigRecord(
            instance_id=instance_id,
            category="full",
            config_data={
                "name": request.name,
                "description": request.description,
                "tags": [],
                "variant": "v1",
            },
            created_at=now,
            updated_at=now,
        )
        session.add(full_row)

        # Create the category config row
        row = ComponentConfigRecord(
            instance_id=instance_id,
            category=request.category,
            config_data=request.config_data,
            created_at=now,
            updated_at=now,
        )
        session.add(row)

        session.commit()
        session.refresh(row)

        result = _row_to_dict(row)
        result["name"] = request.name
        result["description"] = request.description

        return {
            "success": True,
            "data": result,
            "message": f"Config for '{request.category}' created",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create category config")
        raise HTTPException(
            status_code=500, detail=f"Failed to create config: {str(e)}"
        )


@router.put("/learning/configs/{config_id}")
async def update_category_config(
    config_id: int,
    request: CategoryConfigUpdateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update a specific component configuration and its parent instance details."""
    try:
        row = session.get(ComponentConfigRecord, config_id)
        if not row:
            raise HTTPException(404, f"Config record {config_id} not found")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        row.config_data = request.config_data
        row.updated_at = now
        session.add(row)

        # Find parent full row to update name/description
        parent = session.exec(
            select(ComponentConfigRecord).where(
                ComponentConfigRecord.instance_id == row.instance_id,
                ComponentConfigRecord.category == "full"
            )
        ).first()

        if parent:
            cd = parent.config_data or {}
            if request.name is not None:
                cd["name"] = request.name
            if request.description is not None:
                cd["description"] = request.description
            parent.config_data = cd
            parent.updated_at = now
            session.add(parent)

        session.commit()
        session.refresh(row)

        result = _row_to_dict(row)
        if parent:
            result["name"] = parent.config_data.get("name", "")
            result["description"] = parent.config_data.get("description", "")
        else:
            result["name"] = request.name or ""
            result["description"] = request.description or ""

        return {
            "success": True,
            "data": result,
            "message": "Config updated",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update config")
        raise HTTPException(
            status_code=500, detail=f"Failed to update config: {str(e)}"
        )


@router.delete("/learning/configs/{config_id}")
async def delete_category_config(
    config_id: int,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete a specific component config and its parent instance bundle."""
    try:
        row = session.get(ComponentConfigRecord, config_id)
        if not row:
            raise HTTPException(404, f"Config record {config_id} not found")

        instance_id = row.instance_id

        # Delete the specific config row
        session.delete(row)

        # Check if there are other sibling configs remaining for this instance
        siblings = session.exec(
            select(ComponentConfigRecord).where(
                ComponentConfigRecord.instance_id == instance_id,
                ComponentConfigRecord.category != "full"
            )
        ).all()

        # If no other sibling configs are left, clean up the 'full' row as well
        if not siblings:
            parent = session.exec(
                select(ComponentConfigRecord).where(
                    ComponentConfigRecord.instance_id == instance_id,
                    ComponentConfigRecord.category == "full"
                )
            ).first()
            if parent:
                session.delete(parent)

        session.commit()

        return {
            "success": True,
            "data": {"id": config_id},
            "message": "Config deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to delete config")
        raise HTTPException(
            status_code=500, detail=f"Failed to delete config: {str(e)}"
        )


# ── Instance CRUD ─────────────────────────────────────────
# These endpoints operate on the bundle of rows sharing an instance_id.


@router.get("/learning/instances")
async def list_instances(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """List all instance bundles (rows where category='full')."""
    q = (
        select(ComponentConfigRecord)
        .where(ComponentConfigRecord.category == "full")
        .offset(offset)
        .limit(limit)
    )
    records = session.exec(q).all()
    total_q = select(ComponentConfigRecord).where(
        ComponentConfigRecord.category == "full"
    )
    total = len(session.exec(total_q).all())

    instances = []
    for rec in records:
        cd = rec.config_data or {}
        instances.append(
            {
                "id": rec.instance_id,
                "name": cd.get("name", ""),
                "description": cd.get("description", ""),
                "tags": cd.get("tags", []),
                "variant": cd.get("variant", "v1"),
                "createdAt": rec.created_at.isoformat() if rec.created_at else None,
                "updatedAt": rec.updated_at.isoformat() if rec.updated_at else None,
            }
        )

    return {
        "success": True,
        "data": {
            "instances": instances,
            "total": total,
            "limit": limit,
            "offset": offset,
        },
        "message": f"Found {total} instances",
    }


@router.post("/learning/instances", status_code=201)
async def create_instance(
    request: InstanceCreateRequest,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Create a full instance bundle with component configs."""
    try:
        instance_id = _gen_instance_id()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # 'full' row — carries instance identity + all configs as a convenience reference
        full_row = ComponentConfigRecord(
            instance_id=instance_id,
            category="full",
            config_data={
                "name": request.name,
                "description": request.description,
                "tags": request.tags,
                "variant": request.variant,
            },
            created_at=now,
            updated_at=now,
        )
        session.add(full_row)

        # Component rows — one per configured category
        for cat, data in (request.configs or {}).items():
            if cat not in CATEGORIES or cat == "full":
                continue
            row = ComponentConfigRecord(
                instance_id=instance_id,
                category=cat,
                config_data=data,
                created_at=now,
                updated_at=now,
            )
            session.add(row)

        session.commit()

        # Fetch back all rows to assemble response
        rows = session.exec(
            select(ComponentConfigRecord).where(
                ComponentConfigRecord.instance_id == instance_id
            )
        ).all()

        return {
            "success": True,
            "data": _instance_from_rows(rows),
            "message": f"Instance '{request.name}' created",
        }

    except Exception as e:
        logger.exception("Failed to create instance")
        raise HTTPException(
            status_code=500, detail=f"Failed to create instance: {str(e)}"
        )


@router.get("/learning/instances/{instance_id}")
async def get_instance(
    instance_id: str = Path(..., description="Instance identifier"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Get a full instance bundle by instance_id."""
    rows = session.exec(
        select(ComponentConfigRecord).where(
            ComponentConfigRecord.instance_id == instance_id
        )
    ).all()

    if not rows:
        raise HTTPException(404, f"Instance {instance_id} not found")

    return {
        "success": True,
        "data": _instance_from_rows(rows),
        "message": "Instance retrieved",
    }


@router.put("/learning/instances/{instance_id}")
async def update_instance(
    request: InstanceUpdateRequest,
    instance_id: str = Path(..., description="Instance to update"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Update an instance bundle — replaces component rows."""
    existing = session.exec(
        select(ComponentConfigRecord).where(
            ComponentConfigRecord.instance_id == instance_id
        )
    ).all()

    if not existing:
        raise HTTPException(404, f"Instance {instance_id} not found")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Update 'full' row
    full_row = next((r for r in existing if r.category == "full"), None)
    if full_row:
        cd = full_row.config_data or {}
        if request.name is not None:
            cd["name"] = request.name
        if request.description is not None:
            cd["description"] = request.description
        if request.tags is not None:
            cd["tags"] = request.tags
        if request.variant is not None:
            cd["variant"] = request.variant
        full_row.config_data = cd
        full_row.updated_at = now
        session.add(full_row)

    # Replace component rows: delete existing, insert new
    if request.configs is not None:
        for r in existing:
            if r.category != "full":
                session.delete(r)

        for cat, data in request.configs.items():
            if cat not in CATEGORIES or cat == "full":
                continue
            row = ComponentConfigRecord(
                instance_id=instance_id,
                category=cat,
                config_data=data,
                created_at=now,
                updated_at=now,
            )
            session.add(row)

    session.commit()

    rows = session.exec(
        select(ComponentConfigRecord).where(
            ComponentConfigRecord.instance_id == instance_id
        )
    ).all()

    return {
        "success": True,
        "data": _instance_from_rows(rows),
        "message": f"Instance updated",
    }


@router.delete("/learning/instances/{instance_id}")
async def delete_instance(
    instance_id: str = Path(..., description="Instance to delete"),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    """Delete all config rows for an instance."""
    existing = session.exec(
        select(ComponentConfigRecord).where(
            ComponentConfigRecord.instance_id == instance_id
        )
    ).all()

    if not existing:
        raise HTTPException(404, f"Instance {instance_id} not found")

    for r in existing:
        session.delete(r)
    session.commit()

    return {
        "success": True,
        "data": {"id": instance_id},
        "message": f"Instance {instance_id} deleted",
    }
