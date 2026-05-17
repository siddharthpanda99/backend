import base64
import io
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.modules.common.types.index import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────────────────────────
# Request/Response Models
# ──────────────────────────────────────────────


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
    target_position: Optional[Tuple[int, int]] = None
    reference_segment_id: Optional[str] = None
    similar_threshold: float = 0.6
    export_format: str = "png"
    dilation_pixels: int = 10
    erosion_pixels: int = 10
    refinement_iterations: int = 3
    effect: str = "blur"
    effect_params: Optional[Dict[str, Any]] = None
    # AI Generation params
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
    # ControlNet params
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


# ──────────────────────────────────────────────
# In-memory session store
# ──────────────────────────────────────────────

_sessions: Dict[str, Any] = {}


def _get_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return _sessions[session_id]


def _base64_to_tensor(b64: str):
    from common_lib.modules.image_processing.functions.sam3.utils import pil_to_tensor
    from common_lib.modules.image_processing.functions.sam3.segmentation_product import (
        _base64_to_pil,
    )

    pil = _base64_to_pil(b64)
    return pil_to_tensor([pil]).squeeze(0)


def _tensor_to_base64(tensor) -> str:
    from common_lib.modules.image_processing.functions.sam3.utils import tensor_to_pil

    pil = tensor_to_pil(tensor.unsqueeze(0))[0]
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"


def _get_model():
    import os

    os.environ["USE_PERFLIB"] = "0"
    from common_lib.modules.image_processing.functions.sam3.model_loader import (
        resolve_sam3_model,
        build_sam3_image_model,
    )

    model_info = resolve_sam3_model(model_id="sam3.1", precision="fp16")
    return build_sam3_image_model(model_info=model_info, enable_inst_interactivity=True)


# ──────────────────────────────────────────────
# Session Management
# ──────────────────────────────────────────────


