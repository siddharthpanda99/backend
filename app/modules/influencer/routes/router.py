"""
AI Influencer Studio — Backend Routes

Endpoints for managing personas and generating consistent AI influencer images.

Routes:
  POST   /personas              Create persona
  GET    /personas              List all personas
  GET    /personas/{id}         Get persona details
  PUT    /personas/{id}         Update persona
  DELETE /personas/{id}         Delete persona
  POST   /personas/{id}/images  Add reference image

  POST   /generate              Generate image (single)
  POST   /generate/parallel     Generate multiple images in parallel
  POST   /generate/batch        Start batch job
  GET    /batch/{job_id}        Get batch job status

  POST   /pipeline/t2i          Text-to-image with persona
  POST   /pipeline/i2i          Image-to-image with persona
  POST   /pipeline/identity     Identity-preserving generation
  POST   /pipeline/pose         Pose-conditioned generation
  POST   /pipeline/controlnet   ControlNet-conditioned generation
  POST   /pipeline/tryon        Virtual try-on
  POST   /pipeline/scene        Scene composite generation

  GET    /presets               Get preset prompts and configs
  GET    /stats                 Generation statistics
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["influencer"])


# ── Request / Response Schemas ──────────────────────────────────────────
class PersonaCreateRequest(BaseModel):
    name: str
    description: str = ""
    reference_images: List[str] = Field(default_factory=list)
    attributes: Dict[str, str] = Field(default_factory=dict)
    style_tokens: List[str] = Field(default_factory=list)
    consistency_method: str = "instantid"
    lora_ids: List[str] = Field(default_factory=list)


class PersonaUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    attributes: Optional[Dict[str, str]] = None
    style_tokens: Optional[List[str]] = None
    consistency_method: Optional[str] = None
    lora_ids: Optional[List[str]] = None


class GenerateRequest(BaseModel):
    persona_id: Optional[str] = None
    mode: str = "text_to_image"
    prompt: str
    negative_prompt: str = ""
    width: int = 1024
    height: int = 1024
    steps: int = 30
    guidance_scale: float = 7.5
    seed: Optional[int] = None
    num_images: int = 1
    consistency_method: Optional[str] = None
    consistency_weight: float = 0.8
    controlnet_type: Optional[str] = None
    controlnet_image: Optional[str] = None
    controlnet_strength: float = 0.7
    ip_adapter_weight: float = 0.6
    pose_image: Optional[str] = None
    source_image: Optional[str] = None
    style_reference: Optional[str] = None
    denoise_strength: float = 0.7
    garment_image: Optional[str] = None
    garment_type: str = "upper"
    try_on_quality: str = "premium"
    background_prompt: Optional[str] = None
    background_mode: str = "replace"
    quality_tier: str = "standard"
    min_face_similarity: float = 0.6
    model_id: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    persona_id: Optional[str] = None
    requests: List[GenerateRequest]
    parallel: bool = False
    max_workers: int = 4


class AddImageRequest(BaseModel):
    image_path: str


# ── Service singleton ───────────────────────────────────────────────────
_service = None


def _get_service():
    global _service
    if _service is None:
        from common_lib.modules.image_processing.services.ai_influencer_service import (
            AIInfluencerService,
        )
        _service = AIInfluencerService()
    return _service


# ── Persona Routes ──────────────────────────────────────────────────────
@router.post("/personas")
async def create_persona(req: PersonaCreateRequest):
    """Create a new AI influencer persona."""
    try:
        from common_lib.modules.image_processing.services.ai_influencer_service import (
            ConsistencyMethod,
        )

        method_str = req.consistency_method.lower()
        try:
            method = ConsistencyMethod(method_str)
        except ValueError:
            method = ConsistencyMethod.INSTANTID

        persona = _get_service().create_persona(
            name=req.name,
            description=req.description,
            reference_images=req.reference_images,
            attributes=req.attributes,
            style_tokens=req.style_tokens,
            consistency_method=method,
            lora_ids=req.lora_ids,
        )
        return {
            "status": "success",
            "persona": _persona_response(persona),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/personas")
async def list_personas():
    """List all personas."""
    personas = _get_service().list_personas()
    return {
        "status": "success",
        "personas": [_persona_response(p) for p in personas],
        "total": len(personas),
    }


@router.get("/personas/{persona_id}")
async def get_persona(persona_id: str):
    """Get persona details."""
    persona = _get_service().get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")
    return {
        "status": "success",
        "persona": _persona_response(persona),
    }


@router.put("/personas/{persona_id}")
async def update_persona(persona_id: str, req: PersonaUpdateRequest):
    """Update a persona."""
    updates = req.model_dump(exclude_none=True)
    persona = _get_service().update_persona(persona_id, **updates)
    if not persona:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")
    return {
        "status": "success",
        "persona": _persona_response(persona),
    }


@router.delete("/personas/{persona_id}")
async def delete_persona(persona_id: str):
    """Delete a persona."""
    deleted = _get_service().delete_persona(persona_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Persona {persona_id} not found")
    return {"status": "success", "deleted": persona_id}


@router.post("/personas/{persona_id}/images")
async def add_reference_image(persona_id: str, req: AddImageRequest):
    """Add a reference image to a persona and re-extract face embedding."""
    try:
        persona = _get_service().add_reference_image(persona_id, req.image_path)
        return {
            "status": "success",
            "persona": _persona_response(persona),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Consistency Report ────────────────────────────────────────────────

@router.get("/personas/{persona_id}/consistency")
async def get_consistency_report(persona_id: str):
    """Get face consistency report for a persona across all generated images."""
    try:
        report = _get_service().get_consistency_report(persona_id)
        return {"status": "success", "report": report}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Consistency report failed: {str(e)}")


# ── Generation Routes ───────────────────────────────────────────────────
@router.post("/generate/stream")
async def generate_image_stream(req: GenerateRequest):
    """Generate a single image with SSE progress streaming."""
    from fastapi.responses import StreamingResponse
    from common_lib.modules.image_processing.services.ai_influencer_stream import stream_generate

    try:
        gen_req = _build_generation_request(req)
        return StreamingResponse(
            stream_generate(_get_service(), gen_req),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_image(req: GenerateRequest):
    """Generate a single image."""
    try:
        from common_lib.modules.image_processing.services.ai_influencer_service import (
            GenerationRequest as GenReq,
            GenerationMode,
            QualityTier,
            ConsistencyMethod,
        )

        gen_req = _build_generation_request(req)
        result = await _get_service().generate(gen_req)
        return {
            "status": "success" if result.status.value == "completed" else "error",
            "result": _result_response(result),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/parallel")
async def generate_parallel(req: BatchGenerateRequest):
    """Generate multiple images in parallel."""
    try:
        from common_lib.modules.image_processing.services.ai_influencer_service import (
            GenerationRequest as GenReq,
        )

        gen_requests = [_build_generation_request(r) for r in req.requests]
        results = await _get_service().generate_parallel(
            gen_requests, max_workers=req.max_workers
        )
        return {
            "status": "success",
            "results": [_result_response(r) for r in results],
            "total": len(results),
            "completed": sum(1 for r in results if r.status.value == "completed"),
            "failed": sum(1 for r in results if r.status.value == "failed"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/batch")
async def start_batch(req: BatchGenerateRequest):
    """Start a batch generation job."""
    try:
        from common_lib.modules.image_processing.services.ai_influencer_service import (
            BatchJob,
            GenerationRequest as GenReq,
        )

        job = BatchJob(
            persona_id=req.persona_id,
            requests=[_build_generation_request(r) for r in req.requests],
        )
        # Run in background
        job = await _get_service().generate_batch(job)
        return {
            "status": "success",
            "job_id": job.id,
            "total": job.total,
            "completed": job.completed,
            "failed": job.failed,
            "results": [_result_response(r) for r in job.results],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/{job_id}")
async def get_batch_status(job_id: str):
    """Get batch job status."""
    job = _get_service().get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Batch job {job_id} not found")
    return {
        "status": "success",
        "job": {
            "id": job.id,
            "persona_id": job.persona_id,
            "total": job.total,
            "completed": job.completed,
            "failed": job.failed,
            "progress_pct": (job.completed / job.total * 100) if job.total else 0,
            "status": job.status.value,
        },
    }


# ── Pipeline Routes ─────────────────────────────────────────────────────
@router.post("/pipeline/t2i")
async def pipeline_t2i(req: GenerateRequest):
    """Text-to-image generation with optional persona consistency."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationRequest as GenReq,
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.T2I
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


