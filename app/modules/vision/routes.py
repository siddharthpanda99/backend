from fastapi import APIRouter, Depends, HTTPException
from .schemas import VisionGenerateRequest, VisionGenerateResponse
from .service import vision_service
from app.modules.common.types.index import APIResponse
from app.modules.auth.dependencies.index import get_current_active_user

router = APIRouter()

@router.post("/generate-high-res", response_model=APIResponse[VisionGenerateResponse])
def generate_vision_task(
    request_in: VisionGenerateRequest,
    current_user: Any = Depends(get_current_active_user)
):
    """
    Triggers a 2-pass SD 1.5 High-Resolution generation.
    """
    result = vision_service.generate_high_res(request_in)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return APIResponse(
        data=VisionGenerateResponse(**result),
        message="Vision generation completed successfully"
    )