@router.post("/session/create", response_model=APIResponse)
async def create_session(req: SessionCreateRequest):
    """Create a new segmentation session."""
    try:
        from common_lib.modules.image_processing.functions.sam3.segmentation_product import (
            SegmentationSession,
            _generate_id,
        )

        image_tensor = _base64_to_tensor(req.image_base64)
        session = SegmentationSession(
            image_id=_generate_id("img"),
            original_image=image_tensor,
        )
        session_id = _generate_id("sess")
        _sessions[session_id] = session
        return APIResponse(
            status="success", message="Session created", data={"session_id": session_id}
        )
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/action", response_model=APIResponse)
async def session_action(req: SessionAction):
    """Execute an action on a segmentation session."""
    try:
        session = _get_session(req.session_id)
        model = _get_model()
        action = req.action
        params = req.params

        # Import core segmentation functions
        from common_lib.modules.image_processing.functions.sam3.segmentation_product import (
            seg_click_to_segment,
            seg_auto_scene_split,
            seg_segment_to_layers,
            seg_multi_object_selection,
            seg_selection_expand,
            seg_selection_reduce,
            seg_persistent_selection,
            seg_rename_segment,
            seg_group_segments,
            seg_lock_segment,
            seg_toggle_visibility,
            seg_duplicate_segment,
            seg_merge_segments,
            seg_split_segment,
            seg_search_segments,
            seg_segment_history,
            seg_background_removal,
            seg_background_replacement,
            seg_object_removal,
            seg_object_replacement,
            seg_local_prompt_editing,
            seg_recolor_segment,
            seg_resize_segment,
            seg_reposition_segment,
            seg_rotate_segment,
            seg_blur_segment,
            seg_style_transfer_segment,
            seg_inpaint_segment,
            seg_outpaint_segment,
            seg_clone_segment,
            seg_text_to_segment,
            seg_similar_selection,
            seg_auto_suggestions,
            seg_smart_subject_detection,
            seg_classify_segments,
            seg_scene_understanding,
            seg_caption_segment,
            seg_tag_segments,
            seg_quality_score,
            seg_smart_refinement,
            seg_export_mask,
            seg_export_transparent_png,
            seg_export_svg,
            seg_export_annotation,
            seg_export_layer_project,
            seg_batch_export,
            # AI Generation (SEG-AI-01 to SEG-AI-50)
            seg_ai_replace_object,
            seg_ai_region_prompt_edit,
            seg_ai_smart_object_removal,
            seg_ai_remove_rebuild_scene,
            seg_ai_multi_object_replacement,
            seg_ai_clothing_swap,
            seg_ai_hairstyle_generator,
            seg_ai_beard_generator,
            seg_ai_face_attribute_edit,
            seg_ai_age_transformation,
            seg_ai_expression_generator,
            seg_ai_pose_refinement,
            seg_ai_background_regeneration,
            seg_ai_sky_replacement,
            seg_ai_weather_transformation,
            seg_ai_time_of_day,
            seg_ai_seasonal_transformation,
            seg_ai_scene_expansion,
            seg_ai_infinite_canvas_expansion,
            seg_ai_object_relighting,
            seg_ai_shadow_generation,
            seg_ai_reflection_generator,
            seg_ai_depth_aware_generation,
            seg_ai_perspective_correction,
            seg_ai_environment_matching,
            seg_ai_texture_continuation,
            seg_ai_smart_hole_filling,
            seg_ai_occlusion_recovery,
            seg_ai_edge_continuation,
            seg_ai_object_completion,
            seg_ai_turn_object_into,
            seg_ai_character_transformation,
            seg_ai_artistic_region_style,
            seg_ai_sticker_pack_generator,
            seg_ai_meme_generator,
            seg_ai_avatar_creator,
            seg_ai_object_variations,
            seg_ai_prop_generator,
            seg_ai_scene_recomposition,
            seg_ai_cinematic_scene,
            seg_ai_product_background,
            seg_ai_marketing_banner,
            seg_ai_social_post,
            seg_ai_thumbnail_generator,
            seg_ai_catalog_generator,
            seg_ai_poster_generator,
            seg_ai_story_scene,
            seg_ai_interior_designer,
            seg_ai_fashion_look,
            seg_ai_composite_builder,
            # ControlNet + IPAdapter (SEG-CN-01 to SEG-CN-50)
            seg_cn_region_prompting,
            seg_cn_region_style_injection,
            seg_cn_face_identity_preservation,
            seg_cn_object_identity_preservation,
            seg_cn_local_character_transfer,
            seg_cn_multi_character_scene,
            seg_cn_segment_to_pose,
            seg_cn_clothing_transfer,
            seg_cn_hairstyle_transfer,
            seg_cn_face_style_transfer,
            seg_cn_pose_guided_replacement,
            seg_cn_edge_guided_generation,
            seg_cn_depth_guided_replacement,
            seg_cn_scribble_guided_editing,
            seg_cn_shape_preserving_replacement,
            seg_cn_segment_perspective_lock,
            seg_cn_object_reposition_regenerate,
            seg_cn_region_composition_control,
            seg_cn_character_pose_animator,
            seg_cn_scene_layout_generator,
            seg_cn_character_consistency,
            seg_cn_product_consistency,
            seg_cn_brand_asset_preservation,
            seg_cn_multi_reference_fusion,
            seg_cn_regional_reference_mapping,
            seg_cn_subject_swap,
            seg_cn_object_attribute_transfer,
            seg_cn_environment_style_transfer,
            seg_cn_consistent_avatar_builder,
            seg_cn_character_sheet_generator,
            seg_cn_smart_region_regeneration,
            seg_cn_context_aware_fill,
            seg_cn_partial_object_reconstruction,
            seg_cn_occlusion_repair,
            seg_cn_object_expansion,
            seg_cn_background_reconstruction,
            seg_cn_smart_remove_replace,
            seg_cn_local_variation_generation,
            seg_cn_segment_iteration_mode,
            seg_cn_segment_undo_chain,
            seg_cn_character_into_scene,
            seg_cn_scene_to_scene_transfer,
            seg_cn_story_frame_generator,
            seg_cn_comic_panel_builder,
            seg_cn_ai_interior_designer,
            seg_cn_fashion_outfit_builder,
            seg_cn_product_visualization,
            seg_cn_thumbnail_scene_composer,
            seg_cn_cinematic_scene_generator,
            seg_cn_layer_to_generation,
        )

        def _get_seg(segment_id: str):
            return next((s for s in session.segments if s.id == segment_id), None)

        action_map = {
            # ── Core (SEG-01 to SEG-16) ──
            "click_segment": lambda: seg_click_to_segment(
                model,
                session.original_image.unsqueeze(0),
                (params.get("x", 0), params.get("y", 0)),
                params.get("label", 1),
            ),
            "auto_split": lambda: seg_auto_scene_split(
                model,
                session.original_image.unsqueeze(0),
                params.get("threshold", 0.4),
                params.get("max_detections", 20),
            ),
            "to_layers": lambda: seg_segment_to_layers(
                session.segments, session.original_image
            ),
            "multi_select": lambda: seg_multi_object_selection(
                model,
                session.original_image.unsqueeze(0),
                [(p["x"], p["y"]) for p in params.get("points", [])],
                [p.get("label", 1) for p in params.get("points", [])],
            ),
            "expand": lambda: seg_selection_expand(
                session,
                model,
                session.original_image.unsqueeze(0),
                params.get("dilation_pixels", 10),
            ),
            "reduce": lambda: seg_selection_reduce(
                session, params.get("erosion_pixels", 10)
            ),
            "save_selection": lambda: seg_persistent_selection(
                session, params.get("segment_ids", [])
            ),
            "rename": lambda: seg_rename_segment(
                session, params["segment_id"], params["new_name"]
            ),
            "group": lambda: seg_group_segments(
                session, params.get("segment_ids", []), params.get("group_name", "")
            ),
            "lock": lambda: seg_lock_segment(
                session, params["segment_id"], params.get("locked", True)
            ),
            "toggle_visibility": lambda: seg_toggle_visibility(
                session, params["segment_id"]
            ),
            "duplicate": lambda: seg_duplicate_segment(session, params["segment_id"]),
            "merge": lambda: seg_merge_segments(
                session, params.get("segment_ids", []), params.get("new_name")
            ),
            "split": lambda: seg_split_segment(
                session, params["segment_id"], params.get("num_splits", 2)
            ),
            "search": lambda: seg_search_segments(session, params.get("query", "")),
            "history": lambda: seg_segment_history(session),
            # ── Editing (SEG-17 to SEG-30) ──
            "bg_removal": lambda: seg_background_removal(
                model, session.original_image.unsqueeze(0)
            ),
            "bg_replacement": lambda: seg_background_replacement(
                model,
                session.original_image.unsqueeze(0),
                _base64_to_tensor(params["background_image_base64"]).unsqueeze(0),
            ),
            "object_removal": lambda: seg_object_removal(
                session, session.original_image, params.get("segment_ids", [])
            ),
            "object_replacement": lambda: seg_object_replacement(
                session,
                session.original_image,
                params.get("segment_ids", []),
                _base64_to_tensor(params["replacement_image_base64"]).unsqueeze(0),
            ),
            "recolor": lambda: seg_recolor_segment(
                session,
                session.original_image,
                params["segment_id"],
                tuple(params.get("target_color", [0, 0, 0])),
            ),
            "resize": lambda: seg_resize_segment(
                session,
                params["segment_id"],
                params.get("scale_x", 1.0),
                params.get("scale_y", 1.0),
            ),
            "reposition": lambda: seg_reposition_segment(
                session, params["segment_id"], params.get("dx", 0), params.get("dy", 0)
            ),
            "rotate": lambda: seg_rotate_segment(
                session, params["segment_id"], params.get("angle", 0)
            ),
            "blur": lambda: seg_blur_segment(
                session,
                session.original_image,
                params["segment_id"],
                params.get("blur_radius", 5.0),
            ),
            "style_transfer": lambda: seg_style_transfer_segment(
                session.original_image,
                params["segment_id"],
                session,
                params.get("style_params", {}),
            ),
            "inpaint": lambda: seg_inpaint_segment(
                session,
                session.original_image,
                params.get("segment_ids", []),
                params.get("prompt", ""),
            ),
            "outpaint": lambda: seg_outpaint_segment(
                session,
                session.original_image,
                params["segment_id"],
                params.get("padding", 50),
            ),
            "clone": lambda: seg_clone_segment(
                session,
                session.original_image,
                params["segment_id"],
                tuple(params.get("target_position", (0, 0))),
            ),
            # ── AI (SEG-31 to SEG-40) ──
            "text_segment": lambda: seg_text_to_segment(
                model,
                session.original_image.unsqueeze(0),
                params.get("prompt", ""),
                params.get("threshold", 0.4),
            ),
            "similar": lambda: seg_similar_selection(
                model,
                session.original_image.unsqueeze(0),
                _get_seg(params["reference_segment_id"]),
                params.get("similar_threshold", 0.6),
            ),
            "suggestions": lambda: seg_auto_suggestions(
                model, session.original_image.unsqueeze(0)
            ),
            "detect_subject": lambda: seg_smart_subject_detection(
                model, session.original_image.unsqueeze(0)
            ),
            "classify": lambda: seg_classify_segments(
                model, session.original_image.unsqueeze(0)
            ),
            "scene_understanding": lambda: seg_scene_understanding(
                model, session.original_image.unsqueeze(0)
            ),
            "caption": lambda: seg_caption_segment(_get_seg(params["segment_id"])),
            "tag": lambda: seg_tag_segments(session.segments),
            "quality_score": lambda: seg_quality_score(_get_seg(params["segment_id"])),
            "refine": lambda: seg_smart_refinement(
                model,
                session.original_image.unsqueeze(0),
                _get_seg(params["segment_id"]),
                params.get("refinement_iterations", 3),
            ),
            # ── Export (SEG-41 to SEG-46) ──
            "export_mask": lambda: seg_export_mask(
                _get_seg(params["segment_id"]), params.get("export_format", "png")
            ),
            "export_transparent": lambda: seg_export_transparent_png(
                _get_seg(params["segment_id"]), session.original_image
            ),
            "export_svg": lambda: seg_export_svg(_get_seg(params["segment_id"])),
            "export_annotation": lambda: seg_export_annotation(
                session.segments, params.get("export_format", "coco")
            ),
            "export_project": lambda: seg_export_layer_project(
                session.segments, session.original_image
            ),
            "batch_export": lambda: seg_batch_export(
                session.segments, session.original_image
            ),
            # ── AI Generation (SEG-AI-01 to SEG-AI-50) ──
            "ai_replace_object": lambda: seg_ai_replace_object(
                session,
                session.original_image,
                params.get("segment_ids", []),
                params.get("prompt", ""),
                params.get("negative_prompt", ""),
            ),
            "ai_region_prompt_edit": lambda: seg_ai_region_prompt_edit(
                session,
                session.original_image,
                params["segment_id"],
                params.get("prompt", ""),
                params.get("strength", 0.75),
            ),
            "ai_smart_object_removal": lambda: seg_ai_smart_object_removal(
                session, session.original_image, params.get("segment_ids", [])
            ),
            "ai_remove_rebuild_scene": lambda: seg_ai_remove_rebuild_scene(
                session,
                session.original_image,
                params.get("segment_ids", []),
                params.get("context_prompt", ""),
            ),
            "ai_multi_object_replacement": lambda: seg_ai_multi_object_replacement(
                session, session.original_image, params.get("replacements", [])
            ),
            "ai_clothing_swap": lambda: seg_ai_clothing_swap(
                session,
                session.original_image,
                params["clothing_segment_id"],
                params["style_prompt"],
            ),
            "ai_hairstyle_generator": lambda: seg_ai_hairstyle_generator(
                session,
                session.original_image,
                params["hair_segment_id"],
                params["style"],
            ),
            "ai_beard_generator": lambda: seg_ai_beard_generator(
                session,
                session.original_image,
                params["face_segment_id"],
                params["beard_style"],
            ),
            "ai_face_attribute_edit": lambda: seg_ai_face_attribute_edit(
                session,
                session.original_image,
                params["face_segment_id"],
                params.get("attributes", {}),
            ),
            "ai_age_transformation": lambda: seg_ai_age_transformation(
                session,
                session.original_image,
                params["face_segment_id"],
                params["target_age"],
            ),
            "ai_expression_generator": lambda: seg_ai_expression_generator(
                session,
                session.original_image,
                params["face_segment_id"],
                params["expression"],
            ),
            "ai_pose_refinement": lambda: seg_ai_pose_refinement(
                session,
                session.original_image,
                params["body_segment_id"],
                params["pose_description"],
            ),
            "ai_background_regeneration": lambda: seg_ai_background_regeneration(
                session,
                session.original_image,
                params["bg_segment_id"],
                params["prompt"],
            ),
            "ai_sky_replacement": lambda: seg_ai_sky_replacement(
                session,
                session.original_image,
                params["sky_segment_id"],
                params["sky_type"],
            ),
            "ai_weather_transformation": lambda: seg_ai_weather_transformation(
                session, session.original_image, params["weather"]
            ),
            "ai_time_of_day": lambda: seg_ai_time_of_day(
                session, session.original_image, params["time"]
            ),
            "ai_seasonal_transformation": lambda: seg_ai_seasonal_transformation(
                session, session.original_image, params["season"]
            ),
            "ai_scene_expansion": lambda: seg_ai_scene_expansion(
                session,
                session.original_image,
                params.get("padding", 100),
                params.get("direction", "all"),
            ),
            "ai_infinite_canvas_expansion": lambda: seg_ai_infinite_canvas_expansion(
                session,
                session.original_image,
                params.get("steps", 3),
                params.get("step_size", 100),
            ),
            "ai_object_relighting": lambda: seg_ai_object_relighting(
                session,
                session.original_image,
                params["segment_id"],
                params["lighting"],
            ),
            "ai_shadow_generation": lambda: seg_ai_shadow_generation(
                session,
                session.original_image,
                params["segment_id"],
                params.get("shadow_direction", "bottom-right"),
                params.get("shadow_opacity", 0.3),
            ),
            "ai_reflection_generator": lambda: seg_ai_reflection_generator(
                session,
                session.original_image,
                params["segment_id"],
                params.get("reflection_type", "water"),
            ),
            "ai_depth_aware_generation": lambda: seg_ai_depth_aware_generation(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "ai_perspective_correction": lambda: seg_ai_perspective_correction(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "ai_environment_matching": lambda: seg_ai_environment_matching(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "ai_texture_continuation": lambda: seg_ai_texture_continuation(
                session, session.original_image, params["segment_id"]
            ),
            "ai_smart_hole_filling": lambda: seg_ai_smart_hole_filling(
                session, session.original_image, params["segment_id"]
            ),
            "ai_occlusion_recovery": lambda: seg_ai_occlusion_recovery(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "ai_edge_continuation": lambda: seg_ai_edge_continuation(
                session, session.original_image, params["segment_id"]
            ),
            "ai_object_completion": lambda: seg_ai_object_completion(
                session,
                session.original_image,
                params["segment_id"],
                params.get("completion_direction", "right"),
            ),
            "ai_turn_object_into": lambda: seg_ai_turn_object_into(
                session,
                session.original_image,
                params["segment_id"],
                params["target_object"],
            ),
            "ai_character_transformation": lambda: seg_ai_character_transformation(
                session,
                session.original_image,
                params["face_segment_id"],
                params["style"],
            ),
            "ai_artistic_region_style": lambda: seg_ai_artistic_region_style(
                session,
                session.original_image,
                params["segment_id"],
                params["art_style"],
            ),
            "ai_sticker_pack_generator": lambda: seg_ai_sticker_pack_generator(
                session, session.original_image, params.get("segment_ids", [])
            ),
            "ai_meme_generator": lambda: seg_ai_meme_generator(
                session,
                session.original_image,
                params["segment_id"],
                params.get("top_text", ""),
                params.get("bottom_text", ""),
            ),
            "ai_avatar_creator": lambda: seg_ai_avatar_creator(
                session,
                session.original_image,
                params["face_segment_id"],
                params.get("style", "cartoon"),
            ),
            "ai_object_variations": lambda: seg_ai_object_variations(
                session,
                session.original_image,
                params["segment_id"],
                params["prompt"],
                params.get("num_variations", 4),
            ),
            "ai_prop_generator": lambda: seg_ai_prop_generator(
                session,
                session.original_image,
                params["segment_id"],
                params["prop_description"],
            ),
            "ai_scene_recomposition": lambda: seg_ai_scene_recomposition(
                session, session.original_image, params.get("rearrangements", [])
            ),
            "ai_cinematic_scene": lambda: seg_ai_cinematic_scene(
                session, session.original_image, params.get("mood", "dramatic")
            ),
            "ai_product_background": lambda: seg_ai_product_background(
                session,
                session.original_image,
                params["product_segment_id"],
                params["background_prompt"],
            ),
            "ai_marketing_banner": lambda: seg_ai_marketing_banner(
                session,
                session.original_image,
                params["product_segment_id"],
                params["banner_text"],
                params.get("style", "modern"),
            ),
            "ai_social_post": lambda: seg_ai_social_post(
                session,
                session.original_image,
                params.get("segment_ids", []),
                params.get("platform", "instagram"),
                params.get("caption", ""),
            ),
            "ai_thumbnail_generator": lambda: seg_ai_thumbnail_generator(
                session,
                session.original_image,
                params["subject_segment_id"],
                params["title"],
                params.get("style", "youtube"),
            ),
            "ai_catalog_generator": lambda: seg_ai_catalog_generator(
                session,
                params.get("images", []),
                params.get("segment_ids", []),
                params.get("layout", "grid"),
            ),
            "ai_poster_generator": lambda: seg_ai_poster_generator(
                session,
                session.original_image,
                params["segment_id"],
                params["title"],
                params.get("subtitle", ""),
            ),
            "ai_story_scene": lambda: seg_ai_story_scene(
                session,
                session.original_image,
                params["character_segment_id"],
                params["scene_description"],
            ),
            "ai_interior_designer": lambda: seg_ai_interior_designer(
                session,
                session.original_image,
                params.get("furniture_segment_ids", []),
                params["style"],
            ),
            "ai_fashion_look": lambda: seg_ai_fashion_look(
                session,
                session.original_image,
                params.get("clothing_segment_ids", []),
                params["look_description"],
            ),
            "ai_composite_builder": lambda: seg_ai_composite_builder(
                session,
                session.original_image,
                params.get("source_segments", []),
                params.get("positions", []),
            ),
            # ── ControlNet + IPAdapter (SEG-CN-01 to SEG-CN-50) ──
            "cn_region_prompting": lambda: seg_cn_region_prompting(
                session, session.original_image, params.get("region_prompts", [])
            ),
            "cn_region_style_injection": lambda: seg_cn_region_style_injection(
                session,
                session.original_image,
                params["segment_id"],
                params["reference_image_base64"],
            ),
            "cn_face_identity_preservation": lambda: seg_cn_face_identity_preservation(
                session,
                session.original_image,
                params["face_segment_id"],
                params["reference_face_base64"],
                params.get("attributes", {}),
            ),
            "cn_object_identity_preservation": lambda: seg_cn_object_identity_preservation(
                session,
                session.original_image,
                params["segment_id"],
                params["reference_image_base64"],
                params["prompt"],
            ),
            "cn_local_character_transfer": lambda: seg_cn_local_character_transfer(
                session,
                session.original_image,
                params["segment_id"],
                params["character_reference_base64"],
            ),
            "cn_multi_character_scene": lambda: seg_cn_multi_character_scene(
                session, session.original_image, params.get("character_assignments", [])
            ),
            "cn_segment_to_pose": lambda: seg_cn_segment_to_pose(
                session,
                session.original_image,
                params["person_segment_id"],
                params["target_pose"],
            ),
            "cn_clothing_transfer": lambda: seg_cn_clothing_transfer(
                session,
                session.original_image,
                params["clothing_segment_id"],
                params["reference_clothing_base64"],
            ),
            "cn_hairstyle_transfer": lambda: seg_cn_hairstyle_transfer(
                session,
                session.original_image,
                params["hair_segment_id"],
                params["reference_hair_base64"],
            ),
            "cn_face_style_transfer": lambda: seg_cn_face_style_transfer(
                session,
                session.original_image,
                params["face_segment_id"],
                params["reference_face_base64"],
            ),
            "cn_pose_guided_replacement": lambda: seg_cn_pose_guided_replacement(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "cn_edge_guided_generation": lambda: seg_cn_edge_guided_generation(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "cn_depth_guided_replacement": lambda: seg_cn_depth_guided_replacement(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "cn_scribble_guided_editing": lambda: seg_cn_scribble_guided_editing(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "cn_shape_preserving_replacement": lambda: seg_cn_shape_preserving_replacement(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "cn_segment_perspective_lock": lambda: seg_cn_segment_perspective_lock(
                session, session.original_image, params["segment_id"], params["prompt"]
            ),
            "cn_object_reposition_regenerate": lambda: seg_cn_object_reposition_regenerate(
                session,
                session.original_image,
                params["segment_id"],
                params.get("dx", 0),
                params.get("dy", 0),
                params.get("prompt", ""),
            ),
            "cn_region_composition_control": lambda: seg_cn_region_composition_control(
                session, session.original_image, params.get("region_prompts", [])
            ),
            "cn_character_pose_animator": lambda: seg_cn_character_pose_animator(
                session,
                session.original_image,
                params["person_segment_id"],
                params.get("pose_sequence", []),
            ),
            "cn_scene_layout_generator": lambda: seg_cn_scene_layout_generator(
                session, session.original_image, params.get("layout_description", "")
            ),
            "cn_character_consistency": lambda: seg_cn_character_consistency(
                session,
                session.original_image,
                params["segment_id"],
                params["reference_image_base64"],
                params["prompt"],
            ),
            "cn_product_consistency": lambda: seg_cn_product_consistency(
                session,
                session.original_image,
                params["product_segment_id"],
                params["reference_image_base64"],
                params["prompt"],
            ),
            "cn_brand_asset_preservation": lambda: seg_cn_brand_asset_preservation(
                session,
                session.original_image,
                params["segment_id"],
                params["reference_image_base64"],
                params["prompt"],
            ),
            "cn_multi_reference_fusion": lambda: seg_cn_multi_reference_fusion(
                session,
                session.original_image,
                params.get("references", []),
                params["prompt"],
            ),
            "cn_regional_reference_mapping": lambda: seg_cn_regional_reference_mapping(
                session, session.original_image, params.get("mappings", [])
            ),
            "cn_subject_swap": lambda: seg_cn_subject_swap(
                session,
                session.original_image,
                params["subject_segment_id"],
                params["reference_image_base64"],
            ),
            "cn_object_attribute_transfer": lambda: seg_cn_object_attribute_transfer(
                session,
                session.original_image,
                params["source_segment_id"],
                params["target_segment_id"],
            ),
            "cn_environment_style_transfer": lambda: seg_cn_environment_style_transfer(
                session, session.original_image, params["reference_image_base64"]
            ),
            "cn_consistent_avatar_builder": lambda: seg_cn_consistent_avatar_builder(
                session,
                session.original_image,
                params["face_segment_id"],
                params["reference_image_base64"],
                params.get("style", "cartoon"),
            ),
            "cn_character_sheet_generator": lambda: seg_cn_character_sheet_generator(
                session,
                session.original_image,
                params["character_segment_id"],
                params["reference_image_base64"],
                params.get("num_poses", 6),
            ),
            "cn_smart_region_regeneration": lambda: seg_cn_smart_region_regeneration(
                session,
                session.original_image,
                params["segment_id"],
                params.get("prompt", ""),
            ),
            "cn_context_aware_fill": lambda: seg_cn_context_aware_fill(
                session, session.original_image, params["segment_id"]
            ),
            "cn_partial_object_reconstruction": lambda: seg_cn_partial_object_reconstruction(
                session,
                session.original_image,
                params["segment_id"],
                params.get("prompt", ""),
            ),
            "cn_occlusion_repair": lambda: seg_cn_occlusion_repair(
                session, session.original_image, params["segment_id"]
            ),
            "cn_object_expansion": lambda: seg_cn_object_expansion(
                session,
                session.original_image,
                params["segment_id"],
                params.get("expand_direction", "all"),
                params.get("expand_amount", 20),
            ),
            "cn_background_reconstruction": lambda: seg_cn_background_reconstruction(
                session, session.original_image, params["segment_id"]
            ),
            "cn_smart_remove_replace": lambda: seg_cn_smart_remove_replace(
                session,
                session.original_image,
                params["segment_id"],
                params.get("prompt", ""),
            ),
            "cn_local_variation_generation": lambda: seg_cn_local_variation_generation(
                session,
                session.original_image,
                params["segment_id"],
                params.get("prompt", ""),
                params.get("num_variations", 4),
            ),
            "cn_segment_iteration_mode": lambda: seg_cn_segment_iteration_mode(
                session,
                session.original_image,
                params["segment_id"],
                params.get("prompt", ""),
                params.get("num_iterations", 4),
            ),
            "cn_segment_undo_chain": lambda: seg_cn_segment_undo_chain(
                session, session.original_image, params["segment_id"]
            ),
            "cn_character_into_scene": lambda: seg_cn_character_into_scene(
                session,
                session.original_image,
                params["target_segment_id"],
                params["character_reference_base64"],
            ),
            "cn_scene_to_scene_transfer": lambda: seg_cn_scene_to_scene_transfer(
                session, session.original_image, params["reference_image_base64"]
            ),
            "cn_story_frame_generator": lambda: seg_cn_story_frame_generator(
                session,
                session.original_image,
                params.get("story_description", ""),
                params.get("num_frames", 4),
            ),
            "cn_comic_panel_builder": lambda: seg_cn_comic_panel_builder(
                session,
                session.original_image,
                params.get("character_segment_ids", []),
                params.get("panel_layout", "3x2"),
            ),
            "cn_ai_interior_designer": lambda: seg_cn_ai_interior_designer(
                session,
                session.original_image,
                params.get("furniture_segment_ids", []),
                params["style"],
            ),
            "cn_fashion_outfit_builder": lambda: seg_cn_fashion_outfit_builder(
                session,
                session.original_image,
                params["person_segment_id"],
                params.get("clothing_references", []),
            ),
            "cn_product_visualization_generator": lambda: seg_cn_product_visualization(
                session,
                session.original_image,
                params["product_segment_id"],
                params["context_prompt"],
            ),
            "cn_thumbnail_scene_composer": lambda: seg_cn_thumbnail_scene_composer(
                session,
                session.original_image,
                params["subject_segment_id"],
                params["title"],
                params.get("style", "youtube"),
            ),
            "cn_cinematic_scene_generator": lambda: seg_cn_cinematic_scene_generator(
                session,
                session.original_image,
                params.get("mood", "dramatic"),
                params.get("style", "film"),
            ),
            "cn_layer_to_generation_workflow": lambda: seg_cn_layer_to_generation(
                session, session.original_image, params.get("layer_prompts", [])
            ),
        }

        handler = action_map.get(action)
        if handler is None:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

        result = handler()

        # Convert tensor results to base64
        import torch

        if isinstance(result, torch.Tensor):
            result = _tensor_to_base64(result)
        elif isinstance(result, list):
            if len(result) > 0 and isinstance(result[0], torch.Tensor):
                result = [_tensor_to_base64(t) for t in result]
            elif len(result) > 0 and hasattr(result[0], "to_dict"):
                result = [s.to_dict() for s in result]
        elif hasattr(result, "to_dict"):
            result = result.to_dict()

        return APIResponse(
            status="success",
            message=f"Action '{action}' completed",
            data={"result": result},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Session action failed: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=APIResponse)
async def get_session(session_id: str):
    """Get session state."""
    try:
        session = _get_session(session_id)
        return APIResponse(
            status="success",
            message="Session retrieved",
            data={
                "session_id": session_id,
                "image_id": session.image_id,
                "segments": [s.to_dict() for s in session.segments],
                "active_selection": session.active_selection,
                "history_count": len(session.history),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/session/{session_id}", response_model=APIResponse)
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id in _sessions:
        del _sessions[session_id]
    return APIResponse(status="success", message="Session deleted")


@router.get("/model-status", response_model=APIResponse)
async def model_status():
    """Check SAM3 model availability."""
    try:
        import os

        os.environ["USE_PERFLIB"] = "0"
        from common_lib.modules.image_processing.functions.sam3.model_loader import (
            check_sam3_ready,
        )

        status = check_sam3_ready(model_id="sam3.1")
        return APIResponse(status="success", message="SAM3 status", data=status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/features/catalog", response_model=APIResponse)
async def features_catalog():
    """Return the full catalog of 150 SAM3 features organized by category."""
    catalog = {
        "core": {
            "label": "Core Segmentation",
            "features": [
                {"id": "click_segment", "name": "Click-to-Segment", "seg": "SEG-01"},
                {"id": "auto_split", "name": "Auto Scene Split", "seg": "SEG-02"},
                {"id": "to_layers", "name": "Segment-to-Layers", "seg": "SEG-03"},
                {
                    "id": "multi_select",
                    "name": "Multi-Object Selection",
                    "seg": "SEG-04",
                },
                {"id": "expand", "name": "Smart Selection Expansion", "seg": "SEG-05"},
                {"id": "reduce", "name": "Smart Selection Reduction", "seg": "SEG-06"},
                {
                    "id": "save_selection",
                    "name": "Persistent Selection",
                    "seg": "SEG-07",
                },
                {"id": "rename", "name": "Segment Rename", "seg": "SEG-08"},
                {"id": "group", "name": "Segment Grouping", "seg": "SEG-09"},
                {"id": "lock", "name": "Segment Lock", "seg": "SEG-10"},
                {
                    "id": "toggle_visibility",
                    "name": "Visibility Toggle",
                    "seg": "SEG-11",
                },
                {"id": "duplicate", "name": "Segment Duplicate", "seg": "SEG-12"},
                {"id": "merge", "name": "Segment Merge", "seg": "SEG-13"},
                {"id": "split", "name": "Segment Split", "seg": "SEG-14"},
                {"id": "search", "name": "Segment Search", "seg": "SEG-15"},
                {"id": "history", "name": "Segment History", "seg": "SEG-16"},
            ],
        },
        "editing": {
            "label": "Editing",
            "features": [
                {"id": "bg_removal", "name": "Background Removal", "seg": "SEG-17"},
                {
                    "id": "bg_replacement",
                    "name": "Background Replacement",
                    "seg": "SEG-18",
                },
                {"id": "object_removal", "name": "Object Removal", "seg": "SEG-19"},
                {
                    "id": "object_replacement",
                    "name": "Object Replacement",
                    "seg": "SEG-20",
                },
                {"id": "recolor", "name": "Segment Recolor", "seg": "SEG-22"},
                {"id": "resize", "name": "Segment Resize", "seg": "SEG-23"},
                {"id": "reposition", "name": "Segment Reposition", "seg": "SEG-24"},
                {"id": "rotate", "name": "Segment Rotation", "seg": "SEG-25"},
                {"id": "blur", "name": "Segment Blur", "seg": "SEG-26"},
                {
                    "id": "style_transfer",
                    "name": "Segment Style Transfer",
                    "seg": "SEG-27",
                },
                {"id": "inpaint", "name": "Segment Inpainting", "seg": "SEG-28"},
                {"id": "outpaint", "name": "Segment Outpainting", "seg": "SEG-29"},
                {"id": "clone", "name": "Segment Clone", "seg": "SEG-30"},
            ],
        },
        "ai": {
            "label": "AI Features",
            "features": [
                {"id": "text_segment", "name": "Text-to-Segment", "seg": "SEG-31"},
                {"id": "similar", "name": "Similar Object Selection", "seg": "SEG-32"},
                {"id": "suggestions", "name": "Auto Mask Suggestions", "seg": "SEG-33"},
                {
                    "id": "detect_subject",
                    "name": "Smart Subject Detection",
                    "seg": "SEG-34",
                },
                {"id": "classify", "name": "Segment Classification", "seg": "SEG-35"},
                {
                    "id": "scene_understanding",
                    "name": "AI Scene Understanding",
                    "seg": "SEG-36",
                },
                {"id": "caption", "name": "Segment Captioning", "seg": "SEG-37"},
                {"id": "tag", "name": "Segment Tagging", "seg": "SEG-38"},
                {
                    "id": "quality_score",
                    "name": "Segment Quality Scoring",
                    "seg": "SEG-39",
                },
                {"id": "refine", "name": "Smart Refinement", "seg": "SEG-40"},
            ],
        },
        "export": {
            "label": "Export",
            "features": [
                {"id": "export_mask", "name": "Export Mask", "seg": "SEG-41"},
                {
                    "id": "export_transparent",
                    "name": "Export Transparent PNG",
                    "seg": "SEG-42",
                },
                {"id": "export_svg", "name": "Export SVG", "seg": "SEG-43"},
                {
                    "id": "export_annotation",
                    "name": "Export Annotation",
                    "seg": "SEG-44",
                },
                {
                    "id": "export_project",
                    "name": "Export Layer Project",
                    "seg": "SEG-45",
                },
                {
                    "id": "batch_export",
                    "name": "Batch Export Segments",
                    "seg": "SEG-46",
                },
            ],
        },
        "ai_generation": {
            "label": "AI Generation",
            "features": [
                {
                    "id": "ai_replace_object",
                    "name": "Replace Selected Object",
                    "seg": "SEG-AI-01",
                },
                {
                    "id": "ai_region_prompt_edit",
                    "name": "Region Prompt Editing",
                    "seg": "SEG-AI-02",
                },
                {
                    "id": "ai_smart_object_removal",
                    "name": "Smart Object Removal",
                    "seg": "SEG-AI-03",
                },
                {
                    "id": "ai_remove_rebuild_scene",
                    "name": "Remove and Rebuild Scene",
                    "seg": "SEG-AI-04",
                },
                {
                    "id": "ai_multi_object_replacement",
                    "name": "Multi-Object Replacement",
                    "seg": "SEG-AI-05",
                },
                {
                    "id": "ai_clothing_swap",
                    "name": "AI Clothing Swap",
                    "seg": "SEG-AI-06",
                },
                {
                    "id": "ai_hairstyle_generator",
                    "name": "Hairstyle Generator",
                    "seg": "SEG-AI-07",
                },
                {
                    "id": "ai_beard_generator",
                    "name": "Beard Generator",
                    "seg": "SEG-AI-08",
                },
                {
                    "id": "ai_face_attribute_edit",
                    "name": "Face Attribute Editing",
                    "seg": "SEG-AI-09",
                },
                {
                    "id": "ai_age_transformation",
                    "name": "Age Transformation",
                    "seg": "SEG-AI-10",
                },
                {
                    "id": "ai_expression_generator",
                    "name": "Expression Generator",
                    "seg": "SEG-AI-11",
                },
                {
                    "id": "ai_pose_refinement",
                    "name": "Pose Refinement",
                    "seg": "SEG-AI-12",
                },
                {
                    "id": "ai_background_regeneration",
                    "name": "Background Regeneration",
                    "seg": "SEG-AI-13",
                },
                {
                    "id": "ai_sky_replacement",
                    "name": "Sky Replacement",
                    "seg": "SEG-AI-14",
                },
                {
                    "id": "ai_weather_transformation",
                    "name": "Weather Transformation",
                    "seg": "SEG-AI-15",
                },
                {
                    "id": "ai_time_of_day",
                    "name": "Time-of-Day Generator",
                    "seg": "SEG-AI-16",
                },
                {
                    "id": "ai_seasonal_transformation",
                    "name": "Seasonal Transformation",
                    "seg": "SEG-AI-17",
                },
                {
                    "id": "ai_scene_expansion",
                    "name": "Scene Expansion",
                    "seg": "SEG-AI-18",
                },
                {
                    "id": "ai_infinite_canvas_expansion",
                    "name": "Infinite Canvas Expansion",
                    "seg": "SEG-AI-19",
                },
                {
                    "id": "ai_object_relighting",
                    "name": "Object Relighting",
                    "seg": "SEG-AI-20",
                },
                {
                    "id": "ai_shadow_generation",
                    "name": "Shadow Generation",
                    "seg": "SEG-AI-21",
                },
                {
                    "id": "ai_reflection_generator",
                    "name": "Reflection Generator",
                    "seg": "SEG-AI-22",
                },
                {
                    "id": "ai_depth_aware_generation",
                    "name": "Depth-Aware Generation",
                    "seg": "SEG-AI-23",
                },
                {
                    "id": "ai_perspective_correction",
                    "name": "Perspective Correction",
                    "seg": "SEG-AI-24",
                },
                {
                    "id": "ai_environment_matching",
                    "name": "Environment Matching",
                    "seg": "SEG-AI-25",
                },
                {
                    "id": "ai_texture_continuation",
                    "name": "Texture Continuation",
                    "seg": "SEG-AI-26",
                },
                {
                    "id": "ai_smart_hole_filling",
                    "name": "Smart Hole Filling",
                    "seg": "SEG-AI-27",
                },
                {
                    "id": "ai_occlusion_recovery",
                    "name": "Occlusion Recovery",
                    "seg": "SEG-AI-28",
                },
                {
                    "id": "ai_edge_continuation",
                    "name": "Edge Continuation",
                    "seg": "SEG-AI-29",
                },
                {
                    "id": "ai_object_completion",
                    "name": "Object Completion",
                    "seg": "SEG-AI-30",
                },
                {
                    "id": "ai_turn_object_into",
                    "name": "Turn Object Into Another",
                    "seg": "SEG-AI-31",
                },
                {
                    "id": "ai_character_transformation",
                    "name": "Character Transformation",
                    "seg": "SEG-AI-32",
                },
                {
                    "id": "ai_artistic_region_style",
                    "name": "Artistic Region Style Transfer",
                    "seg": "SEG-AI-33",
                },
                {
                    "id": "ai_sticker_pack_generator",
                    "name": "Smart Sticker Pack Generator",
                    "seg": "SEG-AI-34",
                },
                {
                    "id": "ai_meme_generator",
                    "name": "Meme Generator",
                    "seg": "SEG-AI-35",
                },
                {
                    "id": "ai_avatar_creator",
                    "name": "Avatar Creator",
                    "seg": "SEG-AI-36",
                },
                {
                    "id": "ai_object_variations",
                    "name": "Object Variations",
                    "seg": "SEG-AI-37",
                },
                {
                    "id": "ai_prop_generator",
                    "name": "AI Prop Generator",
                    "seg": "SEG-AI-38",
                },
                {
                    "id": "ai_scene_recomposition",
                    "name": "Scene Recomposition",
                    "seg": "SEG-AI-39",
                },
                {
                    "id": "ai_cinematic_scene",
                    "name": "Cinematic Scene Generator",
                    "seg": "SEG-AI-40",
                },
                {
                    "id": "ai_product_background",
                    "name": "Product Background Generator",
                    "seg": "SEG-AI-41",
                },
                {
                    "id": "ai_marketing_banner",
                    "name": "Marketing Banner Generator",
                    "seg": "SEG-AI-42",
                },
                {
                    "id": "ai_social_post",
                    "name": "Social Post Generator",
                    "seg": "SEG-AI-43",
                },
                {
                    "id": "ai_thumbnail_generator",
                    "name": "Thumbnail Generator",
                    "seg": "SEG-AI-44",
                },
                {
                    "id": "ai_catalog_generator",
                    "name": "Catalog Generator",
                    "seg": "SEG-AI-45",
                },
                {
                    "id": "ai_poster_generator",
                    "name": "Poster Generator",
                    "seg": "SEG-AI-46",
                },
                {
                    "id": "ai_story_scene",
                    "name": "Story Scene Generator",
                    "seg": "SEG-AI-47",
                },
                {
                    "id": "ai_interior_designer",
                    "name": "Interior Designer",
                    "seg": "SEG-AI-48",
                },
                {
                    "id": "ai_fashion_look",
                    "name": "Fashion Look Generator",
                    "seg": "SEG-AI-49",
                },
                {
                    "id": "ai_composite_builder",
                    "name": "AI Composite Builder",
                    "seg": "SEG-AI-50",
                },
            ],
        },
        "controlnet": {
            "label": "ControlNet + IPAdapter",
            "features": [
                {
                    "id": "cn_region_prompting",
                    "name": "Region-Specific Prompting",
                    "seg": "SEG-CN-01",
                },
                {
                    "id": "cn_region_style_injection",
                    "name": "Region Style Injection",
                    "seg": "SEG-CN-02",
                },
                {
                    "id": "cn_face_identity_preservation",
                    "name": "Face Identity Preservation",
                    "seg": "SEG-CN-03",
                },
                {
                    "id": "cn_object_identity_preservation",
                    "name": "Object Identity Preservation",
                    "seg": "SEG-CN-04",
                },
                {
                    "id": "cn_local_character_transfer",
                    "name": "Local Character Transfer",
                    "seg": "SEG-CN-05",
                },
                {
                    "id": "cn_multi_character_scene",
                    "name": "Multi-Character Scene Builder",
                    "seg": "SEG-CN-06",
                },
                {
                    "id": "cn_segment_to_pose",
                    "name": "Segment-to-Pose Generation",
                    "seg": "SEG-CN-07",
                },
                {
                    "id": "cn_clothing_transfer",
                    "name": "Clothing Transfer",
                    "seg": "SEG-CN-08",
                },
                {
                    "id": "cn_hairstyle_transfer",
                    "name": "Hairstyle Transfer",
                    "seg": "SEG-CN-09",
                },
                {
                    "id": "cn_face_style_transfer",
                    "name": "Face Style Transfer",
                    "seg": "SEG-CN-10",
                },
                {
                    "id": "cn_pose_guided_replacement",
                    "name": "Pose Guided Replacement",
                    "seg": "SEG-CN-11",
                },
                {
                    "id": "cn_edge_guided_generation",
                    "name": "Edge Guided Generation",
                    "seg": "SEG-CN-12",
                },
                {
                    "id": "cn_depth_guided_replacement",
                    "name": "Depth Guided Replacement",
                    "seg": "SEG-CN-13",
                },
                {
                    "id": "cn_scribble_guided_editing",
                    "name": "Scribble Guided Editing",
                    "seg": "SEG-CN-14",
                },
                {
                    "id": "cn_shape_preserving_replacement",
                    "name": "Shape Preserving Replacement",
                    "seg": "SEG-CN-15",
                },
                {
                    "id": "cn_segment_perspective_lock",
                    "name": "Segment Perspective Lock",
                    "seg": "SEG-CN-16",
                },
                {
                    "id": "cn_object_reposition_regenerate",
                    "name": "Object Reposition + Regenerate",
                    "seg": "SEG-CN-17",
                },
                {
                    "id": "cn_region_composition_control",
                    "name": "Region Composition Control",
                    "seg": "SEG-CN-18",
                },
                {
                    "id": "cn_character_pose_animator",
                    "name": "Character Pose Animator",
                    "seg": "SEG-CN-19",
                },
                {
                    "id": "cn_scene_layout_generator",
                    "name": "Scene Layout Generator",
                    "seg": "SEG-CN-20",
                },
                {
                    "id": "cn_character_consistency",
                    "name": "Character Consistency",
                    "seg": "SEG-CN-21",
                },
                {
                    "id": "cn_product_consistency",
                    "name": "Product Consistency",
                    "seg": "SEG-CN-22",
                },
                {
                    "id": "cn_brand_asset_preservation",
                    "name": "Brand Asset Preservation",
                    "seg": "SEG-CN-23",
                },
                {
                    "id": "cn_multi_reference_fusion",
                    "name": "Multi-Reference Fusion",
                    "seg": "SEG-CN-24",
                },
                {
                    "id": "cn_regional_reference_mapping",
                    "name": "Regional Reference Mapping",
                    "seg": "SEG-CN-25",
                },
                {"id": "cn_subject_swap", "name": "Subject Swap", "seg": "SEG-CN-26"},
                {
                    "id": "cn_object_attribute_transfer",
                    "name": "Object Attribute Transfer",
                    "seg": "SEG-CN-27",
                },
                {
                    "id": "cn_environment_style_transfer",
                    "name": "Environment Style Transfer",
                    "seg": "SEG-CN-28",
                },
                {
                    "id": "cn_consistent_avatar_builder",
                    "name": "Consistent Avatar Builder",
                    "seg": "SEG-CN-29",
                },
                {
                    "id": "cn_character_sheet_generator",
                    "name": "Character Sheet Generator",
                    "seg": "SEG-CN-30",
                },
                {
                    "id": "cn_smart_region_regeneration",
                    "name": "Smart Region Regeneration",
                    "seg": "SEG-CN-31",
                },
                {
                    "id": "cn_context_aware_fill",
                    "name": "Context-Aware Fill",
                    "seg": "SEG-CN-32",
                },
                {
                    "id": "cn_partial_object_reconstruction",
                    "name": "Partial Object Reconstruction",
                    "seg": "SEG-CN-33",
                },
                {
                    "id": "cn_occlusion_repair",
                    "name": "Occlusion Repair",
                    "seg": "SEG-CN-34",
                },
                {
                    "id": "cn_object_expansion",
                    "name": "Object Expansion",
                    "seg": "SEG-CN-35",
                },
                {
                    "id": "cn_background_reconstruction",
                    "name": "Background Reconstruction",
                    "seg": "SEG-CN-36",
                },
                {
                    "id": "cn_smart_remove_replace",
                    "name": "Smart Remove and Replace",
                    "seg": "SEG-CN-37",
                },
                {
                    "id": "cn_local_variation_generation",
                    "name": "Local Variation Generation",
                    "seg": "SEG-CN-38",
                },
                {
                    "id": "cn_segment_iteration_mode",
                    "name": "Segment Iteration Mode",
                    "seg": "SEG-CN-39",
                },
                {
                    "id": "cn_segment_undo_chain",
                    "name": "Segment Undo Chain",
                    "seg": "SEG-CN-40",
                },
                {
                    "id": "cn_character_into_scene",
                    "name": "Character Into Scene",
                    "seg": "SEG-CN-41",
                },
                {
                    "id": "cn_scene_to_scene_transfer",
                    "name": "Scene-to-Scene Transfer",
                    "seg": "SEG-CN-42",
                },
                {
                    "id": "cn_story_frame_generator",
                    "name": "Story Frame Generator",
                    "seg": "SEG-CN-43",
                },
                {
                    "id": "cn_comic_panel_builder",
                    "name": "Comic Panel Builder",
                    "seg": "SEG-CN-44",
                },
                {
                    "id": "cn_ai_interior_designer",
                    "name": "AI Interior Designer",
                    "seg": "SEG-CN-45",
                },
                {
                    "id": "cn_fashion_outfit_builder",
                    "name": "Fashion Outfit Builder",
                    "seg": "SEG-CN-46",
                },
                {
                    "id": "cn_product_visualization_generator",
                    "name": "Product Visualization Generator",
                    "seg": "SEG-CN-47",
                },
                {
                    "id": "cn_thumbnail_scene_composer",
                    "name": "Thumbnail Scene Composer",
                    "seg": "SEG-CN-48",
                },
                {
                    "id": "cn_cinematic_scene_generator",
                    "name": "Cinematic Scene Generator",
                    "seg": "SEG-CN-49",
                },
                {
                    "id": "cn_layer_to_generation_workflow",
                    "name": "Layer-to-Generation Workflow",
                    "seg": "SEG-CN-50",
                },
            ],
        },
    }
    return APIResponse(status="success", message="Feature catalog", data=catalog)