@router.post("/pipeline/i2i")
async def pipeline_i2i(req: GenerateRequest):
    """Image-to-image transformation with persona consistency."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.I2I
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


@router.post("/pipeline/identity")
async def pipeline_identity(req: GenerateRequest):
    """Identity-preserving generation (InstantID/PuLID/IP-Adapter)."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.IDENTITY_TRANSFER
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


@router.post("/pipeline/pose")
async def pipeline_pose(req: GenerateRequest):
    """Pose-conditioned generation (OpenPose ControlNet)."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.POSE_CONDITIONED
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


@router.post("/pipeline/controlnet")
async def pipeline_controlnet(req: GenerateRequest):
    """ControlNet-conditioned generation."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.CONTROLNET
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


@router.post("/pipeline/tryon")
async def pipeline_tryon(req: GenerateRequest):
    """Virtual try-on generation."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.VIRTUAL_TRYON
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


@router.post("/pipeline/scene")
async def pipeline_scene(req: GenerateRequest):
    """Scene composite generation (background + person)."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationMode,
    )
    gen_req = _build_generation_request(req)
    gen_req.mode = GenerationMode.SCENE_COMPOSITE
    result = await _get_service().generate(gen_req)
    return {"status": "success", "result": _result_response(result)}


# ── Presets & Stats ─────────────────────────────────────────────────────
@router.get("/presets")
async def get_presets():
    """Get preset prompts, configs, and quick-start templates."""
    return {
        "status": "success",
        "presets": INFLUENCER_PRESETS,
        "poses": POSE_PRESETS,
        "scenes": SCENE_PRESETS,
        "styles": STYLE_PRESETS,
    }


