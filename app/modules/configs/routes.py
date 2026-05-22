import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from sqlalchemy import or_, func
from sqlmodel import select
from pydantic import BaseModel

from common_lib.modules.orchestration.infrastructure.sd.models import SdPresetRecord
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.vision.schemas import (
    VisionPresetSchema,
    VisionPresetCreateRequest,
    VisionPresetUpdateRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/configs", tags=["Configs"])

def record_to_schema(record: SdPresetRecord) -> VisionPresetSchema:
    """Helper to map ORM record to Pydantic schema."""
    return VisionPresetSchema(
        id=record.id,
        name=record.name,
        prompt=record.prompt,
        negative_prompt=record.negative_prompt,
        sampler=record.sampler,
        steps=record.steps,
        cfg=float(record.cfg) if record.cfg is not None else 7.0,
        width=record.width,
        height=record.height,
        seed=record.seed if isinstance(record.seed, int) else None,
        denoise=float(record.denoise) if record.denoise is not None else None,
        scheduler=record.scheduler,
        metadata=record.metadata_json or {},
        created_at=record.created_at,
        updated_at=record.updated_at
    )

@router.get("/", response_model=List[VisionPresetSchema])
async def list_configs(
    search: Optional[str] = Query(None),
    offset: int = Query(0),
    limit: int = Query(100),
):
    """
    List generation configs (presets).
    """
    with next(get_session()) as session:
        stmt = select(SdPresetRecord)
        if search:
            stmt = stmt.where(
                or_(
                    SdPresetRecord.name.ilike(f"%{search}%"),
                    SdPresetRecord.prompt.ilike(f"%{search}%")
                )
            )
        
        stmt = stmt.offset(offset).limit(limit)
        records = session.execute(stmt).scalars().all()
        return [record_to_schema(r) for r in records]

@router.get("/{config_id}", response_model=VisionPresetSchema)
async def get_config(config_id: str):
    """
    Get a single config by ID.
    """
    with next(get_session()) as session:
        record = session.get(SdPresetRecord, config_id)
        if not record:
            raise HTTPException(status_code=404, detail="Config not found")
        return record_to_schema(record)

@router.post("/", response_model=VisionPresetSchema)
async def create_config(request: VisionPresetCreateRequest):
    """
    Create a new config.
    """
    with next(get_session()) as session:
        # Check if ID already exists if provided
        if request.id:
            existing = session.get(SdPresetRecord, request.id)
            if existing:
                raise HTTPException(status_code=400, detail="Config with this ID already exists")
        
        import uuid
        new_id = request.id or f"preset_{uuid.uuid4().hex[:8]}"
        
        record = SdPresetRecord(
            id=new_id,
            name=request.name,
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            sampler=request.sampler,
            steps=request.steps,
            cfg=request.cfg,
            width=request.width,
            height=request.height,
            seed=request.seed,
            denoise=request.denoise,
            scheduler=request.scheduler,
            metadata_json=request.metadata or {}
        )
        
        session.add(record)
        session.commit()
        session.refresh(record)
        return record_to_schema(record)

class BatchConfigUpdateItem(BaseModel):
    id: str
    updates: Dict[str, Any]

class BatchConfigUpdateRequest(BaseModel):
    items: List[BatchConfigUpdateItem]

class BatchConfigUpdateResponse(BaseModel):
    status: str
    updated_count: int
    updated_ids: List[str]

@router.patch("/batch", response_model=BatchConfigUpdateResponse)
async def update_configs_batch(request: BatchConfigUpdateRequest):
    """
    Update multiple configs (presets) in a single database transaction.
    """
    updated_ids = []
    with next(get_session()) as session:
        for item in request.items:
            record = session.get(SdPresetRecord, item.id)
            if not record:
                raise HTTPException(status_code=404, detail=f"Config with ID {item.id} not found")
            
            update_data = dict(item.updates)
            if "metadata" in update_data:
                record.metadata_json = update_data.pop("metadata")
                
            for key, value in update_data.items():
                setattr(record, key, value)
                
            session.add(record)
            updated_ids.append(item.id)
            
        session.commit()
        return BatchConfigUpdateResponse(
            status="success",
            updated_count=len(updated_ids),
            updated_ids=updated_ids
        )

@router.patch("/{config_id}", response_model=VisionPresetSchema)
async def update_config(config_id: str, request: VisionPresetUpdateRequest):
    """
    Update an existing config.
    """
    with next(get_session()) as session:
        record = session.get(SdPresetRecord, config_id)
        if not record:
            raise HTTPException(status_code=404, detail="Config not found")
        
        # Update fields
        update_data = request.dict(exclude_unset=True)
        if "metadata" in update_data:
            record.metadata_json = update_data.pop("metadata")
            
        for key, value in update_data.items():
            setattr(record, key, value)
            
        session.add(record)
        session.commit()
        session.refresh(record)
        return record_to_schema(record)

@router.delete("/{config_id}")
async def delete_config(config_id: str):
    """
    Delete a config.
    """
    with next(get_session()) as session:
        record = session.get(SdPresetRecord, config_id)
        if not record:
            raise HTTPException(status_code=404, detail="Config not found")
            
        session.delete(record)
        session.commit()
        return {"status": "success", "message": f"Config {config_id} deleted"}

@router.post("/init")
async def init_configs():
    """
    Initialize configs from legacy JSON file if table is empty.
    """
    from common_lib.paths import get_repo_root
    import json
    import os
    
    config_path = get_repo_root() / "Backend" / "app" / "modules" / "vision" / "prompts_config.json"
    if not config_path.exists():
        return {"status": "skipped", "message": "Legacy config file not found"}
        
    with next(get_session()) as session:
        # Check if already has data
        count = session.execute(select(func.count()).select_from(SdPresetRecord)).scalar()
        if count > 0:
            return {"status": "skipped", "message": "Database already contains configs"}
            
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        added = 0
        for item in data:
            import uuid
            preset_id = f"preset_{uuid.uuid4().hex[:8]}"
            record = SdPresetRecord(
                id=preset_id,
                name=item.get("name", "Untitled"),
                prompt=item.get("prompt", ""),
                negative_prompt=item.get("negative_prompt", ""),
                sampler=item.get("sampler", "euler"),
                steps=item.get("steps", 25),
                cfg=item.get("cfg", 7.0),
                width=item.get("width", 512),
                height=item.get("height", 512),
                seed=item.get("seed", -1),
                denoise=item.get("denoise", 0.5),
                scheduler=item.get("scheduler", "normal"),
                metadata_json=item.get("metadata", {})
            )
            session.add(record)
            added += 1
            
        session.commit()
        return {"status": "success", "seeded": added}
