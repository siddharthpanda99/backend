"""
Schema Builder — Environment Promotion Routes

CRUD + workflow endpoints for promoting schema changes between environments
(dev → uat → prod) with diff tracking, approval gates, and rollback.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.app_builder.schema import (
    APIResponse,
    EnvironmentPromotionRecord,
    AppIsolationConfigRecord,
)

router = APIRouter(prefix="/promotions", tags=["Environment Promotions"])


# ─── Helpers ───────────────────────────────────────────────────────

def _generate_promotion_diff(
    db: Session, app_id: str, from_env: str, to_env: str
) -> dict:
    """Generate a schema/migration/seed diff between two environments.

    In a production system this would compare actual DB schemas.
    For now, it returns a structured diff object.
    """
    return {
        "schema_diff": {
            "added_tables": [],
            "removed_tables": [],
            "modified_tables": [],
            "added_columns": [],
            "removed_columns": [],
        },
        "migration_diff": {
            "pending_up": [],
            "pending_down": [],
        },
        "seed_data_diff": {
            "added_rows": 0,
            "removed_rows": 0,
            "modified_tables": [],
        },
    }


# ─── CRUD ──────────────────────────────────────────────────────────

@router.get("", response_model=APIResponse)
async def list_promotions(
    app_id: str = Query(..., description="App ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: Session = Depends(get_session),
):
    """List promotion records for an app, optionally filtered by status."""
    query = select(EnvironmentPromotionRecord).where(
        EnvironmentPromotionRecord.app_id == app_id
    )
    if status:
        query = query.where(EnvironmentPromotionRecord.status == status)
    query = query.order_by(EnvironmentPromotionRecord.created_at.desc())
    items = db.execute(query).scalars().all()
    return APIResponse(data=[i.model_dump() for i in items])


@router.get("/{promotion_id}", response_model=APIResponse)
async def get_promotion(promotion_id: str, db: Session = Depends(get_session)):
    """Get a single promotion record by ID."""
    item = db.get(EnvironmentPromotionRecord, promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Promotion not found")
    return APIResponse(data=item.model_dump())


@router.post("", response_model=APIResponse)
async def create_promotion(
    data: dict,
    db: Session = Depends(get_session),
):
    """Create a new promotion record (generates diff automatically)."""
    app_id = data.get("app_id")
    from_env = data.get("from_env")
    to_env = data.get("to_env")

    if not all([app_id, from_env, to_env]):
        raise HTTPException(status_code=400, detail="app_id, from_env, to_env required")

    if from_env == to_env:
        raise HTTPException(status_code=400, detail="from_env and to_env must differ")

    valid_envs = {"dev", "uat", "prod"}
    if from_env not in valid_envs or to_env not in valid_envs:
        raise HTTPException(status_code=400, detail="Environments must be dev, uat, or prod")

    diff = _generate_promotion_diff(db, app_id, from_env, to_env)

    promotion = EnvironmentPromotionRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        from_env=from_env,
        to_env=to_env,
        status="pending",
        schema_diff_json=json.dumps(diff["schema_diff"]),
        migration_diff_json=json.dumps(diff["migration_diff"]),
        seed_data_diff_json=json.dumps(diff["seed_data_diff"]),
    )
    db.add(promotion)
    db.commit()
    db.refresh(promotion)
    return APIResponse(data=promotion.model_dump())


@router.delete("/{promotion_id}", response_model=APIResponse)
async def delete_promotion(promotion_id: str, db: Session = Depends(get_session)):
    """Delete a promotion record (only if pending)."""
    item = db.get(EnvironmentPromotionRecord, promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Promotion not found")
    if item.status not in ("pending", "rolled_back"):
        raise HTTPException(status_code=400, detail="Can only delete pending or rolled-back promotions")
    db.delete(item)
    db.commit()
    return APIResponse(data={"deleted": True})


# ─── Workflow Actions ─────────────────────────────────────────────

@router.post("/{promotion_id}/approve", response_model=APIResponse)
async def approve_promotion(
    promotion_id: str,
    data: dict = None,
    db: Session = Depends(get_session),
):
    """Approve a pending promotion (gate before apply)."""
    item = db.get(EnvironmentPromotionRecord, promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Promotion not found")
    if item.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot approve promotion in '{item.status}' status")

    approved_by = (data or {}).get("approved_by", "current-user")
    item.status = "approved"
    item.approved_by = approved_by
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIResponse(data=item.model_dump())


@router.post("/{promotion_id}/apply", response_model=APIResponse)
async def apply_promotion(
    promotion_id: str,
    db: Session = Depends(get_session),
):
    """Apply an approved promotion (runs migrations + seeds on target env)."""
    item = db.get(EnvironmentPromotionRecord, promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Promotion not found")
    if item.status not in ("pending", "approved"):
        raise HTTPException(status_code=400, detail=f"Cannot apply promotion in '{item.status}' status")

    # In production: run migration SQL on target env DB, apply seed data
    # For now, mark as applied
    item.status = "applied"
    item.applied_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIResponse(data=item.model_dump())


@router.post("/{promotion_id}/rollback", response_model=APIResponse)
async def rollback_promotion(
    promotion_id: str,
    db: Session = Depends(get_session),
):
    """Rollback an applied promotion (reverses migrations on target env)."""
    item = db.get(EnvironmentPromotionRecord, promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Promotion not found")
    if item.status != "applied":
        raise HTTPException(status_code=400, detail=f"Cannot rollback promotion in '{item.status}' status")

    # In production: run DOWN migrations on target env DB
    # For now, mark as rolled back
    item.status = "rolled_back"
    item.rollback_at = datetime.now(timezone.utc)
    db.add(item)
    db.commit()
    db.refresh(item)
    return APIResponse(data=item.model_dump())


@router.get("/{promotion_id}/diff", response_model=APIResponse)
async def get_promotion_diff(
    promotion_id: str,
    db: Session = Depends(get_session),
):
    """Get the full diff for a promotion record."""
    item = db.get(EnvironmentPromotionRecord, promotion_id)
    if not item:
        raise HTTPException(status_code=404, detail="Promotion not found")
    return APIResponse(data={
        "schema_diff": json.loads(item.schema_diff_json or "{}"),
        "migration_diff": json.loads(item.migration_diff_json or "{}"),
        "seed_data_diff": json.loads(item.seed_data_diff_json or "{}"),
    })


# ─── Isolation Config ─────────────────────────────────────────────

@router.get("/isolation/{app_id}", response_model=APIResponse)
async def get_isolation_config(
    app_id: str,
    db: Session = Depends(get_session),
):
    """Get isolation config for an app."""
    item = db.execute(
        select(AppIsolationConfigRecord).where(AppIsolationConfigRecord.app_id == app_id)
    ).scalar_one_or_none()
    if not item:
        return APIResponse(data={"app_id": app_id, "isolation_strategy": "separate_database"})
    return APIResponse(data=item.model_dump())


@router.post("/isolation", response_model=APIResponse)
async def save_isolation_config(
    data: dict,
    db: Session = Depends(get_session),
):
    """Create or update isolation config for an app."""
    app_id = data.get("app_id")
    strategy = data.get("isolation_strategy", "separate_database")

    if not app_id:
        raise HTTPException(status_code=400, detail="app_id required")

    existing = db.execute(
        select(AppIsolationConfigRecord).where(AppIsolationConfigRecord.app_id == app_id)
    ).scalar_one_or_none()

    if existing:
        existing.isolation_strategy = strategy
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return APIResponse(data=existing.model_dump())

    config = AppIsolationConfigRecord(
        id=str(uuid.uuid4()),
        app_id=app_id,
        isolation_strategy=strategy,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return APIResponse(data=config.model_dump())
