import os
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from sqlalchemy import or_, func
from sqlmodel import select
from pydantic import BaseModel

from common_lib.modules.orchestration.infrastructure.sd.models import SdModelRecord
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.paths import IMAGE_MODELS_ROOT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sd-models", tags=["SD Models"])

class SdModelSchema(BaseModel):
    id: str
    name: str
    type: str
    fs_path: str
    trigger_words: List[str] = []
    is_active: bool = True
    metadata_json: Dict[str, Any] = {}
    created_at: Any = None
    updated_at: Any = None

    class Config:
        from_attributes = True

class SdModelUpdateRequest(BaseModel):
    name: Optional[str] = None
    trigger_words: Optional[List[str]] = None
    is_active: Optional[bool] = None
    metadata_json: Optional[Dict[str, Any]] = None

@router.get("/", response_model=List[SdModelSchema])
async def list_sd_models(
    type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    offset: int = Query(0),
    limit: int = Query(100),
):
    """List SD models from the database registry."""
    with next(get_session()) as session:
        stmt = select(SdModelRecord)
        if type:
            stmt = stmt.where(SdModelRecord.type == type)
        if search:
            stmt = stmt.where(
                or_(
                    SdModelRecord.name.ilike(f"%{search}%"),
                    SdModelRecord.id.ilike(f"%{search}%")
                )
            )
        
        stmt = stmt.offset(offset).limit(limit)
        results = session.execute(stmt).scalars().all()
        return results

@router.get("/{model_id}", response_model=SdModelSchema)
async def get_sd_model(model_id: str):
    """Get details for a specific SD model."""
    with next(get_session()) as session:
        model = session.get(SdModelRecord, model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return model

@router.patch("/{model_id}", response_model=SdModelSchema)
async def update_sd_model(model_id: str, request: SdModelUpdateRequest):
    """Update metadata for an SD model."""
    with next(get_session()) as session:
        model = session.get(SdModelRecord, model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        
        update_data = request.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(model, key, value)
            
        session.add(model)
        session.commit()
        session.refresh(model)
        return model

@router.post("/sync")
async def sync_sd_models():
    """
    Sync models from filesystem to database.
    Scans checkpoints, loras, embeddings, etc.
    """
    if not IMAGE_MODELS_ROOT.exists():
        return {"status": "error", "message": f"Path not found: {IMAGE_MODELS_ROOT}"}

    extensions = [".safetensors", ".ckpt", ".pt", ".pth"]
    
    # Mapping of directory names to SD types
    type_mapping = {
        "checkpoints": "checkpoint",
        "loras": "lora",
        "embeddings": "embedding",
        "vae": "vae",
        "controlnet": "controlnet",
        "ipadapter": "ipadapter",
        "upscale": "upscale",
        "detailing": "detailing",
        "ultralytics": "ultralytics",
        "reactor": "reactor",
        "facerestore": "facerestore",
        "facedetection": "facedetection",
        "insightface": "insightface",
        "sam": "sam",
        "grounding_dino": "grounding_dino"
    }

    count_added = 0
    count_updated = 0
    
    with next(get_session()) as session:
        # 1. Scan subdirectories
        for subdir in IMAGE_MODELS_ROOT.iterdir():
            if not subdir.is_dir():
                continue
                
            folder_name = subdir.name.lower()
            model_type = type_mapping.get(folder_name, folder_name)
            
            # Recursive scan for this folder
            for root, dirs, files in os.walk(subdir):
                for file in files:
                    file_path = os.path.join(root, file)
                    if any(file.lower().endswith(ext) for ext in extensions):
                        # Generate a unique ID: rel_path stem
                        rel_path = os.path.relpath(file_path, IMAGE_MODELS_ROOT)
                        model_id = os.path.splitext(rel_path.replace("\\", "/"))[0]
                        
                        # Category detection (e.g. sd15, sdxl)
                        category = "default"
                        parts = rel_path.replace("\\", "/").split("/")
                        if len(parts) > 2:
                            category = parts[1] # e.g. checkpoints/sd15/model.st -> sd15
                        
                        existing = session.get(SdModelRecord, model_id)
                        if existing:
                            # Update path if moved, but keep other metadata
                            existing.fs_path = str(os.path.abspath(file_path))
                            existing.type = model_type
                            existing.metadata_json = {**existing.metadata_json, "category": category}
                            count_updated += 1
                        else:
                            new_model = SdModelRecord(
                                id=model_id,
                                name=os.path.splitext(file)[0],
                                type=model_type,
                                fs_path=str(os.path.abspath(file_path)),
                                metadata_json={"category": category},
                                is_active=True
                            )
                            session.add(new_model)
                            count_added += 1
        
        session.commit()
    
    return {
        "status": "success", 
        "message": f"Sync completed: {count_added} added, {count_updated} updated"
    }

@router.delete("/{model_id}")
async def delete_sd_model_record(model_id: str):
    """Delete a model record from the database (does not delete file)."""
    with next(get_session()) as session:
        model = session.get(SdModelRecord, model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        session.delete(model)
        session.commit()
        return {"status": "success", "message": "Model record deleted"}