@router.get("/stats")
async def get_stats():
    """Get generation statistics."""
    service = _get_service()
    return {
        "status": "success",
        "stats": {
            "total_personas": len(service.list_personas()),
            "total_batch_jobs": len(service._batch_jobs),
            "methods_available": [
                "instantid", "pulid", "photomaker",
                "ip_adapter_faceid", "reference_only", "face_swap",
            ],
            "modes_available": [
                "text_to_image", "image_to_image",
                "identity_transfer", "pose_conditioned",
                "controlnet", "virtual_tryon", "scene_composite",
            ],
        },
    }


# ── Preset Data ─────────────────────────────────────────────────────────
INFLUENCER_PRESETS = [
    {
        "id": "fashion_editorial",
        "name": "Fashion Editorial",
        "prompt": "high fashion editorial photo, studio lighting, professional photography, magazine cover, sharp focus, 8k",
        "style_tokens": ["fashion", "editorial", "high-end", "professional"],
        "mode": "identity_transfer",
    },
    {
        "id": "casual_lifestyle",
        "name": "Casual Lifestyle",
        "prompt": "casual lifestyle photo, natural lighting, candid pose, coffee shop, warm tones, photorealistic",
        "style_tokens": ["casual", "lifestyle", "warm", "candid"],
        "mode": "text_to_image",
    },
    {
        "id": "street_style",
        "name": "Street Style",
        "prompt": "urban street style photo, city background, dynamic pose, fashionable outfit, golden hour",
        "style_tokens": ["urban", "street", "dynamic", "golden hour"],
        "mode": "scene_composite",
    },
    {
        "id": "beach_vacation",
        "name": "Beach Vacation",
        "prompt": "beach vacation photo, tropical location, sunset, casual summer outfit, ocean background, warm tones",
        "style_tokens": ["beach", "vacation", "tropical", "sunset"],
        "mode": "scene_composite",
    },
    {
        "id": "professional_headshot",
        "name": "Professional Headshot",
        "prompt": "professional headshot, corporate background, suit, confident expression, studio lighting, 4k",
        "style_tokens": ["professional", "corporate", "headshot", "studio"],
        "mode": "identity_transfer",
    },
    {
        "id": "fitness_gym",
        "name": "Fitness & Gym",
        "prompt": "fitness photo, gym setting, athletic wear, dynamic pose, motivational, high energy, dramatic lighting",
        "style_tokens": ["fitness", "athletic", "dynamic", "dramatic"],
        "mode": "pose_conditioned",
    },
    {
        "id": "artistic_portrait",
        "name": "Artistic Portrait",
        "prompt": "artistic portrait, dramatic lighting, Rembrandt lighting, moody atmosphere, fine art photography",
        "style_tokens": ["artistic", "portrait", "dramatic", "fine art"],
        "mode": "identity_transfer",
    },
    {
        "id": "nightlife_glam",
        "name": "Nightlife Glam",
        "prompt": "nightlife glamour photo, neon lights, club atmosphere, glamorous outfit, bold makeup, city at night",
        "style_tokens": ["glamour", "nightlife", "neon", "bold"],
        "mode": "scene_composite",
    },
    {
        "id": "minimalist_clean",
        "name": "Minimalist Clean",
        "prompt": "minimalist photo, clean background, simple outfit, soft lighting, modern aesthetic, high fashion",
        "style_tokens": ["minimalist", "clean", "modern", "aesthetic"],
        "mode": "text_to_image",
    },
    {
        "id": "vintage_retro",
        "name": "Vintage Retro",
        "prompt": "vintage retro photo, 70s aesthetic, warm film tones, retro outfit, grain texture, nostalgic",
        "style_tokens": ["vintage", "retro", "film", "nostalgic"],
        "mode": "text_to_image",
    },
]

