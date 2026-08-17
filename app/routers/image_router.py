from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from sqlmodel import Session
from common_lib.modules.data_storage.database.connection import get_session
from common_lib.modules.image_processing.services.repositories import ModelRegistryRepository, AssetManagerRepository
from common_lib.modules.image_processing.domain.models import ModelRegistryEntry, GeneratedAsset
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/images", tags=["Image Intelligence Platform"])

class GenerateRequest(BaseModel):
    prompt: str
    workflow_id: str
    negative_prompt: str = ""
    seed: int = -1
    steps: int = 20
    cfg: float = 7.0
    resolution: List[int] = [1024, 1024]
    
@router.get("/models", response_model=List[ModelRegistryEntry])
async def list_models(limit: int = 100, offset: int = 0, session: Session = Depends(get_session)):
    repo = ModelRegistryRepository(session)
    return repo.list_all(limit=limit, offset=offset)

@router.get("/assets", response_model=List[GeneratedAsset])
async def list_assets(limit: int = 50, session: Session = Depends(get_session)):
    repo = AssetManagerRepository(session)
    return repo.list_recent(limit=limit)

@router.post("/generate")
async def generate_image(request: GenerateRequest, session: Session = Depends(get_session)):
    # Placeholder for actual generation logic
    # Will be connected to the workflow engine in phase 2
    return {"status": "queued", "workflow_id": request.workflow_id, "prompt": request.prompt}

class EditRequest(BaseModel):
    image_base64: str
    prompt: str
    
@router.post("/edit")
async def edit_image(request: EditRequest, session: Session = Depends(get_session)):
    # Placeholder for general instruction editing (e.g., using vision.restyle or MageFlow)
    return {"status": "queued", "action": "edit", "prompt": request.prompt}

class UpscaleRequest(BaseModel):
    image_base64: str
    scale_factor: float = 2.0

@router.post("/upscale")
async def upscale_image(request: UpscaleRequest, session: Session = Depends(get_session)):
    # Placeholder for upscaling via vision.upscale
    return {"status": "queued", "action": "upscale", "scale_factor": request.scale_factor}


class SegmentRequest(BaseModel):
    image_base64: str
    points: List[Dict[str, Any]] # e.g. [{"x": 100, "y": 200, "type": "positive"}]

from common_lib.modules.image_processing.services.sam_service import SAMService
from common_lib.modules.image_processing.services.inpaint_service import InpaintService

@router.post("/segment")
async def segment_image(request: SegmentRequest, session: Session = Depends(get_session)):
    sam_service = SAMService()
    mask = sam_service.generate_mask(request.image_base64, request.points)
    return {"status": "success", "mask_base64": mask}

class InpaintRequest(BaseModel):
    image_base64: str
    mask_base64: str
    prompt: str
    
@router.post("/inpaint")
async def inpaint_image(request: InpaintRequest, session: Session = Depends(get_session)):
    inpaint_service = InpaintService()
    result = inpaint_service.inpaint(request.image_base64, request.mask_base64, request.prompt)
    return {"status": "success", "image_base64": result}

class ExtractRequest(BaseModel):
    image_base64: str
    mask_base64: str

@router.post("/extract")
async def extract_layer(request: ExtractRequest, session: Session = Depends(get_session)):
    sam_service = SAMService()
    result = sam_service.extract_layer(request.image_base64, request.mask_base64)
    return {"status": "success", "image_base64": result}
