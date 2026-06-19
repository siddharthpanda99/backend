from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
import io

from app.modules.common.types.index import APIResponse
from common_lib.modules.image_processing.collage_sticker import (
    CollageDocument,
    render_collage,
    get_layout
)

router = APIRouter()

@router.post("/render")
async def render_collage_endpoint(doc: CollageDocument):
    """
    Renders the given CollageDocument config into a high-res composed image.
    Returns the raw composed image as a streaming PNG.
    """
    try:
        composed_img = render_collage(doc)
        
        output_buffer = io.BytesIO()
        composed_img.save(output_buffer, format="PNG")
        output_buffer.seek(0)
        
        return StreamingResponse(output_buffer, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")

@router.post("/layout", response_model=APIResponse)
async def generate_layout_endpoint(payload: Dict[str, Any]):
    """
    Computes cell slots for the chosen layout family and image count.
    """
    try:
        layout_type = payload.get("type", "grid")
        image_count = payload.get("imageCount", 4)
        seed = payload.get("seed", 42)
        
        slots = get_layout(layout_type, image_count, seed)
        return APIResponse(
            data={
                "type": layout_type,
                "imageCount": image_count,
                "slots": slots
            },
            message="Layout resolved successfully"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/cutout", response_model=APIResponse)
async def cutout_background_endpoint(file: UploadFile = File(...)):
    """
    Auto AI background removal endpoint. For simulation/dev fallback,
    returns a mock status confirming background deletion and mask preparation.
    """
    try:
        contents = await file.read()
        # In full implementation, this calls an ONNX segmenter/matting model on the server
        return APIResponse(
            data={
                "success": True,
                "message": "Background removed successfully",
                "alpha_mask_available": True
            },
            message="AI cutout computed"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