POSE_PRESETS = [
    {"id": "standing_confident", "name": "Standing Confident", "pose_type": "openpose", "description": "Hands on hips, confident stance"},
    {"id": "sitting_relaxed", "name": "Sitting Relaxed", "pose_type": "openpose", "description": "Relaxed sitting pose"},
    {"id": "walking_dynamic", "name": "Walking Dynamic", "pose_type": "openpose", "description": "Walking with movement"},
    {"id": "leaning_casual", "name": "Leaning Casual", "pose_type": "openpose", "description": "Leaning against wall"},
    {"id": "crossing_arms", "name": "Crossing Arms", "pose_type": "openpose", "description": "Arms crossed, assertive"},
    {"id": "hands_in_pocket", "name": "Hands in Pockets", "pose_type": "openpose", "description": "Casual hands in pockets"},
    {"id": "pointing", "name": "Pointing", "pose_type": "openpose", "description": "Pointing at camera"},
    {"id": "peace_sign", "name": "Peace Sign", "pose_type": "openpose", "description": "Peace sign gesture"},
    {"id": "runway_walk", "name": "Runway Walk", "pose_type": "openpose", "description": "Fashion runway walking pose"},
    {"id": "dancing", "name": "Dancing", "pose_type": "openpose", "description": "Dynamic dance pose"},
]

SCENE_PRESETS = [
    {"id": "studio_white", "name": "White Studio", "prompt": "white seamless studio background, professional photography", "lighting": "studio"},
    {"id": "studio_dark", "name": "Dark Studio", "prompt": "dark moody studio background, dramatic lighting", "lighting": "dramatic"},
    {"id": "urban_street", "name": "Urban Street", "prompt": "city street background, urban environment, modern architecture", "lighting": "natural"},
    {"id": "nature_forest", "name": "Forest", "prompt": "lush forest background, natural light through trees, green foliage", "lighting": "natural"},
    {"id": "beach_sunset", "name": "Beach Sunset", "prompt": "tropical beach at sunset, ocean waves, golden sand", "lighting": "golden hour"},
    {"id": "cafe_interior", "name": "Cafe Interior", "prompt": "cozy cafe interior, warm lighting, wooden furniture, ambient", "lighting": "warm"},
    {"id": "rooftop_city", "name": "Rooftop City", "prompt": "city rooftop, skyline view, modern urban, glass and steel", "lighting": "golden hour"},
    {"id": "mountain_landscape", "name": "Mountain", "prompt": "mountain landscape, dramatic peaks, clear sky, adventure", "lighting": "natural"},
    {"id": "neon_night", "name": "Neon Night", "prompt": "neon-lit night city, cyberpunk atmosphere, colorful lights", "lighting": "neon"},
    {"id": "minimalist_room", "name": "Minimalist Room", "prompt": "minimalist modern interior, clean lines, neutral tones", "lighting": "soft"},
]

STYLE_PRESETS = [
    {"id": "photorealistic", "name": "Photorealistic", "prompt_addition": "photorealistic, 8k uhd, dslr, sharp focus"},
    {"id": "fashion_magazine", "name": "Fashion Magazine", "prompt_addition": "vogue magazine style, high fashion, editorial"},
    {"id": "cinematic", "name": "Cinematic", "prompt_addition": "cinematic lighting, movie still, dramatic color grading"},
    {"id": "anime", "name": "Anime", "prompt_addition": "anime style, vibrant colors, cel shading"},
    {"id": "oil_painting", "name": "Oil Painting", "prompt_addition": "oil painting style, textured brushstrokes, classical art"},
    {"id": "watercolor", "name": "Watercolor", "prompt_addition": "watercolor painting, soft edges, transparent layers"},
    {"id": "pop_art", "name": "Pop Art", "prompt_addition": "pop art style, bold colors, Andy Warhol inspired"},
    {"id": "noir", "name": "Film Noir", "prompt_addition": "film noir style, black and white, high contrast, moody"},
]


