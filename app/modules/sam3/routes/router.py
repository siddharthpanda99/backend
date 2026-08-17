"""SAM3 Routes — Thin API layer delegating to common_lib Sam3SessionService."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.common.types.index import APIResponse
from common_lib.modules.image_processing.sam3.service import get_sam3_service, check_sam3_status

logger = logging.getLogger(__name__)

router = APIRouter()


class Point(BaseModel):
    x: int
    y: int
    label: int = 1


class SegmentRequest(BaseModel):
    image_base64: str
    mode: str = "click"
    point: Optional[Point] = None
    points: Optional[List[Point]] = None
    prompt: Optional[str] = None
    threshold: float = 0.4
    max_detections: int = 20
    segment_ids: Optional[List[str]] = None
    new_name: Optional[str] = None
    group_name: Optional[str] = None
    locked: Optional[bool] = None
    num_splits: int = 2
    query: Optional[str] = None
    background_image_base64: Optional[str] = None
    replacement_image_base64: Optional[str] = None
    target_color: Optional[List[int]] = None
    scale_x: float = 1.0
    scale_y: float = 1.0
    dx: int = 0
    dy: int = 0
    angle: float = 0.0
    blur_radius: float = 5.0
    style_params: Optional[Dict[str, Any]] = None
    padding: int = 50
    target_position: Optional[tuple] = None
    reference_segment_id: Optional[str] = None
    similar_threshold: float = 0.6
    export_format: str = "png"
    dilation_pixels: int = 10
    erosion_pixels: int = 10
    refinement_iterations: int = 3
    effect: str = "blur"
    effect_params: Optional[Dict[str, Any]] = None
    prompt_text: Optional[str] = None
    negative_prompt: Optional[str] = None
    reference_image_base64: Optional[str] = None
    style: Optional[str] = None
    weather: Optional[str] = None
    time_of_day: Optional[str] = None
    season: Optional[str] = None
    lighting: Optional[str] = None
    mood: Optional[str] = None
    direction: Optional[str] = None
    shadow_direction: Optional[str] = None
    shadow_opacity: Optional[str] = None
    reflection_type: Optional[str] = None
    completion_direction: Optional[str] = None
    target_object: Optional[str] = None
    art_style: Optional[str] = None
    top_text: Optional[str] = None
    bottom_text: Optional[str] = None
    num_variations: Optional[int] = None
    prop_description: Optional[str] = None
    background_prompt: Optional[str] = None
    banner_text: Optional[str] = None
    platform: Optional[str] = None
    caption: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    scene_description: Optional[str] = None
    look_description: Optional[str] = None
    reference_face_base64: Optional[str] = None
    reference_hair_base64: Optional[str] = None
    reference_clothing_base64: Optional[str] = None
    character_reference_base64: Optional[str] = None
    target_pose: Optional[str] = None
    pose_description: Optional[str] = None
    attributes: Optional[Dict[str, str]] = None
    region_prompts: Optional[List[Dict[str, str]]] = None
    character_assignments: Optional[List[Dict[str, str]]] = None
    rearrangements: Optional[List[Dict[str, Any]]] = None
    replacements: Optional[List[Dict[str, Any]]] = None
    layout: Optional[str] = None
    steps: Optional[int] = None
    step_size: Optional[int] = None
    control_type: Optional[str] = None
    guidance_scale: Optional[float] = None
    num_inference_steps: Optional[int] = None
    strength: Optional[float] = None
    controlnet_conditioning_scale: Optional[float] = None
    low_threshold: Optional[int] = None
    high_threshold: Optional[int] = None


class SessionCreateRequest(BaseModel):
    image_base64: str


class SessionAction(BaseModel):
    session_id: str
    action: str
    params: Dict[str, Any] = {}


# Session Management


@router.post("/session/create", response_model=APIResponse)
async def create_session(req: SessionCreateRequest):
    try:
        svc = get_sam3_service()
        result = svc.create_session(req.image_base64)
        return APIResponse(
            status="success", message="Session created", data=result
        )
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/action", response_model=APIResponse)
async def session_action(req: SessionAction):
    try:
        svc = get_sam3_service()
        result = svc.execute_action(
            session_id=req.session_id,
            action=req.action,
            params=req.params,
        )
        return APIResponse(
            status="success",
            message=f"Action '{req.action}' completed",
            data={"result": result},
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Session action failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=APIResponse)
async def get_session(session_id: str):
    try:
        svc = get_sam3_service()
        state = svc.get_session_state(session_id)
        return APIResponse(status="success", message="Session retrieved", data=state)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}", response_model=APIResponse)
async def delete_session(session_id: str):
    svc = get_sam3_service()
    svc.delete_session(session_id)
    return APIResponse(status="success", message="Session deleted")


@router.get("/model-status", response_model=APIResponse)
async def model_status():
    try:
        status = check_sam3_status()
        return APIResponse(status="success", message="SAM3 status", data=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features", response_model=APIResponse)
async def list_features():
    """Return the full catalog of 150+ SAM3 segmentation features organized by category."""
    from common_lib.modules.image_processing.sam3.features_catalog import FEATURES_CATALOG

    return APIResponse(
        status="success",
        message="SAM3 features catalog",
        data=FEATURES_CATALOG,
    )