# ── Helper Functions ────────────────────────────────────────────────────
def _build_generation_request(req: GenerateRequest):
    """Convert Pydantic model to service GenerationRequest."""
    from common_lib.modules.image_processing.services.ai_influencer_service import (
        GenerationRequest as GenReq,
        GenerationMode,
        QualityTier,
        ConsistencyMethod,
    )

    mode_map = {
        "text_to_image": GenerationMode.T2I,
        "image_to_image": GenerationMode.I2I,
        "identity_transfer": GenerationMode.IDENTITY_TRANSFER,
        "pose_conditioned": GenerationMode.POSE_CONDITIONED,
        "controlnet": GenerationMode.CONTROLNET,
        "virtual_tryon": GenerationMode.VIRTUAL_TRYON,
        "scene_composite": GenerationMode.SCENE_COMPOSITE,
    }

    tier_map = {
        "fast": QualityTier.FAST,
        "standard": QualityTier.STANDARD,
        "premium": QualityTier.PREMIUM,
    }

    method_map = {
        "instantid": ConsistencyMethod.INSTANTID,
        "pulid": ConsistencyMethod.PULID,
        "photomaker": ConsistencyMethod.PHOTOMAKER,
        "ip_adapter_faceid": ConsistencyMethod.IP_ADAPTER_FACEID,
        "reference_only": ConsistencyMethod.REFERENCE_ONLY,
        "face_swap": ConsistencyMethod.FACE_SWAP,
    }

    kwargs = {
        "persona_id": req.persona_id,
        "mode": mode_map.get(req.mode, GenerationMode.T2I),
        "prompt": req.prompt,
        "negative_prompt": req.negative_prompt,
        "width": req.width,
        "height": req.height,
        "steps": req.steps,
        "guidance_scale": req.guidance_scale,
        "seed": req.seed,
        "num_images": req.num_images,
        "consistency_weight": req.consistency_weight,
        "controlnet_type": req.controlnet_type,
        "controlnet_image": req.controlnet_image,
        "controlnet_strength": req.controlnet_strength,
        "ip_adapter_weight": req.ip_adapter_weight,
        "pose_image": req.pose_image,
        "source_image": req.source_image,
        "style_reference": req.style_reference,
        "denoise_strength": req.denoise_strength,
        "garment_image": req.garment_image,
        "garment_type": req.garment_type,
        "try_on_quality": req.try_on_quality,
        "background_prompt": req.background_prompt,
        "background_mode": req.background_mode,
        "quality_tier": tier_map.get(req.quality_tier, QualityTier.STANDARD),
        "min_face_similarity": req.min_face_similarity,
        "model_id": req.model_id,
    }

    if req.consistency_method:
        kwargs["consistency_method"] = method_map.get(
            req.consistency_method, ConsistencyMethod.INSTANTID
        )

    return GenReq(**kwargs)


def _persona_response(persona) -> Dict[str, Any]:
    return {
        "id": persona.id,
        "name": persona.name,
        "description": persona.description,
        "reference_images": persona.reference_images,
        "face_embedding": persona.face_embedding is not None,
        "face_crop": persona.face_crop_path is not None,
        "consistency_method": persona.consistency_method.value
        if hasattr(persona.consistency_method, "value")
        else persona.consistency_method,
        "attributes": persona.attributes,
        "style_tokens": persona.style_tokens,
        "lora_ids": persona.lora_ids,
        "created_at": persona.created_at,
        "updated_at": persona.updated_at,
    }


def _result_response(result) -> Dict[str, Any]:
    return {
        "id": result.id,
        "request_id": result.request_id,
        "persona_id": result.persona_id,
        "image_base64": result.image_base64,
        "image_path": result.image_path,
        "model_used": result.model_used,
        "method_used": result.method_used,
        "seed_used": result.seed_used,
        "generation_time_ms": result.generation_time_ms,
        "face_similarity": result.face_similarity,
        "quality_score": result.quality_score,
        "passed_quality_gate": result.passed_quality_gate,
        "quality_notes": result.quality_notes,
        "stages_completed": result.stages_completed,
        "routing_info": result.routing_info,
        "error": result.error,
        "status": result.status.value,
    }
