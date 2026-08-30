"""
Face Routes — Dedicated /api/v1/face/ endpoints for all face operations.

Thin router layer delegating to common_lib face services.
"""

from __future__ import annotations

import base64
import logging
import io
import time
import json
import asyncio
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body, Query
from fastapi.responses import Response, StreamingResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Face Operations"])


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _decode_image(b64_data: str) -> np.ndarray:
    """Decode base64 image to RGB numpy array."""
    from PIL import Image

    raw = base64.b64decode(b64_data)
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(pil)


def _encode_image(arr: np.ndarray) -> str:
    """Encode RGB numpy array to base64 PNG."""
    from PIL import Image

    pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _decode_optional_image(data: Dict[str, Any], key: str = "image") -> Optional[np.ndarray]:
    """Decode optional base64 image from request body."""
    val = data.get(key)
    if val:
        return _decode_image(val)
    return None


# ── Detection ────────────────────────────────────────────────────


@router.post("/detect")
async def detect_faces(body: Dict[str, Any] = Body(...)):
    """Detect faces in an image. Returns bounding boxes, landmarks, embeddings."""
    from common_lib.modules.image_processing.services.face_operations import (
        detect_faces as _detect,
    )

    image = _decode_image(body.get("image", ""))
    detector = body.get("detector", "scrfd")
    confidence = body.get("confidence", 0.5)
    max_faces = body.get("max_faces", 10)

    faces = _detect(image, detector=detector, confidence=confidence, max_faces=max_faces)
    return {
        "status": "success",
        "faces": faces,
        "count": len(faces),
    }


@router.post("/landmarks")
async def detect_landmarks(body: Dict[str, Any] = Body(...)):
    """Detect facial landmarks within a face bounding box."""
    from common_lib.modules.image_processing.services.face_operations import (
        detect_landmarks as _landmarks,
    )

    image = _decode_image(body.get("image", ""))
    bbox = body.get("bbox")
    model = body.get("model", "mediapipe")

    if not bbox:
        raise HTTPException(400, detail="Missing 'bbox' [x1, y1, x2, y2]")

    result = _landmarks(image, bbox, model=model)
    # Convert numpy arrays for JSON serialization
    if "points" in result and isinstance(result["points"], np.ndarray):
        result["points"] = result["points"].tolist()
    return {"status": "success", **result}


# ── Alignment / Crop ────────────────────────────────────────────


@router.post("/align")
async def align_face(body: Dict[str, Any] = Body(...)):
    """Align and center a face using eye landmarks."""
    from common_lib.modules.image_processing.services.face_operations import align_face

    image = _decode_image(body.get("image", ""))
    landmarks = np.array(body.get("landmarks", []))
    output_size = tuple(body.get("output_size", [256, 256]))
    scale = body.get("scale", 1.0)

    if len(landmarks) < 5:
        raise HTTPException(400, detail="Need at least 5 landmarks for alignment")

    result = align_face(image, landmarks, output_size=output_size, scale=scale)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/crop")
async def crop_face(body: Dict[str, Any] = Body(...)):
    """Crop a face from an image with margin."""
    from common_lib.modules.image_processing.services.face_operations import crop_face

    image = _decode_image(body.get("image", ""))
    bbox = body.get("bbox")
    margin = body.get("margin", 1.6)
    output_size = tuple(body.get("output_size", [256, 256]))

    if not bbox:
        raise HTTPException(400, detail="Missing 'bbox' [x1, y1, x2, y2]")

    result = crop_face(image, bbox, margin=margin, output_size=output_size)
    return {"status": "success", "image": _encode_image(result)}


# ── Quality Assessment ──────────────────────────────────────────


@router.post("/quality")
async def assess_quality(body: Dict[str, Any] = Body(...)):
    """Assess face quality (sharpness, brightness, noise, size)."""
    from common_lib.modules.image_processing.services.face_operations import (
        assess_face_quality,
    )

    image = _decode_image(body.get("image", ""))
    bbox = body.get("bbox")
    result = assess_face_quality(image, face_bbox=bbox)
    return {"status": "success", **result}


# ── Restoration ─────────────────────────────────────────────────


@router.post("/restore")
async def restore_face(body: Dict[str, Any] = Body(...)):
    """Restore a degraded face using CodeFormer or GFPGAN."""
    from common_lib.modules.image_processing.services.face_operations import restore_face

    image = _decode_image(body.get("image", ""))
    model = body.get("model", "codeformer")
    fidelity = body.get("fidelity", 0.5)
    upscale = body.get("upscale", False)

    result = restore_face(image, model=model, fidelity=fidelity, upscale=upscale)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/restore/stream")
async def restore_face_stream(body: Dict[str, Any] = Body(...)):
    """Restore face with SSE progress streaming."""
    from common_lib.modules.image_processing.services.face_operations import restore_face

    image = _decode_image(body.get("image", ""))
    model = body.get("model", "codeformer")
    fidelity = body.get("fidelity", 0.5)

    async def event_generator():
        start = time.time()
        yield _sse("progress", {"percent": 10, "message": "Detecting faces...", "phase": "Detection"})
        await asyncio.sleep(0.1)

        yield _sse("progress", {"percent": 30, "message": "Loading restoration model...", "phase": "Model"})
        await asyncio.sleep(0.1)

        yield _sse("progress", {"percent": 50, "message": "Restoring face...", "phase": "Processing"})
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: restore_face(image, model=model, fidelity=fidelity))

        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encoding"})
        img_b64 = _encode_image(result)

        elapsed = time.time() - start
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"model": model, "fidelity": fidelity, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Swapping ────────────────────────────────────────────────────


@router.post("/swap")
async def swap_face(body: Dict[str, Any] = Body(...)):
    """Swap face from source onto target."""
    from common_lib.modules.image_processing.services.face_operations import swap_face

    source = _decode_image(body.get("source", ""))
    target = _decode_image(body.get("target", ""))
    source_bbox = body.get("source_bbox")
    target_bbox = body.get("target_bbox")
    model = body.get("model", "inswapper")

    result = swap_face(source, target, source_bbox=source_bbox, target_bbox=target_bbox, model=model)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/swap/stream")
async def swap_face_stream(body: Dict[str, Any] = Body(...)):
    """Swap face with SSE progress streaming."""
    from common_lib.modules.image_processing.services.face_operations import swap_face

    source = _decode_image(body.get("source", ""))
    target = _decode_image(body.get("target", ""))
    model = body.get("model", "inswapper")

    async def event_generator():
        start = time.time()
        yield _sse("progress", {"percent": 10, "message": "Detecting source face...", "phase": "Detection"})
        await asyncio.sleep(0.1)

        yield _sse("progress", {"percent": 30, "message": "Detecting target face...", "phase": "Detection"})
        await asyncio.sleep(0.1)

        yield _sse("progress", {"percent": 50, "message": "Swapping face...", "phase": "Processing"})
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: swap_face(source, target, model=model))

        yield _sse("progress", {"percent": 90, "message": "Blending...", "phase": "Post-process"})
        img_b64 = _encode_image(result)

        elapsed = time.time() - start
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"model": model, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Identity ────────────────────────────────────────────────────


@router.post("/identity/embed")
async def compute_embedding(body: Dict[str, Any] = Body(...)):
    """Compute face identity embedding (ArcFace)."""
    from common_lib.modules.image_processing.services.face_operations import (
        compute_face_embedding,
    )

    image = _decode_image(body.get("image", ""))
    bbox = body.get("bbox")
    model = body.get("model", "arcface")

    embedding = compute_face_embedding(image, face_bbox=bbox, model=model)
    if embedding is None:
        raise HTTPException(400, detail="No face detected in image")
    return {"status": "success", "embedding": embedding, "dimension": len(embedding)}


@router.post("/identity/compare")
async def compare_faces(body: Dict[str, Any] = Body(...)):
    """Compare two face embeddings for identity similarity."""
    from common_lib.modules.image_processing.services.face_operations import compare_faces

    emb_a = body.get("embedding_a")
    emb_b = body.get("embedding_b")
    if not emb_a or not emb_b:
        raise HTTPException(400, detail="Need 'embedding_a' and 'embedding_b'")

    similarity = compare_faces(emb_a, emb_b)
    return {
        "status": "success",
        "similarity": similarity,
        "match": similarity > 0.5,
        "confidence": "high" if similarity > 0.8 else "medium" if similarity > 0.5 else "low",
    }


# ── Expression ──────────────────────────────────────────────────


@router.post("/expression")
async def edit_expression(body: Dict[str, Any] = Body(...)):
    """Edit facial expression (smile, sad, surprised, angry, serious, neutral)."""
    from common_lib.modules.image_processing.services.face_operations import edit_expression

    image = _decode_image(body.get("image", ""))
    expression = body.get("expression", "smile")
    strength = body.get("strength", 0.5)

    result = edit_expression(image, expression=expression, strength=strength)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/expression/stream")
async def edit_expression_stream(body: Dict[str, Any] = Body(...)):
    """Edit expression with SSE progress streaming."""
    from common_lib.modules.image_processing.services.face_operations import edit_expression
    image = _decode_image(body.get("image", ""))
    expression = body.get("expression", "smile")
    strength = body.get("strength", 0.5)

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 10, "message": "Detecting face landmarks...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 30, "message": f"Applying {expression}...", "phase": "Editing"})
        result = edit_expression(image, expression=expression, strength=strength)
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"expression": expression, "strength": strength, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Age ─────────────────────────────────────────────────────────


@router.post("/age")
async def transform_age(body: Dict[str, Any] = Body(...)):
    """Transform face age (5-80)."""
    from common_lib.modules.image_processing.services.face_operations import transform_age

    image = _decode_image(body.get("image", ""))
    target_age = body.get("target_age", 30)

    result = transform_age(image, target_age=target_age)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/age/stream")
async def transform_age_stream(body: Dict[str, Any] = Body(...)):
    """Transform age with SSE progress streaming."""
    from common_lib.modules.image_processing.services.face_operations import transform_age
    image = _decode_image(body.get("image", ""))
    target_age = body.get("target_age", 30)

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 10, "message": "Detecting face...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 40, "message": f"Transforming to age {target_age}...", "phase": "Processing"})
        result = transform_age(image, target_age=target_age)
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"target_age": target_age, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Relighting ──────────────────────────────────────────────────


@router.post("/relight")
async def relight_face(body: Dict[str, Any] = Body(...)):
    """Relight face with directional lighting."""
    from common_lib.modules.image_processing.services.face_operations import relight_face

    image = _decode_image(body.get("image", ""))
    direction = body.get("direction", "front")
    color = body.get("color", [255, 255, 255])
    intensity = body.get("intensity", 0.7)

    result = relight_face(image, light_direction=direction, light_color=tuple(color), intensity=intensity)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/relight/stream")
async def relight_face_stream(body: Dict[str, Any] = Body(...)):
    """Relight face with SSE progress streaming."""
    from common_lib.modules.image_processing.services.face_operations import relight_face
    image = _decode_image(body.get("image", ""))
    direction = body.get("direction", "front")
    color = body.get("color", [255, 255, 255])
    intensity = body.get("intensity", 0.7)

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 10, "message": "Detecting face...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 40, "message": f"Relighting from {direction}...", "phase": "Processing"})
        result = relight_face(image, light_direction=direction, light_color=tuple(color), intensity=intensity)
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"direction": direction, "intensity": intensity, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Eyes ────────────────────────────────────────────────────────


@router.post("/eyes")
async def edit_eyes(body: Dict[str, Any] = Body(...)):
    """Edit eyes (color, whiten, eyelash, enhance, bags)."""
    from common_lib.modules.image_processing.services.face_operations import edit_eyes

    image = _decode_image(body.get("image", ""))
    operation = body.get("operation", "whiten")
    value = body.get("value")
    strength = body.get("strength", 0.5)

    result = edit_eyes(image, operation=operation, value=value, strength=strength)
    return {"status": "success", "image": _encode_image(result)}


# ── Mouth / Teeth ───────────────────────────────────────────────


@router.post("/mouth")
async def edit_mouth(body: Dict[str, Any] = Body(...)):
    """Edit mouth (whiten_teeth, lip_color, smile, shape)."""
    from common_lib.modules.image_processing.services.face_operations import edit_mouth

    image = _decode_image(body.get("image", ""))
    operation = body.get("operation", "whiten_teeth")
    value = body.get("value")
    strength = body.get("strength", 0.5)

    result = edit_mouth(image, operation=operation, value=value, strength=strength)
    return {"status": "success", "image": _encode_image(result)}


# ── Enhancement / Beautification ────────────────────────────────


@router.post("/enhance")
async def face_enhance(body: Dict[str, Any] = Body(...)):
    """Full face enhancement pipeline."""
    from common_lib.modules.image_processing.services.face_operations import (
        full_beautification,
    )

    image = _decode_image(body.get("image", ""))
    params = {k: v for k, v in body.items() if k != "image"}

    result = full_beautification(image, **params)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/enhance/stream")
async def face_enhance_stream(body: Dict[str, Any] = Body(...)):
    """Full face enhancement with SSE progress streaming."""
    from common_lib.modules.image_processing.services.face_operations import (
        full_beautification,
    )

    image = _decode_image(body.get("image", ""))
    params = {k: v for k, v in body.items() if k != "image"}

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Analyzing face...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 20, "message": "Smoothing skin...", "phase": "Skin"})
        await asyncio.sleep(0)
        result = full_beautification(image, **params)
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Makeup ───────────────────────────────────────────────────


@router.post("/makeup")
async def apply_makeup(body: Dict[str, Any] = Body(...)):
    """Transfer makeup from reference image onto target face."""
    from common_lib.modules.image_processing.services.beauty_operations import (
        makeup_transfer,
    )

    image = _decode_image(body.get("image", ""))
    reference = _decode_optional_image(body, "reference")
    region = body.get("region", "full")
    intensity = body.get("intensity", 0.7)

    if reference is None:
        raise HTTPException(400, detail="Missing 'reference' image for makeup transfer")

    result = makeup_transfer(image, reference, region=region, intensity=intensity)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/makeup/preset")
async def apply_makeup_preset(body: Dict[str, Any] = Body(...)):
    """Apply a predefined makeup preset (natural, glam, smoky, etc.)."""
    from common_lib.modules.image_processing.services.beauty_operations import (
        makeup_preset,
    )

    image = _decode_image(body.get("image", ""))
    preset_id = body.get("preset", body.get("preset_id", "natural_glam"))

    result = makeup_preset(image, preset_id=preset_id)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/makeup/text")
async def apply_makeup_text(body: Dict[str, Any] = Body(...)):
    """Apply text-guided makeup (e.g. 'bold red lipstick, smoky eyes')."""
    from common_lib.modules.image_processing.services.beauty_operations import (
        makeup_apply_text,
    )

    image = _decode_image(body.get("image", ""))
    prompt = body.get("prompt", body.get("makeup_prompt", ""))
    strength = body.get("strength", 0.6)

    result = makeup_apply_text(image, prompt, strength=strength)
    return {"status": "success", "image": _encode_image(result)}


# ── Tattoo ───────────────────────────────────────────────────


@router.post("/tattoo/design")
async def design_tattoo(body: Dict[str, Any] = Body(...)):
    """Design a tattoo pattern from text prompt."""
    from common_lib.modules.image_processing.services.skin_operations import (
        tattoo_design,
    )

    prompt = body.get("prompt", "")
    style = body.get("style", "traditional")
    colors = body.get("colors")
    body_part = body.get("body_part")

    result = tattoo_design(prompt=prompt, style=style, colors=colors, body_part=body_part)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/tattoo/place")
async def place_tattoo(body: Dict[str, Any] = Body(...)):
    """Place a tattoo on a body region with realistic perspective."""
    from common_lib.modules.image_processing.services.skin_operations import (
        tattoo_place,
    )

    image = _decode_image(body.get("image", ""))
    tattoo = _decode_image(body.get("tattoo", ""))
    body_part = body.get("body_part", body.get("body_region", "arm"))
    x = body.get("x")
    y = body.get("y")

    result = tattoo_place(image, tattoo, body_part=body_part, x=x, y=y)
    return {"status": "success", "image": _encode_image(result)}


@router.post("/tattoo/remove")
async def remove_tattoo(body: Dict[str, Any] = Body(...)):
    """Remove a tattoo using inpainting."""
    from common_lib.modules.image_processing.services.skin_operations import (
        tattoo_remove,
    )

    image = _decode_image(body.get("image", ""))
    tattoo_region = body.get("tattoo_region")
    fade_sessions = body.get("fade_sessions", 0)

    result = tattoo_remove(image, tattoo_region=tattoo_region, fade_sessions=fade_sessions)
    return {"status": "success", "image": _encode_image(result)}


# ── Task Router ─────────────────────────────────────────────────


@router.post("/route")
async def route_face_task(body: Dict[str, Any] = Body(...)):
    """Get optimal routing recommendation for a face operation."""
    from common_lib.modules.image_processing.services.task_router import (
        route_face_operation,
        QualityTier,
    )

    operation = body.get("operation")
    if not operation:
        raise HTTPException(400, detail="Missing 'operation'")

    quality_tier = None
    if body.get("quality_tier"):
        quality_tier = QualityTier(body["quality_tier"])

    image_analysis = body.get("image_analysis")

    result = route_face_operation(
        operation,
        image_analysis=image_analysis,
        quality_tier=quality_tier,
    )

    if result is None:
        raise HTTPException(404, detail=f"No route found for '{operation}'")

    return {
        "status": "success",
        "operation": result.operation,
        "method": result.method,
        "model": result.model,
        "quality_tier": result.quality_tier.value,
        "hardware_tier": result.hardware_tier.value,
        "estimated_time_seconds": result.estimated_time_seconds,
        "estimated_vram_mb": result.estimated_vram_mb,
        "fallback_method": result.fallback_method,
        "notes": result.notes,
        "params": result.params,
    }


@router.get("/operations")
async def list_face_operations():
    """List all available face operations and their routing profiles."""
    from common_lib.modules.image_processing.services.task_router import (
        get_operations_by_tag,
    )

    face_ops = get_operations_by_tag("face")
    return {"status": "success", "operations": face_ops, "count": len(face_ops)}


@router.get("/hardware")
async def get_hardware_info():
    """Get current hardware capabilities."""
    from common_lib.modules.image_processing.services.task_router import (
        detect_hardware,
        get_available_vram_mb,
    )

    return {
        "status": "success",
        "hardware": detect_hardware().value,
        "vram_mb": get_available_vram_mb(),
    }


# ── Health Checks ─────────────────────────────────────────────


def _check_model_exists(*paths: str) -> bool:
    """Check if any of the given model file paths exist."""
    import os
    return any(os.path.isfile(p) for p in paths)


def _check_importable(module_path: str, attr: str) -> bool:
    """Check if a module attribute can be imported."""
    try:
        mod = __import__(module_path, fromlist=[attr])
        return hasattr(mod, attr)
    except (ImportError, Exception):
        return False


@router.get("/health")
async def health_check():
    """Overall face API health — checks all models and dependencies."""
    from common_lib.paths import RESOURCES_ROOT

    resources = str(RESOURCES_ROOT)
    models = {
        # Detection
        "insightface_scrfd": _check_importable("insightface", "FaceAnalysis"),
        "insightface_models": _check_model_exists(
            os.path.join(os.path.expanduser("~"), ".insightface", "models", "buffalo_l", "det_10g.onnx"),
        ) if _check_importable("insightface", "FaceAnalysis") else False,

        # Restoration
        "codeformer": _check_model_exists(
            os.path.join(resources, "image_models", "reactor", "facerestore", "CodeFormer.pth"),
        ),
        "gfpgan": _check_model_exists(
            os.path.join(resources, "image_models", "reactor", "facerestore", "GFPGANv1.4.pth"),
        ),

        # Face parsing
        "bisenet_parsing": _check_model_exists(
            os.path.join(resources, "image_models", "face", "parsing", "79999_iter.pth"),
        ),

        # Swapping
        "inswapper_128": _check_model_exists(
            os.path.join(resources, "image_models", "insightface", "models", "inswapper_128.onnx"),
        ),

        # Dependencies
        "opencv": _check_importable("cv2", "imread"),
        "mediapipe": _check_importable("mediapipe", "solutions"),
        "torch": _check_importable("torch", "Tensor"),
        "numpy": _check_importable("numpy", "array"),
    }

    available_count = sum(1 for v in models.values() if v)
    total_count = len(models)
    overall = "healthy" if available_count >= 5 else "degraded" if available_count >= 3 else "unhealthy"

    return {
        "status": "success",
        "health": overall,
        "models": models,
        "available": available_count,
        "total": total_count,
        "operations": {
            "detect": models.get("insightface_scrfd", False),
            "restore": models.get("codeformer", False) or models.get("gfpgan", False),
            "swap": models.get("inswapper_128", False) and models.get("insightface_scrfd", False),
            "expression": models.get("bisenet_parsing", False),
            "age": models.get("bisenet_parsing", False),
            "relight": models.get("opencv", False),
            "eyes": models.get("bisenet_parsing", False),
            "mouth": models.get("bisenet_parsing", False),
            "enhance": models.get("opencv", False),
            "makeup": models.get("opencv", False),
            "tattoo": models.get("opencv", False),
        },
    }


import os


@router.get("/health/models")
async def health_models():
    """Check which face models are downloaded and available."""
    from common_lib.paths import RESOURCES_ROOT

    resources = str(RESOURCES_ROOT)
    home = os.path.expanduser("~")

    models = {}

    # ── Detection models ──
    insightface_dir = os.path.join(home, ".insightface", "models", "buffalo_l")
    models["insightface_buffalo_l"] = {
        "available": os.path.isdir(insightface_dir),
        "path": insightface_dir,
        "files": os.listdir(insightface_dir) if os.path.isdir(insightface_dir) else [],
    }

    # ── Restoration models ──
    restore_dir = os.path.join(resources, "image_models", "reactor", "facerestore")
    for name in ["CodeFormer.pth", "GFPGANv1.4.pth"]:
        path = os.path.join(restore_dir, name)
        models[name.replace(".pth", "").lower()] = {
            "available": os.path.isfile(path),
            "path": path,
            "size_mb": round(os.path.getsize(path) / 1024 / 1024, 1) if os.path.isfile(path) else 0,
        }

    # ── Face parsing ──
    parsing_dir = os.path.join(resources, "image_models", "face", "parsing")
    models["bisenet_parsing"] = {
        "available": os.path.isfile(os.path.join(parsing_dir, "79999_iter.pth")),
        "path": os.path.join(parsing_dir, "79999_iter.pth"),
        "size_mb": round(os.path.getsize(os.path.join(parsing_dir, "79999_iter.pth")) / 1024 / 1024, 1)
            if os.path.isfile(os.path.join(parsing_dir, "79999_iter.pth")) else 0,
    }

    # ── Swapping models ──
    inswapper_path = os.path.join(resources, "image_models", "insightface", "models", "inswapper_128.onnx")
    models["inswapper_128"] = {
        "available": os.path.isfile(inswapper_path),
        "path": inswapper_path,
        "size_mb": round(os.path.getsize(inswapper_path) / 1024 / 1024, 1) if os.path.isfile(inswapper_path) else 0,
    }

    available = sum(1 for m in models.values() if m["available"])
    return {
        "status": "success",
        "models": models,
        "available": available,
        "total": len(models),
    }


# Model health map: operation → list of model file paths to check
_OPERATION_MODELS: Dict[str, List[str]] = {
    "detect": [
        os.path.join(os.path.expanduser("~"), ".insightface", "models", "buffalo_l", "det_10g.onnx"),
    ],
    "restore": [
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "reactor", "facerestore", "CodeFormer.pth"),
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "reactor", "facerestore", "GFPGANv1.4.pth"),
    ],
    "swap": [
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "insightface", "models", "inswapper_128.onnx"),
    ],
    "expression": [
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "face", "parsing", "79999_iter.pth"),
    ],
    "age": [
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "face", "parsing", "79999_iter.pth"),
    ],
    "eyes": [
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "face", "parsing", "79999_iter.pth"),
    ],
    "mouth": [
        os.path.join(str(RESOURCES_ROOT) if 'RESOURCES_ROOT' in dir() else "resources", "image_models", "face", "parsing", "79999_iter.pth"),
    ],
}


@router.get("/health/{operation}")
async def health_operation(operation: str):
    """Check if a specific face operation has its required models available."""
    from common_lib.paths import RESOURCES_ROOT as _RES

    # Build dynamic paths with actual RESOURCES_ROOT
    resources = str(_RES)
    home = os.path.expanduser("~")
    op_models: Dict[str, List[str]] = {
        "detect": [os.path.join(home, ".insightface", "models", "buffalo_l", "det_10g.onnx")],
        "restore": [
            os.path.join(resources, "image_models", "reactor", "facerestore", "CodeFormer.pth"),
            os.path.join(resources, "image_models", "reactor", "facerestore", "GFPGANv1.4.pth"),
        ],
        "swap": [os.path.join(resources, "image_models", "insightface", "models", "inswapper_128.onnx")],
        "expression": [os.path.join(resources, "image_models", "face", "parsing", "79999_iter.pth")],
        "age": [os.path.join(resources, "image_models", "face", "parsing", "79999_iter.pth")],
        "relight": [],
        "eyes": [os.path.join(resources, "image_models", "face", "parsing", "79999_iter.pth")],
        "mouth": [os.path.join(resources, "image_models", "face", "parsing", "79999_iter.pth")],
        "enhance": [],
        "makeup": [],
        "tattoo": [],
    }

    if operation not in op_models:
        raise HTTPException(404, detail=f"Unknown operation: {operation}. Known: {list(op_models.keys())}")

    required = op_models[operation]
    available = [_check_model_exists(p) for p in required]
    any_available = any(available)

    return {
        "status": "success",
        "operation": operation,
        "available": any_available,
        "models": {
            os.path.basename(p): {"path": p, "exists": exists}
            for p, exists in zip(required, available)
        } if required else {"note": "CPU-only operation, no models required"},
    }


# ── Sticker Generation (Doc 11 §1) ─────────────────────────────


@router.post("/sticker/generate")
async def generate_sticker(body: Dict[str, Any] = Body(...)):
    """Generate a sticker from a base image.

    Args:
        image: Base64 source image.
        style: Sticker style (flat, kawaii, line_art, watercolor, retro, holographic, emoji, 3d_bubble, cottagecore, meme).
        add_border: Add sticker outline border.
        border_color: Border color hex.
        border_width: Border width in pixels.
    """
    from common_lib.modules.image_processing.services.compositing_service import generate_sticker as _gen_sticker, STICKER_STYLES

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    style = body.get("style", "flat")
    if style not in STICKER_STYLES:
        raise HTTPException(400, detail=f"Unknown style '{style}'. Available: {list(STICKER_STYLES.keys())}")

    img = _decode_image(image_b64)
    result = _gen_sticker(
        base_image=img,
        style=style,
        add_border=body.get("add_border", True),
        border_color=body.get("border_color", "#ffffff"),
        border_width=body.get("border_width", 4),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "style": style,
        "style_prompt": result["style_prompt"],
        "border_applied": result["border_applied"],
        "output_size": result["output_size"],
    }


@router.post("/sticker/from-photo")
async def sticker_from_photo(body: Dict[str, Any] = Body(...)):
    """Create a sticker from a photo by extracting the subject.

    Args:
        photo: Base64 photo image.
        style: Sticker style.
        subject_hint: Optional hint for subject detection.
    """
    from common_lib.modules.image_processing.services.compositing_service import sticker_from_photo as _sticker_photo

    photo_b64 = body.get("photo")
    if not photo_b64:
        raise HTTPException(400, detail="photo (base64) is required")

    img = _decode_image(photo_b64)
    result = _sticker_photo(
        photo=img,
        style=body.get("style", "flat"),
        subject_hint=body.get("subject_hint"),
        add_border=body.get("add_border", True),
        border_color=body.get("border_color", "#ffffff"),
        border_width=body.get("border_width", 4),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "source": result["source"],
        "style": result["style_prompt"],
        "border_applied": result["border_applied"],
    }


@router.post("/sticker/character-pack")
async def generate_character_pack(body: Dict[str, Any] = Body(...)):
    """Generate a character sticker pack with multiple expressions.

    Args:
        image: Base64 base character image.
        expressions: List of expressions (happy, sad, surprised, angry, love, waving, etc.).
        style: Sticker style.
    """
    from common_lib.modules.image_processing.services.compositing_service import generate_character_pack as _char_pack

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = _char_pack(
        base_image=img,
        expressions=body.get("expressions"),
        style=body.get("style", "kawaii"),
    )

    return {
        "status": "success",
        "stickers": [
            {"expression": s["expression"], "image": _encode_image(s["image"]), "style": s["style"]}
            for s in result["stickers"]
        ],
        "count": result["count"],
        "style": result["style"],
    }


# ── Logo Generation (Doc 11 §2) ────────────────────────────────────


@router.post("/logo/generate")
async def generate_logo(body: Dict[str, Any] = Body(...)):
    """Generate a logo from brand name and style.

    Args:
        brand_name: Brand text.
        style: Logo style (minimal, bold, elegant, playful, retro, abstract, tech, organic).
        colors: List of hex colors.
        tagline: Optional tagline.
    """
    from common_lib.modules.image_processing.services.compositing_service import generate_logo as _gen_logo, LOGO_STYLES

    brand_name = body.get("brand_name")
    if not brand_name:
        raise HTTPException(400, detail="brand_name is required")

    style = body.get("style", "minimal")
    if style not in LOGO_STYLES:
        raise HTTPException(400, detail=f"Unknown style '{style}'. Available: {list(LOGO_STYLES.keys())}")

    result = _gen_logo(
        brand_name=brand_name,
        style=style,
        colors=body.get("colors"),
        tagline=body.get("tagline"),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "brand_name": result["brand_name"],
        "style": style,
        "style_prompt": result["style_prompt"],
        "colors": result["colors"],
    }


@router.post("/logo/vectorize")
async def vectorize_logo(body: Dict[str, Any] = Body(...)):
    """Convert a raster logo to SVG vector format.

    Args:
        image: Base64 raster logo image.
        format: Output format ('svg' or 'eps').
    """
    from common_lib.modules.image_processing.services.compositing_service import vectorize_logo as _vec_logo

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = _vec_logo(img=img, output_format=body.get("format", "svg"))

    return {
        "status": "success",
        "svg_data": result["svg_data"],
        "format": result["format"],
        "contour_count": result["contour_count"],
        "width": result["width"],
        "height": result["height"],
    }


@router.post("/logo/variations")
async def logo_variations(body: Dict[str, Any] = Body(...)):
    """Generate color variations of a logo (dark, monochrome, light).

    Args:
        image: Base64 logo image.
        variations: List of variation types (dark_mode, monochrome, light_mode).
    """
    from common_lib.modules.image_processing.services.compositing_service import generate_logo_variations as _logo_vars

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = _logo_vars(logo=img, variations=body.get("variations"))

    return {
        "status": "success",
        "variations": [
            {"name": v["name"], "image": _encode_image(v["image"])}
            for v in result["variations"]
        ],
        "count": result["count"],
    }


# ── Image Compositing (Doc 11 §3) ──────────────────────────────────


@router.post("/composite/overlay")
async def composite_overlay(body: Dict[str, Any] = Body(...)):
    """Overlay an image on a base with blend mode and opacity.

    Args:
        base_image: Base64 background image.
        overlay_image: Base64 overlay image.
        position: [x, y] placement.
        scale: Scale factor for overlay.
        blend_mode: normal, multiply, screen, overlay, soft_light, etc.
        opacity: Overlay opacity 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.compositing_service import overlay_image as _overlay

    base_b64 = body.get("base_image")
    overlay_b64 = body.get("overlay_image")
    if not base_b64 or not overlay_b64:
        raise HTTPException(400, detail="base_image and overlay_image (base64) are required")

    base = _decode_image(base_b64)
    overlay = _decode_image(overlay_b64)

    result = _overlay(
        base=base,
        overlay=overlay,
        position=tuple(body.get("position", [0, 0])),
        scale=body.get("scale", 1.0),
        blend_mode=body.get("blend_mode", "normal"),
        opacity=body.get("opacity", 1.0),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "blend_mode": result["blend_mode"],
        "opacity": result["opacity"],
        "position": result["position"],
    }


@router.post("/composite/harmonize")
async def composite_harmonize(body: Dict[str, Any] = Body(...)):
    """Harmonize a composite image to match lighting and color.

    Args:
        image: Base64 composited image.
        light_direction: auto, left, right, top, bottom.
        color_temperature: 0.0 (cool) to 1.0 (warm).
        intensity: Harmonization strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.compositing_service import harmonize_composite as _harmonize

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = _harmonize(
        composite=img,
        light_direction=body.get("light_direction", "auto"),
        color_temperature=body.get("color_temperature", 0.5),
        intensity=body.get("intensity", 0.5),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "adjustments": result["adjustments"],
    }


@router.post("/composite/add-shadow")
async def composite_add_shadow(body: Dict[str, Any] = Body(...)):
    """Add a cast shadow under/around a subject.

    Args:
        image: Base64 image with subject.
        subject_mask: Optional base64 alpha mask of subject.
        light_direction: Direction light comes FROM.
        shadow_opacity: Shadow transparency 0.0-1.0.
        shadow_blur: Blur radius.
        shadow_color: Shadow color hex.
    """
    from common_lib.modules.image_processing.services.compositing_service import add_shadow as _shadow

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    mask = _decode_image(body["subject_mask"]).getchannel("A") if body.get("subject_mask") else None

    result = _shadow(
        image=img,
        subject_mask=mask,
        light_direction=body.get("light_direction", "bottom-right"),
        shadow_opacity=body.get("shadow_opacity", 0.3),
        shadow_blur=body.get("shadow_blur", 10.0),
        shadow_color=body.get("shadow_color", "#000000"),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "light_direction": result["light_direction"],
        "offset": list(result["offset"]),
    }


@router.post("/composite/add-text")
async def composite_add_text(body: Dict[str, Any] = Body(...)):
    """Add styled text overlay to an image.

    Args:
        image: Base64 image.
        text: Text to render.
        position: [x, y] position.
        font_size: Font size in pixels.
        color: Text color hex.
        bg_color: Optional background color hex.
        opacity: Text opacity 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.compositing_service import add_text_overlay as _text

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    text = body.get("text")
    if not text:
        raise HTTPException(400, detail="text is required")

    img = _decode_image(image_b64)
    result = _text(
        image=img,
        text=text,
        position=tuple(body.get("position", [0, 0])),
        font_size=body.get("font_size", 48),
        color=body.get("color", "#ffffff"),
        bg_color=body.get("bg_color"),
        padding=body.get("padding", 10),
        opacity=body.get("opacity", 1.0),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "text_bbox": list(result["text_bbox"]),
        "font_size": result["font_size"],
    }


@router.post("/composite/product-shot")
async def composite_product_shot(body: Dict[str, Any] = Body(...)):
    """Create an AI product photography composite.

    Args:
        product_image: Base64 product image (RGBA preferred).
        scene_description: Prompt for scene generation.
        position: center, left, right, floor, shelf.
        scale: Product scale relative to scene.
        add_reflection: Add reflection below product.
    """
    from common_lib.modules.image_processing.services.compositing_service import product_shot as _prod_shot

    product_b64 = body.get("product_image")
    if not product_b64:
        raise HTTPException(400, detail="product_image (base64) is required")

    prod = _decode_image(product_b64)
    result = _prod_shot(
        product=prod,
        scene_description=body.get("scene_description", "marble countertop, soft studio lighting"),
        position=body.get("position", "center"),
        scale=body.get("scale", 0.5),
        add_reflection=body.get("add_reflection", True),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "scene_prompt": result["scene_prompt"],
        "position": result["position"],
        "output_size": list(result["output_size"]),
    }


# ── Style Transfer & Magic Filters (Doc 12) ──────────────────────


@router.post("/style/face")
async def style_face(body: Dict[str, Any] = Body(...)):
    """Apply face style from reference or prompt.

    Args:
        image: Base64 source image.
        reference: Optional base64 style reference face.
        style_prompt: Text description of desired face style.
        strength: Transfer strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import face_style_transfer

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    ref = _decode_image(body["reference"]) if body.get("reference") else None

    result = face_style_transfer(
        image=img,
        reference=ref,
        style_prompt=body.get("style_prompt", "natural skin tone"),
        strength=body.get("strength", 0.5),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "prompt": result["prompt"],
        "strength": result["strength"],
        "has_reference": result["has_reference"],
    }


@router.post("/style/hairstyle")
async def style_hairstyle(body: Dict[str, Any] = Body(...)):
    """Transfer hairstyle from reference or apply via prompt.

    Args:
        image: Base64 source image.
        reference: Optional base64 reference hair image.
        hairstyle_prompt: Text description of desired hairstyle.
        hair_mask: Optional base64 hair region mask.
        strength: Transfer strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import hairstyle_transfer

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    ref = _decode_image(body["reference"]) if body.get("reference") else None
    mask = _decode_image(body["hair_mask"]).getchannel("A") if body.get("hair_mask") else None

    result = hairstyle_transfer(
        image=img,
        reference=ref,
        hairstyle_prompt=body.get("hairstyle_prompt", "natural hair"),
        hair_mask=mask,
        strength=body.get("strength", 0.6),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "prompt": result["prompt"],
        "strength": result["strength"],
        "has_reference": result["has_reference"],
    }


@router.post("/style/art")
async def style_art(body: Dict[str, Any] = Body(...)):
    """Transform image to a specific artistic style.

    Styles: oil_painting, watercolor, pencil_sketch, ink_sketch, pastel,
            digital_illustration, impressionism, pop_art, art_nouveau,
            anime, ghibli, disney, comic_book, vintage, film_noir,
            cinematic, polaroid, ukiyoe

    Args:
        image: Base64 source image.
        style: Art style key.
        strength: Style strength 0.0-1.0.
        style_reference: Optional base64 reference image for IP-Adapter.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import art_style_transfer, ART_STYLES

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    style = body.get("style", "oil_painting")
    if style not in ART_STYLES:
        raise HTTPException(400, detail=f"Unknown style '{style}'. Available: {list(ART_STYLES.keys())}")

    img = _decode_image(image_b64)
    ref = _decode_image(body["style_reference"]) if body.get("style_reference") else None

    result = art_style_transfer(
        image=img,
        style=style,
        strength=body.get("strength", 0.7),
        style_reference=ref,
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "style": result["style"],
        "category": result["category"],
        "prompt": result["prompt"],
        "model": result["model"],
        "strength": result["strength"],
    }


@router.post("/style/art/stream")
async def style_art_stream(body: Dict[str, Any] = Body(...)):
    """Art style transfer with SSE progress streaming."""
    from common_lib.modules.image_processing.services.style_transfer_service import art_style_transfer, ART_STYLES

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    style = body.get("style", "oil_painting")
    if style not in ART_STYLES:
        raise HTTPException(400, detail=f"Unknown style '{style}'")
    img = _decode_image(image_b64)
    ref = _decode_image(body["style_reference"]) if body.get("style_reference") else None

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": f"Loading {style} model...", "phase": "Model"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 20, "message": "Analyzing composition...", "phase": "Analysis"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 50, "message": f"Applying {style} style...", "phase": "Processing"})
        result = art_style_transfer(image=img, style=style, strength=body.get("strength", 0.7), style_reference=ref)
        elapsed = time.time() - t0
        img_b64 = _encode_image(result["image"])
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"style": result["style"], "category": result["category"], "prompt": result["prompt"], "model": result["model"], "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Additional Streaming Endpoints ──────────────────────────


@router.post("/makeup/stream")
async def apply_makeup_stream(body: Dict[str, Any] = Body(...)):
    """Apply makeup with SSE progress streaming."""
    from common_lib.modules.image_processing.services.beauty_operations import makeup_transfer, makeup_preset

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    img = _decode_image(image_b64)
    preset = body.get("preset")
    region = body.get("region", "full")
    intensity = body.get("intensity", 0.7)

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Detecting face regions...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 15, "message": "Mapping makeup regions...", "phase": "Analysis"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 30, "message": "Applying makeup...", "phase": "Processing"})
        if preset:
            result = makeup_preset(img, preset_id=preset)
        else:
            reference = _decode_optional_image(body, "reference")
            result = makeup_transfer(img, reference, region=region, intensity=intensity)
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"region": region, "intensity": intensity, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/tattoo/place/stream")
async def place_tattoo_stream(body: Dict[str, Any] = Body(...)):
    """Place tattoo with SSE progress streaming."""
    from common_lib.modules.image_processing.services.skin_operations import tattoo_place

    image_b64 = body.get("image")
    tattoo_b64 = body.get("tattoo")
    if not image_b64 or not tattoo_b64:
        raise HTTPException(400, detail="image and tattoo (base64) are required")
    img = _decode_image(image_b64)
    tattoo = _decode_image(tattoo_b64)
    body_part = body.get("body_part", body.get("body_region", "arm"))

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Detecting body region...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 25, "message": f"Mapping to {body_part}...", "phase": "Mapping"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 50, "message": "Placing tattoo with perspective...", "phase": "Processing"})
        result = tattoo_place(img, tattoo, body_part=body_part, x=body.get("x"), y=body.get("y"))
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"body_part": body_part, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/style/face/stream")
async def style_face_stream(body: Dict[str, Any] = Body(...)):
    """Face style transfer with SSE progress streaming."""
    from common_lib.modules.image_processing.services.style_transfer_service import face_style_transfer

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    img = _decode_image(image_b64)
    style = body.get("style", "portrait")

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Detecting face...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 25, "message": "Analyzing style reference...", "phase": "Analysis"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 50, "message": "Applying face style...", "phase": "Processing"})
        result = face_style_transfer(image=img, style=style, strength=body.get("strength", 0.7))
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"style": style, "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/style/hairstyle/stream")
async def style_hairstyle_stream(body: Dict[str, Any] = Body(...)):
    """Hairstyle transfer with SSE progress streaming."""
    from common_lib.modules.image_processing.services.style_transfer_service import hairstyle_transfer

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    img = _decode_image(image_b64)
    ref = _decode_optional_image(body, "reference")

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Detecting face and hair region...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 30, "message": "Segmenting hair...", "phase": "Segmentation"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 55, "message": "Transferring hairstyle...", "phase": "Processing"})
        result = hairstyle_transfer(image=img, reference=ref, strength=body.get("strength", 0.7))
        elapsed = time.time() - t0
        img_b64 = _encode_image(result)
        yield _sse("progress", {"percent": 90, "message": "Encoding...", "phase": "Encode"})
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"image": img_b64, "metadata": {"duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/video/animate-portrait/stream")
async def video_animate_portrait_stream(body: Dict[str, Any] = Body(...)):
    """Animate portrait with SSE progress streaming."""
    from common_lib.modules.image_processing.services.video_animation_service import animate_portrait, _encode_frames_as_gif, _encode_frames_as_webp

    image_b64 = body.get("source_image")
    if not image_b64:
        raise HTTPException(400, detail="source_image (base64) is required")
    img = _decode_image(image_b64)
    driving = [_decode_image(f) for f in body.get("driving_video_frames", [])] or None

    async def event_generator():
        t0 = time.time()
        motion = body.get("motion_type", "subtle")
        fps = body.get("fps", 25.0)
        duration = body.get("duration_s", 3.0)
        total_frames = int(fps * duration)
        yield _sse("progress", {"percent": 5, "message": "Detecting face landmarks...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 15, "message": "Extracting motion vectors...", "phase": "Analysis"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 30, "message": f"Generating {total_frames} frames ({motion})...", "phase": "Generation"})
        result = animate_portrait(
            source_image=img, motion_type=motion,
            duration_s=duration, fps=fps,
            driving_video_frames=driving,
            motion_seed=body.get("motion_seed"),
        )
        elapsed = time.time() - t0
        yield _sse("progress", {"percent": 80, "message": "Encoding GIF/WebP...", "phase": "Encode"})
        gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
        webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"gif": gif_b64, "webp": webp_b64, "metadata": {"frame_count": result["frame_count"], "fps": result["fps"], "duration_s": result["duration_s"], "model": result["model"], "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/video/talking-avatar/stream")
async def video_talking_avatar_stream(body: Dict[str, Any] = Body(...)):
    """Talking avatar with SSE progress streaming."""
    from common_lib.modules.image_processing.services.video_animation_service import talking_head, _encode_frames_as_gif, _encode_frames_as_webp
    import base64 as _b64

    image_b64 = body.get("portrait_image")
    if not image_b64:
        raise HTTPException(400, detail="portrait_image (base64) is required")
    img = _decode_image(image_b64)
    audio = _b64.b64decode(body["audio_data"]) if body.get("audio_data") else None

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Analyzing portrait...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 15, "message": "Processing audio track...", "phase": "Audio"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 30, "message": "Generating talking head frames...", "phase": "Generation"})
        result = talking_head(
            portrait_image=img, audio_data=audio,
            expression_strength=body.get("expression_strength", 0.8),
            duration_s=body.get("duration_s", 5.0),
            fps=body.get("fps", 25.0),
            quality_refine=body.get("quality_refine", False),
        )
        elapsed = time.time() - t0
        yield _sse("progress", {"percent": 80, "message": "Encoding video...", "phase": "Encode"})
        gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
        webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"gif": gif_b64, "webp": webp_b64, "metadata": {"frame_count": result["frame_count"], "fps": result["fps"], "duration_s": result["duration_s"], "model": result["model"], "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/video/lip-sync/stream")
async def video_lip_sync_stream(body: Dict[str, Any] = Body(...)):
    """Lip sync with SSE progress streaming."""
    from common_lib.modules.image_processing.services.video_animation_service import lip_sync, _encode_frames_as_gif, _encode_frames_as_webp
    import base64 as _b64

    image_b64 = body.get("image") or body.get("source_image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    img = _decode_image(image_b64)
    audio = _b64.b64decode(body["audio_data"]) if body.get("audio_data") else None

    async def event_generator():
        t0 = time.time()
        yield _sse("progress", {"percent": 5, "message": "Detecting face...", "phase": "Detection"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 20, "message": "Analyzing audio phonemes...", "phase": "Audio"})
        await asyncio.sleep(0)
        yield _sse("progress", {"percent": 40, "message": "Syncing lip movements...", "phase": "Processing"})
        result = lip_sync(
            source_image=img, audio_data=audio,
            fps=body.get("fps", 25.0),
            quality=body.get("quality", "standard"),
        )
        elapsed = time.time() - t0
        yield _sse("progress", {"percent": 80, "message": "Encoding video...", "phase": "Encode"})
        gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
        webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])
        yield _sse("progress", {"percent": 100, "message": "Complete!", "phase": "Done", "elapsed": round(elapsed, 1)})
        yield _sse("result", {"gif": gif_b64, "webp": webp_b64, "metadata": {"frame_count": result["frame_count"], "fps": result["fps"], "duration_s": result["duration_s"], "duration_ms": round(elapsed * 1000)}})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/style/art-styles")
async def list_art_styles():
    """List all available art styles."""
    from common_lib.modules.image_processing.services.style_transfer_service import list_art_styles as _list
    return {"status": "success", "styles": _list()}


@router.post("/style/enhance")
async def style_enhance(body: Dict[str, Any] = Body(...)):
    """One-click intelligent photo correction.

    Args:
        image: Base64 source image.
        strength: Enhancement strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import auto_enhance

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = auto_enhance(image=img, strength=body.get("strength", 1.0))

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "adjustments": result["adjustments"],
        "strength": result["strength"],
    }


@router.post("/style/lut")
async def style_lut(body: Dict[str, Any] = Body(...)):
    """Apply a LUT preset for colour grading.

    Presets: cinematic_teal_orange, vintage_film, golden_hour, moody_blue,
             high_fashion, bw_editorial, warm_fade, cool_sharp

    Args:
        image: Base64 source image.
        lut_id: LUT preset ID.
        intensity: LUT strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import apply_lut, LUT_PRESETS

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    lut_id = body.get("lut_id", "cinematic_teal_orange")
    if lut_id not in LUT_PRESETS:
        raise HTTPException(400, detail=f"Unknown LUT '{lut_id}'. Available: {list(LUT_PRESETS.keys())}")

    img = _decode_image(image_b64)
    result = apply_lut(image=img, lut_id=lut_id, intensity=body.get("intensity", 0.85))

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "lut_id": result["lut_id"],
        "lut_name": result["lut_name"],
        "intensity": result["intensity"],
    }


@router.get("/style/luts")
async def list_luts():
    """List all available LUT presets."""
    from common_lib.modules.image_processing.services.style_transfer_service import list_luts as _list
    return {"status": "success", "luts": _list()}


@router.post("/style/instruct")
async def style_instruct(body: Dict[str, Any] = Body(...)):
    """Edit image based on text instruction.

    Args:
        image: Base64 source image.
        instruction: Text instruction (e.g. 'make it sunset', 'add fog', 'vintage look').
        strength: Edit strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import instruction_edit

    image_b64 = body.get("image")
    instruction = body.get("instruction")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")
    if not instruction:
        raise HTTPException(400, detail="instruction is required")

    img = _decode_image(image_b64)
    result = instruction_edit(image=img, instruction=instruction, strength=body.get("strength", 0.7))

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "instruction": result["instruction"],
        "applied_effects": result["applied_effects"],
        "strength": result["strength"],
    }


@router.post("/style/sky-replace")
async def style_sky_replace(body: Dict[str, Any] = Body(...)):
    """Replace the sky in an image.

    Args:
        image: Base64 source image.
        sky_prompt: Description of desired sky.
        sky_reference: Optional base64 sky reference image.
        blend_horizon: Blend zone height at horizon.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import sky_replace

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    ref = _decode_image(body["sky_reference"]) if body.get("sky_reference") else None

    result = sky_replace(
        image=img,
        sky_prompt=body.get("sky_prompt", "clear blue sky"),
        sky_reference=ref,
        blend_horizon=body.get("blend_horizon", 100),
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "sky_prompt": result["sky_prompt"],
        "has_reference": result["has_reference"],
    }


@router.post("/style/bokeh")
async def style_bokeh(body: Dict[str, Any] = Body(...)):
    """Apply depth-aware background blur (bokeh simulation).

    Args:
        image: Base64 source image.
        blur_strength: Maximum blur radius.
        subject_mask: Optional base64 mask of sharp subject.
        depth_map: Optional base64 depth map.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import background_blur

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    mask = _decode_image(body["subject_mask"]).getchannel("A") if body.get("subject_mask") else None
    depth = _decode_image(body["depth_map"]) if body.get("depth_map") else None

    result = background_blur(
        image=img,
        blur_strength=body.get("blur_strength", 10.0),
        subject_mask=mask,
        depth_map=depth,
    )

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "blur_strength": result["blur_strength"],
        "method": result["method"],
    }


@router.post("/style/weather")
async def style_weather(body: Dict[str, Any] = Body(...)):
    """Add weather effects (rain, snow, fog, storm, mist).

    Args:
        image: Base64 source image.
        effect_type: 'rain', 'snow', 'fog', 'storm', 'mist'.
        intensity: Effect strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import weather_effect, WEATHER_EFFECTS

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    effect_type = body.get("effect_type", "rain")
    if effect_type not in WEATHER_EFFECTS:
        raise HTTPException(400, detail=f"Unknown effect '{effect_type}'. Available: {list(WEATHER_EFFECTS.keys())}")

    img = _decode_image(image_b64)
    result = weather_effect(image=img, effect_type=effect_type, intensity=body.get("intensity", 0.5))

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "effect_type": result["effect_type"],
        "intensity": result["intensity"],
    }


@router.post("/style/time-of-day")
async def style_time_of_day(body: Dict[str, Any] = Body(...)):
    """Transform time of day in an image.

    Args:
        image: Base64 source image.
        target_time: 'golden_hour', 'blue_hour', 'noon', 'night', 'overcast', 'sunset', 'sunrise'.
        strength: Transform strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import time_of_day, TIME_OF_DAY_PRESETS

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    target = body.get("target_time", "golden_hour")
    if target not in TIME_OF_DAY_PRESETS:
        raise HTTPException(400, detail=f"Unknown time '{target}'. Available: {list(TIME_OF_DAY_PRESETS.keys())}")

    img = _decode_image(image_b64)
    result = time_of_day(image=img, target_time=target, strength=body.get("strength", 0.7))

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "target_time": result["target_time"],
        "strength": result["strength"],
    }


@router.post("/style/season")
async def style_season(body: Dict[str, Any] = Body(...)):
    """Transform season in an image.

    Args:
        image: Base64 source image.
        target_season: 'spring', 'summer', 'autumn', 'winter'.
        strength: Transform strength 0.0-1.0.
    """
    from common_lib.modules.image_processing.services.style_transfer_service import season_transform, SEASON_PRESETS

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    target = body.get("target_season", "autumn")
    if target not in SEASON_PRESETS:
        raise HTTPException(400, detail=f"Unknown season '{target}'. Available: {list(SEASON_PRESETS.keys())}")

    img = _decode_image(image_b64)
    result = season_transform(image=img, target_season=target, strength=body.get("strength", 0.7))

    return {
        "status": "success",
        "image": _encode_image(result["image"]),
        "target_season": result["target_season"],
        "strength": result["strength"],
    }


# ── Video Animation Pipeline (Doc 15) ─────────────────────────────


@router.post("/video/animate-portrait")
async def video_animate_portrait(body: Dict[str, Any] = Body(...)):
    """Animate a still portrait photo with facial motion.

    Args:
        source_image: Base64 portrait photo.
        motion_type: 'subtle', 'talking', 'expressive'.
        duration_s: Output duration in seconds.
        fps: Frames per second.
        driving_video_frames: Optional list of base64 driving video frames.
        motion_seed: Random seed for reproducibility.
    """
    from common_lib.modules.image_processing.services.video_animation_service import animate_portrait

    image_b64 = body.get("source_image")
    if not image_b64:
        raise HTTPException(400, detail="source_image (base64) is required")

    img = _decode_image(image_b64)
    driving = [_decode_image(f) for f in body.get("driving_video_frames", [])] or None

    result = animate_portrait(
        source_image=img,
        motion_type=body.get("motion_type", "subtle"),
        duration_s=body.get("duration_s", 3.0),
        fps=body.get("fps", 25.0),
        driving_video_frames=driving,
        motion_seed=body.get("motion_seed"),
    )

    # Encode frames
    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "width": result["width"],
        "height": result["height"],
        "motion_type": result["motion_type"],
        "model": result["model"],
    }


@router.post("/video/talking-avatar")
async def video_talking_avatar(body: Dict[str, Any] = Body(...)):
    """Generate a talking head video from portrait + audio.

    Args:
        portrait_image: Base64 portrait photo.
        audio_data: Optional base64-encoded audio.
        expression_strength: How expressive (0.0-1.0).
        duration_s: Output duration.
        fps: Frames per second.
        quality_refine: Apply per-frame face restoration.
    """
    from common_lib.modules.image_processing.services.video_animation_service import talking_head
    import base64 as _b64

    image_b64 = body.get("portrait_image")
    if not image_b64:
        raise HTTPException(400, detail="portrait_image (base64) is required")

    img = _decode_image(image_b64)
    audio = _b64.b64decode(body["audio_data"]) if body.get("audio_data") else None

    result = talking_head(
        portrait=img,
        audio_data=audio,
        expression_strength=body.get("expression_strength", 0.8),
        duration_s=body.get("duration_s", 5.0),
        fps=body.get("fps", 25.0),
        quality_refine=body.get("quality_refine", False),
    )

    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "model": result["model"],
        "audio_analyzed": result["audio_analyzed"],
    }


@router.post("/video/lip-sync")
async def video_lip_sync(body: Dict[str, Any] = Body(...)):
    """Sync lip movements to audio.

    Args:
        video_frames: Optional list of base64 video frames.
        source_image: Base64 source portrait (used if no video_frames).
        audio_data: Base64 audio for lip sync.
        quality: 'fast' (Wav2Lip) or 'standard' (MuseTalk).
        duration_s: Duration if generating from source_image.
        fps: Frame rate.
    """
    from common_lib.modules.image_processing.services.video_animation_service import lip_sync
    import base64 as _b64

    frames = [_decode_image(f) for f in body.get("video_frames", [])] or None
    source = _decode_image(body["source_image"]) if body.get("source_image") else None
    audio = _b64.b64decode(body["audio_data"]) if body.get("audio_data") else None

    if not frames and not source:
        raise HTTPException(400, detail="Either video_frames or source_image is required")

    result = lip_sync(
        video_frames=frames,
        source_image=source,
        audio_data=audio,
        quality=body.get("quality", "standard"),
        duration_s=body.get("duration_s", 5.0),
        fps=body.get("fps", 25.0),
    )

    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "quality": result["quality"],
        "model": result["model"],
    }


@router.post("/video/generate")
async def video_generate(body: Dict[str, Any] = Body(...)):
    """Generate video from text prompt.

    Args:
        prompt: Text description of desired video.
        style: Optional style modifier.
        duration_s: Duration in seconds.
        resolution: '480p' or '720p'.
        tier: 'fast', 'standard', 'premium'.
        seed: Random seed.
        fps: Frames per second.
    """
    from common_lib.modules.image_processing.services.video_animation_service import text_to_video

    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(400, detail="prompt is required")

    result = text_to_video(
        prompt=prompt,
        style=body.get("style"),
        duration_s=body.get("duration_s", 3.0),
        resolution=body.get("resolution", "480p"),
        tier=body.get("tier", "standard"),
        seed=body.get("seed"),
        fps=body.get("fps", 24.0),
    )

    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "width": result["width"],
        "height": result["height"],
        "prompt": result["prompt"],
        "tier": result["tier"],
        "model": result["model"],
    }


@router.post("/video/animate-image")
async def video_animate_image(body: Dict[str, Any] = Body(...)):
    """Animate a still image into a video.

    Args:
        image: Base64 source image.
        motion_prompt: Optional text describing desired motion.
        duration_s: Duration in seconds.
        camera_motion: 'static', 'pan', 'zoom', 'orbit'.
        tier: 'fast', 'standard', 'premium'.
        fps: Frames per second.
    """
    from common_lib.modules.image_processing.services.video_animation_service import image_to_video

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = image_to_video(
        image=img,
        motion_prompt=body.get("motion_prompt"),
        duration_s=body.get("duration_s", 3.0),
        camera_motion=body.get("camera_motion", "static"),
        tier=body.get("tier", "standard"),
        fps=body.get("fps", 24.0),
    )

    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "camera_motion": result["camera_motion"],
        "tier": result["tier"],
        "model": result["model"],
    }


@router.post("/video/style-transfer")
async def video_style_transfer(body: Dict[str, Any] = Body(...)):
    """Apply consistent artistic style to video frames.

    Args:
        video_frames: List of base64 video frames.
        style_name: Style to apply.
        style_reference: Optional base64 reference image.
        consistency_strength: Temporal consistency 0.0-1.0.
        fps: Frame rate.
    """
    from common_lib.modules.image_processing.services.video_animation_service import video_style_transfer as _vst

    frames_b64 = body.get("video_frames", [])
    if not frames_b64:
        raise HTTPException(400, detail="video_frames (list of base64 images) is required")

    frames = [_decode_image(f) for f in frames_b64]
    ref = _decode_image(body["style_reference"]) if body.get("style_reference") else None

    result = _vst(
        video_frames=frames,
        style_name=body.get("style_name", "vintage"),
        style_reference=ref,
        consistency_strength=body.get("consistency_strength", 0.9),
        fps=body.get("fps", 25.0),
    )

    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "style": result["style"],
        "consistency": result["consistency"],
        "model": result["model"],
    }


@router.post("/video/expression-retarget")
async def video_expression_retarget(body: Dict[str, Any] = Body(...)):
    """Retarget facial expressions across video frames.

    Args:
        video_frames: List of base64 video frames.
        expression_delta: Dict of expression deltas (smile, eyebrow, eyes_open, mouth_open, head_tilt).
        fps: Frame rate.
    """
    from common_lib.modules.image_processing.services.video_animation_service import expression_retarget

    frames_b64 = body.get("video_frames", [])
    if not frames_b64:
        raise HTTPException(400, detail="video_frames (list of base64 images) is required")

    frames = [_decode_image(f) for f in frames_b64]

    result = expression_retarget(
        frames=frames,
        expression_delta=body.get("expression_delta", {}),
        fps=body.get("fps", 25.0),
    )

    from common_lib.modules.image_processing.services.video_animation_service import _encode_frames_as_gif, _encode_frames_as_webp
    gif_b64 = _encode_frames_as_gif(result["frames"], result["fps"])
    webp_b64 = _encode_frames_as_webp(result["frames"], result["fps"])

    return {
        "status": "success",
        "gif": gif_b64,
        "webp": webp_b64,
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "expression_delta": result["expression_delta"],
    }


@router.get("/video/routing")
async def video_model_routing():
    """Get the full model routing table for video operations."""
    from common_lib.modules.image_processing.services.video_animation_service import get_model_routing
    return {"status": "success", **get_model_routing()}


# ── Agentic Workflows (Doc 17) ────────────────────────────────────


@router.post("/agent/run")
async def agent_run(body: Dict[str, Any] = Body(...)):
    """Execute a full agentic pipeline: plan → execute → critique → refine.

    Per Doc 17 §3 — autonomous creative pipeline.

    Args:
        user_request: Creative brief (e.g. 'restore and enhance this portrait').
        image: Base64 input image.
        task_type: portrait, fashion, landscape, creature, product, custom.
        reference_image: Optional base64 reference image.
        custom_steps: Optional list of {name, tool, params, output_key}.
        max_iterations: Max critique-refine loops (default 3).
        quality_threshold: Min quality score (default 0.85).
    """
    from common_lib.modules.image_processing.services.agentic_workflow_service import (
        execute_pipeline, TaskType,
    )

    user_request = body.get("user_request", "")
    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    task_type_str = body.get("task_type", "custom")
    try:
        task_type = TaskType(task_type_str)
    except ValueError:
        task_type = TaskType.CUSTOM

    state = execute_pipeline(
        user_request=user_request,
        input_image_b64=image_b64,
        task_type=task_type,
        reference_image_b64=body.get("reference_image"),
        custom_steps=body.get("custom_steps"),
        max_iterations=body.get("max_iterations", 3),
        quality_threshold=body.get("quality_threshold", 0.85),
    )

    return {
        "status": "success",
        "run_id": state.run_id,
        "phase": state.phase.value,
        "final_image": state.final_image,
        "quality_report": state.quality_report.to_dict() if state.quality_report else None,
        "iterations": state.iteration_count,
        "trace_summary": {
            "steps_planned": len(state.plan.steps) if state.plan else 0,
            "steps_executed": len([t for t in state.trace if "tool" in t]),
            "elapsed_s": round(state.completed_at - state.started_at, 2) if state.completed_at else 0,
        },
    }


@router.post("/agent/plan")
async def agent_plan(body: Dict[str, Any] = Body(...)):
    """Plan an agentic pipeline without executing it.

    Args:
        user_request: Creative brief.
        task_type: Task type.
        custom_steps: Optional custom pipeline steps.
    """
    from common_lib.modules.image_processing.services.agentic_workflow_service import (
        plan_pipeline, TaskType,
    )

    task_type_str = body.get("task_type", "custom")
    try:
        task_type = TaskType(task_type_str)
    except ValueError:
        task_type = TaskType.CUSTOM

    plan = plan_pipeline(
        user_request=body.get("user_request", ""),
        task_type=task_type,
        custom_steps=body.get("custom_steps"),
    )

    return {
        "status": "success",
        "plan": plan.to_dict(),
    }


@router.post("/agent/critique")
async def agent_critique(body: Dict[str, Any] = Body(...)):
    """Assess image quality without running a full pipeline.

    Args:
        image: Base64 image to assess.
        reference_image: Optional base64 reference.
        quality_threshold: Min score (default 0.85).
    """
    from common_lib.modules.image_processing.services.agentic_workflow_service import assess_quality

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    report = assess_quality(
        image_b64=image_b64,
        reference_b64=body.get("reference_image"),
        quality_threshold=body.get("quality_threshold", 0.85),
    )

    return {
        "status": "success",
        "quality_report": report.to_dict(),
    }


@router.get("/agent/tools")
async def agent_tools():
    """List all tools available to agents."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import ToolRegistry
    registry = ToolRegistry()
    return {
        "status": "success",
        "tools": registry.list_tools(),
        "categories": registry.list_by_category(),
    }


@router.get("/agent/templates")
async def agent_templates():
    """List all predefined pipeline templates."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import list_pipeline_templates
    return {
        "status": "success",
        "templates": list_pipeline_templates(),
    }


@router.get("/agent/task-types")
async def agent_task_types():
    """List all supported task types."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import TaskType
    return {
        "status": "success",
        "task_types": [t.value for t in TaskType],
    }


@router.post("/agent/run/stream")
async def agent_run_stream(body: Dict[str, Any] = Body(...)):
    """Execute agentic pipeline with SSE streaming for real-time progress."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import (
        execute_pipeline, AgentPhase,
    )

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, "image required")

    user_request = body.get("request", "enhance this image")
    task_type = body.get("task_type", "custom")
    ref = body.get("reference")
    max_iterations = body.get("max_iterations", 3)
    threshold = body.get("quality_threshold", 0.85)

    async def stream_events():
        try:
            yield _sse("started", {"request": user_request[:200], "task_type": task_type})
            state = execute_pipeline(
                user_request, image_b64, task_type=task_type,
                reference_image_b64=ref, max_iterations=max_iterations,
                quality_threshold=threshold,
            )
            # Stream trace events
            for entry in state.trace:
                yield _sse("step", entry)
            # Final result
            yield _sse("complete", {
                "status": state.phase.value,
                "quality": state.quality_report.iqa_score if state.quality_report else None,
                "iterations": state.iteration_count,
                "duration_ms": round((state.completed_at - state.started_at) * 1000) if state.completed_at else 0,
                "has_final_image": bool(state.final_image),
            })
        except Exception as exc:
            yield _sse("error", {"error": str(exc)})

    return StreamingResponse(stream_events(), media_type="text/event-stream")


@router.post("/agent/run/parallel")
async def agent_run_parallel(body: Dict[str, Any] = Body(...)):
    """Execute agentic pipeline with parallel step execution."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import (
        execute_pipeline_parallel, TaskType,
    )

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, "image required")

    user_request = body.get("request", "enhance this image")
    task_type_str = body.get("task_type", "custom")
    ref = body.get("reference")
    max_iterations = body.get("max_iterations", 3)
    threshold = body.get("quality_threshold", 0.85)
    max_workers = body.get("max_workers", 4)
    parallel_groups = body.get("parallel_groups")

    try:
        tt = TaskType(task_type_str)
    except ValueError:
        tt = TaskType.CUSTOM

    state = execute_pipeline_parallel(
        user_request, image_b64, task_type=tt,
        reference_image_b64=ref, parallel_groups=parallel_groups,
        max_iterations=max_iterations, quality_threshold=threshold,
        max_workers=max_workers,
    )

    from common_lib.modules.image_processing.services.agentic_workflow_service import get_trace_summary
    return {
        "status": "success",
        "trace": get_trace_summary(state),
        "quality": state.quality_report.to_dict() if state.quality_report else None,
    }


@router.post("/agent/checkpoint/save")
async def agent_checkpoint_save(body: Dict[str, Any] = Body(...)):
    """Save agent state checkpoint for resume later."""
    import json as _json
    import os
    checkpoint_dir = os.path.join(os.path.expanduser("~"), ".platform", "agent_checkpoints")
    os.makedirs(checkpoint_dir, exist_ok=True)

    run_id = body.get("run_id", str(__import__("uuid").uuid4())[:12])
    state_data = body.get("state", {})
    filepath = os.path.join(checkpoint_dir, f"checkpoint_{run_id}.json")
    with open(filepath, "w") as f:
        _json.dump({"run_id": run_id, "phase": state_data.get("phase", "unknown"),
                     "current_image": state_data.get("current_image"),
                     "iteration": state_data.get("iteration", 0),
                     "trace": state_data.get("trace", [])}, f)
    return {"status": "success", "run_id": run_id, "filepath": filepath}


@router.get("/agent/checkpoint/{run_id}")
async def agent_checkpoint_load(run_id: str):
    """Load an agent state checkpoint."""
    import json as _json
    import os
    checkpoint_dir = os.path.join(os.path.expanduser("~"), ".platform", "agent_checkpoints")
    filepath = os.path.join(checkpoint_dir, f"checkpoint_{run_id}.json")
    if not os.path.exists(filepath):
        raise HTTPException(404, f"Checkpoint '{run_id}' not found")
    with open(filepath) as f:
        data = _json.load(f)
    return {"status": "success", "checkpoint": data}


@router.post("/agent/comfyui/workflow")
async def agent_comfyui_workflow(body: Dict[str, Any] = Body(...)):
    """Build a ComfyUI workflow JSON from a pipeline plan."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import (
        build_comfyui_workflow, TaskType,
    )

    user_request = body.get("request", "enhance this image")
    task_type_str = body.get("task_type", "custom")
    try:
        tt = TaskType(task_type_str)
    except ValueError:
        tt = TaskType.CUSTOM

    workflow = build_comfyui_workflow(user_request, tt)
    return {"status": "success", "workflow": workflow, "node_count": len(workflow)}


@router.post("/agent/critique/batch")
async def agent_critique_batch(body: Dict[str, Any] = Body(...)):
    """Assess quality of multiple images at once."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import assess_quality

    images = body.get("images", [])
    ref = body.get("reference")
    threshold = body.get("quality_threshold", 0.85)
    results = []
    for img_b64 in images:
        report = assess_quality(img_b64, ref, threshold)
        results.append(report.to_dict())
    return {"status": "success", "results": results, "total": len(results)}


@router.get("/agent/history")
async def agent_history(limit: int = 20):
    """List recent agent execution runs."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import list_agent_runs
    return {"status": "success", "runs": list_agent_runs(limit)}


@router.get("/agent/approval/pending")
async def agent_approval_pending():
    """List pending approval gates."""
    from common_lib.modules.image_processing.services.agentic_workflow_service import ApprovalGate
    gate = ApprovalGate()
    return {"status": "success", "pending": gate.get_pending()}


# ── 3D Generation Pipeline (Doc 16) ──────────────────────────────


@router.post("/3d/generate-from-image")
async def generate_3d_from_image(body: Dict[str, Any] = Body(...)):
    """Generate 3D model from a single image.

    Args:
        image: Base64 source image.
        output_format: 'glb', '3dgs', 'radiance'.
        quality: 'fast', 'standard', 'premium'.
        resolution: Mesh grid resolution.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import generate_3d_from_image as _gen3d

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = _gen3d(
        image=img,
        output_format=body.get("output_format", "glb"),
        quality=body.get("quality", "standard"),
        resolution=body.get("resolution", 64),
    )

    return {
        "status": "success",
        "mesh": result["mesh"],
        "vertex_count": result["vertex_count"],
        "face_count": result["face_count"],
        "output_format": result["output_format"],
        "normals_preview": result["normals_preview"],
        "model": result["model"],
    }


@router.post("/3d/generate-from-text")
async def generate_3d_from_text(body: Dict[str, Any] = Body(...)):
    """Generate 3D model from text description.

    Args:
        prompt: Text description.
        style: 'realistic', 'cartoon', 'low_poly'.
        output_format: 'glb', '3dgs'.
        resolution: Mesh resolution.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import generate_3d_from_text as _gen3d_text

    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(400, detail="prompt is required")

    result = _gen3d_text(
        prompt=prompt,
        style=body.get("style", "realistic"),
        output_format=body.get("output_format", "glb"),
        resolution=body.get("resolution", 32),
    )

    return {
        "status": "success",
        "mesh": result["mesh"],
        "vertex_count": result["vertex_count"],
        "face_count": result["face_count"],
        "prompt": result["prompt"],
        "style": result["style"],
        "model": result["model"],
    }


@router.post("/3d/depth-estimate")
async def depth_estimate(body: Dict[str, Any] = Body(...)):
    """Estimate depth from single image.

    Args:
        image: Base64 source image.
        model: 'relative' or 'metric'.
        size: 'small', 'base', 'large'.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import estimate_depth

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = estimate_depth(
        image=img,
        model=body.get("model", "relative"),
        size=body.get("size", "large"),
    )

    return {
        "status": "success",
        "depth_heatmap": result["depth_heatmap"],
        "depth_min": result["depth_min"],
        "depth_max": result["depth_max"],
        "depth_mean": result["depth_mean"],
        "width": result["width"],
        "height": result["height"],
        "model": result["model"],
    }


@router.post("/3d/surface-normals")
async def surface_normals(body: Dict[str, Any] = Body(...)):
    """Estimate surface normals from image.

    Args:
        image: Base64 source image.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import estimate_surface_normals

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = estimate_surface_normals(image=img)

    return {
        "status": "success",
        "normals_image": result["normals_image"],
        "width": result["width"],
        "height": result["height"],
        "model": result["model"],
    }


@router.post("/3d/novel-views")
async def novel_views(body: Dict[str, Any] = Body(...)):
    """Generate novel views at specified angles.

    Args:
        image: Base64 source image.
        angles: List of angles in degrees.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import generate_novel_views

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = generate_novel_views(
        image=img,
        angles=body.get("angles"),
    )

    return {
        "status": "success",
        "views": result["views"],
        "count": result["count"],
        "angles": result["angles"],
        "model": result["model"],
    }


@router.post("/3d/turntable")
async def turntable(body: Dict[str, Any] = Body(...)):
    """Generate 360-degree turntable animation.

    Args:
        image: Base64 source image.
        frames: Number of frames.
        format: 'gif' or 'webp'.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import generate_turntable

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = generate_turntable(
        image=img,
        frames=body.get("frames", 36),
        output_format=body.get("format", "gif"),
    )

    return {
        "status": "success",
        "animated": result["animated"],
        "frame_count": result["frame_count"],
        "fps": result["fps"],
        "duration_s": result["duration_s"],
        "output_format": result["output_format"],
        "mesh": result["mesh"],
        "vertex_count": result["vertex_count"],
    }


@router.post("/3d/body-reconstruct")
async def body_reconstruct(body: Dict[str, Any] = Body(...)):
    """Reconstruct 3D human body from image.

    Args:
        image: Base64 source image.
        model: 'standard' or 'premium'.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import reconstruct_3d_body

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = reconstruct_3d_body(image=img, model=body.get("model", "standard"))

    return {
        "status": "success",
        "smpl_params": result["smpl_params"],
        "bbox": result["bbox"],
        "center": result["center"],
        "body_height_ratio": result["body_height_ratio"],
        "model": result["model"],
        "vertex_count": result["vertex_count"],
    }


@router.post("/3d/face-reconstruct")
async def face_reconstruct_3d(body: Dict[str, Any] = Body(...)):
    """Reconstruct 3D face mesh from image.

    Args:
        image: Base64 source image.
        face_bbox: Optional [x1, y1, x2, y2] face bounding box.
    """
    from common_lib.modules.image_processing.services.three_d_generation_service import reconstruct_3d_face

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) is required")

    img = _decode_image(image_b64)
    result = reconstruct_3d_face(image=img, face_bbox=body.get("face_bbox"))

    return {
        "status": "success",
        "mesh": result["mesh"],
        "model": result["model"],
        "vertex_count": result["vertex_count"],
    }


@router.get("/3d/models")
async def list_3d_models():
    """List all 3D generation models and capabilities."""
    from common_lib.modules.image_processing.services.three_d_generation_service import list_3d_models as _list
    return {"status": "success", **_list()}


# ── LoRA Registry (Doc 13) ────────────────────────────────────────


@router.get("/lora/list")
async def list_loras(
    category: Optional[str] = Query(None, description="Filter by category"),
    task: Optional[str] = Query(None, description="Filter by task"),
):
    """List available LoRA models with metadata."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        LoRARegistry, seed_default_loras,
    )
    registry = LoRARegistry()
    if not registry.list_all():
        seed_default_loras(registry)
    # Build search query from params
    query_parts = []
    if category:
        query_parts.append(category)
    if task:
        query_parts.append(task)
    query = " ".join(query_parts)
    results = registry.search(query=query, category=category or "")
    loras = []
    for e in results:
        d = {
            'lora_id': e.lora_id, 'name': e.name, 'category': e.category,
            'base_model': e.base_model, 'tags': e.tags,
            'trigger_words': e.trigger_words, 'recommended_weight': e.recommended_weight,
            'description': e.description,
        }
        loras.append(d)
    categories = registry.list_categories()
    return {"status": "success", "loras": loras, "total": len(loras), "categories": categories, "base_models": registry.list_base_models()}


@router.post("/lora/download")
async def download_lora(data: Dict[str, Any]):
    """Download a LoRA model from HuggingFace or CivitAI with progress."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        download_lora as _download, LoRARegistry, seed_default_loras,
    )
    lora_id = data.get("lora_id")
    if not lora_id:
        return {"status": "error", "error": "lora_id required"}
    registry = LoRARegistry()
    if not registry.list_all():
        seed_default_loras(registry)
    destination = data.get("destination")
    source = data.get("source")
    return {"status": "success", **_download(registry, lora_id=lora_id, destination=destination, source=source)}


@router.post("/lora/download/stream")
async def download_lora_stream(data: Dict[str, Any]):
    """Download a LoRA with SSE streaming progress."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        download_lora, LoRARegistry, seed_default_loras,
    )
    lora_id = data.get("lora_id")
    if not lora_id:
        raise HTTPException(400, "lora_id required")
    registry = LoRARegistry()
    if not registry.list_all():
        seed_default_loras(registry)

    async def event_generator():
        yield _sse("progress", {"percent": 0, "message": "Preparing download...", "phase": "Init"})
        result = download_lora(registry, lora_id=lora_id, destination=data.get("destination"), source=data.get("source"))
        if result.get("status") == "exists":
            yield _sse("progress", {"percent": 100, "message": "Already downloaded", "phase": "Done"})
            yield _sse("result", result)
        elif result.get("status") == "success":
            yield _sse("progress", {"percent": 100, "message": f"Downloaded {result.get('size_bytes', 0)} bytes", "phase": "Done"})
            yield _sse("result", result)
        else:
            yield _sse("error", {"message": result.get("message", "Download failed")})

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/lora/apply")
async def apply_lora(data: Dict[str, Any]):
    """Apply a LoRA to an image using SD WebUI API."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        apply_lora as _apply,
    )
    image_b64 = data.get("image")
    lora_id = data.get("lora_id")
    if not lora_id:
        return {"status": "error", "error": "lora_id required"}
    from common_lib.modules.image_processing.services.lora_registry_service import (
        LoRARegistry, seed_default_loras, compose_loras, apply_lora,
    )
    registry = LoRARegistry()
    if not registry.list_all():
        seed_default_loras(registry)
    weight = data.get("weight", 0.8)
    prompt = data.get("prompt", "best quality")
    negative = data.get("negative_prompt", "worst quality")
    # Build a single-LoRA composition
    composition = compose_loras(registry, lora_ids=[lora_id], weights=[weight])
    result = _apply(composition, prompt=prompt, negative_prompt=negative)
    return {"status": "success", "metadata": result}


@router.get("/lora/compositions")
async def list_lora_compositions():
    """List preset LoRA compositions (multi-LoRA stacks)."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        list_composition_templates,
    )
    templates = list_composition_templates()
    return {"status": "success", "compositions": templates, "total": len(templates)}


@router.post("/lora/compose")
async def compose_loras(data: Dict[str, Any]):
    """Apply multiple LoRAs with balanced weights."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        LoRARegistry, seed_default_loras, apply_lora as _apply_fn,
    )
    loras = data.get("loras", [])
    if not loras:
        return {"status": "error", "error": "loras list required"}
    from common_lib.modules.image_processing.services.lora_registry_service import (
        LoRARegistry, seed_default_loras, compose_loras,
    )
    registry = LoRARegistry()
    if not registry.list_all():
        seed_default_loras(registry)
    lora_ids = [l.get("lora_id", "") if isinstance(l, dict) else str(l) for l in loras]
    prompt = data.get("prompt", "best quality")
    negative = data.get("negative_prompt", "worst quality")
    composition = compose_loras(registry, lora_ids=lora_ids)
    result = _apply_fn(composition, prompt=prompt, negative_prompt=negative)
    return {"status": "success", "metadata": result}


@router.get("/lora/conflicts")
async def detect_lora_conflicts():
    """Detect potential conflicts between installed LoRAs."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        detect_conflicts as _detect, LoRARegistry,
    )
    registry = LoRARegistry()
    all_ids = [e.lora_id for e in registry.list_all()]
    conflicts = _detect(registry, all_ids)
    return {"status": "success", "conflicts": conflicts, "total": len(conflicts)}


@router.post("/lora/recommend")
async def recommend_loras(data: Dict[str, Any]):
    """Recommend LoRAs for a task based on quality scores and compatibility."""
    from common_lib.modules.image_processing.services.lora_registry_service import (
        LoRARegistry, seed_default_loras,
    )
    task = data.get("task")
    if not task:
        return {"status": "error", "error": "task required"}
    registry = LoRARegistry()
    if not registry.list_all():
        seed_default_loras(registry)
    top_k = data.get("top_k", 5)
    matches = registry.search(query=task)
    if not matches:
        matches = registry.list_all()[:top_k]
    recs = [{'lora_id': e.lora_id, 'name': e.name, 'weight': e.recommended_weight,
             'category': e.category, 'base_model': e.base_model,
             'description': e.description}
            for e in matches[:top_k]]
    return {"status": "success", "task": task, "recommendations": recs}


# ── Advanced Control Techniques (Doc 18) ─────────────────────────


@router.post("/control/preprocess")
async def control_preprocess(body: Dict[str, Any] = Body(...)):
    """Preprocess image to extract control signal (canny, depth, pose, etc.)."""
    from common_lib.modules.image_processing.services.advanced_control_service import preprocess_control, PREPROCESSORS

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) required")
    control_type = body.get("control_type", "canny")
    if control_type not in PREPROCESSORS:
        raise HTTPException(400, detail=f"Unknown type '{control_type}'. Available: {list(PREPROCESSORS.keys())}")

    img = _decode_image(image_b64)
    kwargs = {k: v for k, v in body.items() if k not in ("image", "control_type") and isinstance(v, (int, float, str, bool))}
    result = preprocess_control(img, control_type, **kwargs)
    return {"status": "success", "image": _encode_image(result), "control_type": control_type}


@router.get("/control/preprocessors")
async def control_list_preprocessors():
    """List all available ControlNet preprocessors."""
    from common_lib.modules.image_processing.services.advanced_control_service import PREPROCESSORS
    return {"status": "success", "preprocessors": list(PREPROCESSORS.keys())}


@router.post("/control/generate")
async def control_generate(body: Dict[str, Any] = Body(...)):
    """ControlNet-guided image generation."""
    from common_lib.modules.image_processing.services.advanced_control_service import controlnet_generate

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) required")
    img = _decode_image(image_b64)
    result = controlnet_generate(
        image=img,
        prompt=body.get("prompt", ""),
        control_type=body.get("control_type", "canny"),
        negative_prompt=body.get("negative_prompt", ""),
        strength=body.get("strength", 0.7),
        guidance_scale=body.get("guidance_scale", 7.5),
        num_steps=body.get("num_steps", 30),
        seed=body.get("seed"),
        control_weight=body.get("control_weight", 0.8),
    )
    return {"status": "success", "image": _encode_image(result["image"]),
            "control_image": _encode_image(result["control_image"]),
            "metadata": {k: v for k, v in result.items() if k not in ("image", "control_image")}}


@router.post("/control/ip-adapter")
async def control_ip_adapter(body: Dict[str, Any] = Body(...)):
    """IP-Adapter conditioning (style, face identity, composition)."""
    from common_lib.modules.image_processing.services.advanced_control_service import ip_adapter_condition

    image_b64 = body.get("image")
    ref_b64 = body.get("reference")
    if not image_b64 or not ref_b64:
        raise HTTPException(400, detail="image and reference (base64) required")

    img = _decode_image(image_b64)
    ref = _decode_image(ref_b64)
    result = ip_adapter_condition(
        image=img, reference=ref,
        variant=body.get("variant", "plus"),
        weight=body.get("weight", 0.8),
        is_faceid=body.get("is_faceid", False),
        prompt=body.get("prompt", ""),
    )
    return {"status": "success", "image": _encode_image(result["image"]), "metadata": {k: v for k, v in result.items() if k != "image"}}


@router.post("/control/reference-only")
async def control_reference_only(body: Dict[str, Any] = Body(...)):
    """Reference-only generation (attention coupling, no IP-Adapter)."""
    from common_lib.modules.image_processing.services.advanced_control_service import reference_only

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) required")
    img = _decode_image(image_b64)
    result = reference_only(
        image=img,
        prompt=body.get("prompt", ""),
        style_strength=body.get("style_strength", 0.7),
        content_strength=body.get("content_strength", 0.5),
    )
    return {"status": "success", "image": _encode_image(result["image"]), "metadata": {k: v for k, v in result.items() if k != "image"}}


@router.get("/control/recipes")
async def control_recipes():
    """List all multi-conditioning recipes."""
    from common_lib.modules.image_processing.services.advanced_control_service import get_recipes
    return {"status": "success", "recipes": get_recipes()}


@router.post("/control/apply-recipe")
async def control_apply_recipe(body: Dict[str, Any] = Body(...)):
    """Apply a multi-conditioning recipe."""
    from common_lib.modules.image_processing.services.advanced_control_service import apply_recipe

    image_b64 = body.get("image")
    if not image_b64:
        raise HTTPException(400, detail="image (base64) required")
    img = _decode_image(image_b64)
    ref = _decode_image(body["reference"]) if body.get("reference") else None
    result = apply_recipe(
        image=img, recipe_name=body.get("recipe", "portrait"),
        prompt=body.get("prompt", ""), reference=ref,
    )
    if "error" in result:
        raise HTTPException(400, detail=result["error"])
    return {"status": "success", "image": _encode_image(result["image"]),
            "recipe": result["recipe"], "model": result["model"],
            "controls_applied": result["controls_applied"],
            "duration_ms": result["duration_ms"]}


@router.get("/control/sampler-guide")
async def control_sampler_guide():
    """Get sampler/scheduler optimization guide."""
    from common_lib.modules.image_processing.services.advanced_control_service import get_sampler_guide
    return {"status": "success", **get_sampler_guide()}


@router.post("/control/recommend")
async def control_recommend(body: Dict[str, Any] = Body(...)):
    """Recommend sampler, CFG, and steps for task/quality/model."""
    from common_lib.modules.image_processing.services.advanced_control_service import recommend_settings
    result = recommend_settings(
        task=body.get("task", "portrait"),
        quality=body.get("quality", "standard"),
        model=body.get("model", "sdxl"),
    )
    return {"status": "success", **result}


@router.post("/control/prompt-weight")
async def control_prompt_weight(body: Dict[str, Any] = Body(...)):
    """Apply prompt weighting syntax."""
    from common_lib.modules.image_processing.services.advanced_control_service import apply_prompt_weighting, schedule_prompt
    prompt = body.get("prompt", "")
    weights = body.get("weights", {})
    result = apply_prompt_weighting(prompt, weights)
    scheduled = None
    if body.get("early_concept") and body.get("refined_concept"):
        scheduled = schedule_prompt(body["early_concept"], body["refined_concept"], body.get("switch_ratio", 0.4))
    return {"status": "success", "weighted_prompt": result, "scheduled_prompt": scheduled}


@router.post("/control/flux")
async def control_flux(body: Dict[str, Any] = Body(...)):
    """FLUX native control (Canny, Depth, Fill, Kontext)."""
    from common_lib.modules.image_processing.services.advanced_control_service import flux_control

    image_b64 = body.get("image")
    img = _decode_image(image_b64) if image_b64 else None
    result = flux_control(
        image=img,
        prompt=body.get("prompt", ""),
        control_type=body.get("control_type", "canny"),
        strength=body.get("strength", 0.7),
    )
    return {"status": "success", "image": _encode_image(result["image"]),
            "control_type": result["control_type"], "duration_ms": result["duration_ms"]}


# ── NEX Preset Packages (§22, §24, §91) ──────────────────────────

import base64 as _b64


@router.post("/preset/nex/export")
async def preset_nex_export(body: Dict[str, Any] = Body(...)):
    """Export a face editing preset as a .nex ZIP package with provenance."""
    from common_lib.modules.image_processing.services.nex_preset_service import export_nex_preset
    from fastapi.responses import Response

    name = body.get("name", "Untitled Preset")
    description = body.get("description", "")
    tool_name = body.get("tool_name", "")
    tool_method = body.get("tool_method", "")
    params = body.get("params", {})
    category = body.get("category", "general")
    tags = body.get("tags", [])
    author = body.get("author", "platform")
    model = body.get("model", "")
    provider = body.get("provider", "")

    # Optional thumbnail
    thumbnail = None
    thumb_b64 = body.get("thumbnail")
    if thumb_b64:
        try:
            from PIL import Image as _PilImage
            import io as _io
            if thumb_b64.startswith("data:"):
                thumb_b64 = thumb_b64.split(",", 1)[1]
            thumb_bytes = _b64.b64decode(thumb_b64)
            thumbnail = _PilImage.open(_io.BytesIO(thumb_bytes))
        except Exception:
            pass

    zip_bytes = export_nex_preset(
        name=name, description=description, tool_name=tool_name,
        tool_method=tool_method, params=params, category=category,
        tags=tags, author=author, thumbnail_image=thumbnail,
        model=model, provider=provider,
    )

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name.replace(chr(32), "_")}.nex"'},
    )


@router.post("/preset/nex/import")
async def preset_nex_import(body: Dict[str, Any] = Body(...)):
    """Import a .nex preset package and extract configuration."""
    from common_lib.modules.image_processing.services.nex_preset_service import import_nex_preset

    zip_b64 = body.get("zip_data")
    if not zip_b64:
        raise HTTPException(400, detail="zip_data (base64) required")

    if zip_b64.startswith("data:"):
        zip_b64 = zip_b64.split(",", 1)[1]

    zip_bytes = _b64.b64decode(zip_b64)
    result = import_nex_preset(zip_bytes)
    return {"status": "success", **result}


@router.post("/preset/nex/verify")
async def preset_nex_verify(body: Dict[str, Any] = Body(...)):
    """Verify integrity of a .nex preset package."""
    from common_lib.modules.image_processing.services.nex_preset_service import verify_nex_preset

    zip_b64 = body.get("zip_data")
    if not zip_b64:
        raise HTTPException(400, detail="zip_data (base64) required")

    if zip_b64.startswith("data:"):
        zip_b64 = zip_b64.split(",", 1)[1]

    zip_bytes = _b64.b64decode(zip_b64)
    result = verify_nex_preset(zip_bytes)
    return {"status": "success", **result}


@router.post("/preset/nex/export-collection")
async def preset_nex_export_collection(body: Dict[str, Any] = Body(...)):
    """Export multiple presets as a single .nex collection package."""
    from common_lib.modules.image_processing.services.nex_preset_service import export_nex_preset_collection
    from fastapi.responses import Response

    presets = body.get("presets", [])
    collection_name = body.get("name", "Face Presets")

    zip_bytes = export_nex_preset_collection(presets, collection_name)

    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{collection_name.replace(chr(32), "_")}.nex"'},
    )


@router.post("/preset/nex/import-collection")
async def preset_nex_import_collection(body: Dict[str, Any] = Body(...)):
    """Import a .nex collection package containing multiple presets."""
    from common_lib.modules.image_processing.services.nex_preset_service import import_nex_preset_collection

    zip_b64 = body.get("zip_data")
    if not zip_b64:
        raise HTTPException(400, detail="zip_data (base64) required")

    if zip_b64.startswith("data:"):
        zip_b64 = zip_b64.split(",", 1)[1]

    zip_bytes = _b64.b64decode(zip_b64)
    result = import_nex_preset_collection(zip_bytes)
    return {"status": "success", **result}


# ── Full-Text Search Across All Endpoints ──────────────────────────

# Build route index at module load time
_ROUTE_INDEX: List[Dict[str, Any]] = []


def _build_route_index() -> None:
    """Build searchable index of all face routes."""
    global _ROUTE_INDEX
    if _ROUTE_INDEX:
        return
    for r in router.routes:
        if not hasattr(r, 'path') or not hasattr(r, 'methods'):
            continue
        doc = ''
        if hasattr(r, 'endpoint') and r.endpoint:
            doc = (r.endpoint.__doc__ or '').strip()
        # Build searchable text from path + name + docstring
        path_words = [w for w in r.path.replace('/', ' ').replace('-', ' ').replace('_', ' ').split() if w]
        name_words = (r.name or '').replace('_', ' ').split()
        doc_words = doc.lower().replace('/', ' ').replace('-', ' ').replace('_', ' ').split()
        # Extract category from path (first segment)
        segments = [s for s in r.path.split('/') if s]
        category = segments[0] if segments else 'general'
        # Tags from path segments
        tags = list(set(segments + name_words[:3]))
        _ROUTE_INDEX.append({
            'path': r.path,
            'methods': list(r.methods or []),
            'name': r.name or '',
            'summary': doc.split('\n')[0] if doc else '',
            'full_doc': doc,
            'category': category,
            'tags': tags,
            'search_text': ' '.join(path_words + name_words + doc_words).lower(),
        })


_build_route_index()


@router.get("/search")
async def face_search(
    q: str = "",
    category: Optional[str] = None,
    method: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 20,
):
    """Full-text search across all face endpoints.

    Searches path, name, summary, and tags.
    Filter by category (detect, restore, swap, style, video, etc.),
    HTTP method (GET/POST), or tag.
    """
    if not _ROUTE_INDEX:
        _build_route_index()

    query = q.lower().strip()
    results = _ROUTE_INDEX

    # Filter by category
    if category:
        cat_lower = category.lower()
        results = [r for r in results if cat_lower in r['category'].lower() or cat_lower in r['search_text']]

    # Filter by HTTP method
    if method:
        method_upper = method.upper()
        results = [r for r in results if method_upper in r['methods']]

    # Filter by tag
    if tag:
        tag_lower = tag.lower()
        results = [r for r in results if any(tag_lower in t.lower() for t in r['tags'])]

    # Full-text search with scoring
    if query:
        scored = []
        for route in results:
            score = 0
            text = route['search_text']
            name = route['name'].lower()
            summary = route['summary'].lower()

            # Exact match in name (highest score)
            if query == name:
                score += 100
            # Name starts with query
            elif name.startswith(query):
                score += 80
            # Name contains query
            elif query in name:
                score += 60
            # Summary contains query
            elif query in summary:
                score += 40
            # Path contains query
            elif query in route['path'].lower():
                score += 30
            # Any word matches
            else:
                query_words = query.split()
                for qw in query_words:
                    if qw in text:
                        score += 10
                    # Partial word match
                    for tw in text.split():
                        if tw.startswith(qw):
                            score += 5

            if score > 0:
                scored.append((score, route))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [r for _, r in scored[:limit]]
    else:
        results = results[:limit]

    return {
        "status": "success",
        "query": q,
        "total": len(results),
        "results": [
            {
                "path": r['path'],
                "methods": r['methods'],
                "name": r['name'],
                "summary": r['summary'],
                "category": r['category'],
                "tags": r['tags'],
            }
            for r in results
        ],
        "categories": list(set(r['category'] for r in _ROUTE_INDEX)),
        "total_endpoints": len(_ROUTE_INDEX),
    }


@router.get("/search/categories")
async def face_search_categories():
    """List all endpoint categories with counts."""
    if not _ROUTE_INDEX:
        _build_route_index()
    cats: Dict[str, int] = {}
    for r in _ROUTE_INDEX:
        cats[r['category']] = cats.get(r['category'], 0) + 1
    return {"status": "success", "categories": cats, "total": len(_ROUTE_INDEX)}


@router.get("/search/tags")
async def face_search_tags():
    """List all unique tags across endpoints."""
    if not _ROUTE_INDEX:
        _build_route_index()
    tags: Dict[str, int] = {}
    for r in _ROUTE_INDEX:
        for t in r['tags']:
            tags[t] = tags.get(t, 0) + 1
    sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
    return {"status": "success", "tags": dict(sorted_tags), "total_unique": len(tags)}


# ═══════════════════════════════════════════════════════════════════
# Quality Gate Routes
# ═══════════════════════════════════════════════════════════════════


@router.post("/quality-gate")
async def face_quality_gate(request: Request):
    """Detect faces, assess quality, and auto-route degraded faces to restoration.

    Quality dimensions: sharpness, noise, resolution, exposure.
    Auto-routes blurry/low-quality faces to CodeFormer/GFPGAN before editing.
    """
    from common_lib.modules.image_processing.services.face_quality_gate import (
        apply_quality_gate,
    )
    body = await request.json()
    image = _decode_image(body)
    if image is None:
        raise HTTPException(status_code=400, detail="No valid image provided")

    auto_restore = body.get("auto_restore", True)
    force_restore = body.get("force_restore", False)
    min_confidence = body.get("min_confidence", 0.5)
    max_faces = body.get("max_faces", 10)
    restore_strength = body.get("restore_strength", 0.5)

    restored, result = apply_quality_gate(
        image,
        auto_restore=auto_restore,
        force_restore=force_restore,
        min_confidence=min_confidence,
        max_faces=max_faces,
        restore_strength=restore_strength,
    )

    output = {"status": "success", **result.to_dict()}
    if auto_restore or force_restore:
        output["image"] = _encode_image(restored)
    return output


@router.post("/quality-gate/assess")
async def face_quality_assess(request: Request):
    """Assess face quality without applying restoration.
    Returns per-face quality scores and recommended actions.
    """
    from common_lib.modules.image_processing.services.face_quality_gate import (
        detect_and_assess_faces,
    )
    body = await request.json()
    image = _decode_image(body)
    if image is None:
        raise HTTPException(status_code=400, detail="No valid image provided")

    min_confidence = body.get("min_confidence", 0.5)
    max_faces = body.get("max_faces", 10)

    result = detect_and_assess_faces(
        image,
        min_confidence=min_confidence,
        max_faces=max_faces,
    )
    return {"status": "success", **result.to_dict()}


@router.post("/quality-gate/stream")
async def face_quality_gate_stream(request: Request):
    """Quality gate with SSE streaming for progress updates.
    Reports: detection → assessment → restoration per face.
    """
    from common_lib.modules.image_processing.services.face_quality_gate import (
        apply_quality_gate,
    )
    from fastapi.responses import StreamingResponse
    import json
    import asyncio

    body = await request.json()
    image = _decode_image(body)
    if image is None:
        raise HTTPException(status_code=400, detail="No valid image provided")

    auto_restore = body.get("auto_restore", True)
    restore_strength = body.get("restore_strength", 0.5)

    async def generate():
        yield f"event: progress\ndata: {json.dumps({'phase': 'detecting', 'message': 'Detecting faces...', 'progress': 10})}\n\n"
        await asyncio.sleep(0.05)

        try:
            restored, result = apply_quality_gate(
                image,
                auto_restore=auto_restore,
                restore_strength=restore_strength,
            )

            yield f"event: progress\ndata: {json.dumps({'phase': 'assessed', 'message': f'Found {result.faces_detected} face(s)', 'progress': 40, 'faces': result.faces_detected, 'to_restore': result.faces_to_restore})}\n\n"
            await asyncio.sleep(0.05)

            if result.needs_restore and auto_restore:
                for i, face_idx in enumerate(result.restore_faces):
                    pct = 50 + int(40 * (i / max(1, len(result.restore_faces))))
                    yield f"event: progress\ndata: {json.dumps({'phase': 'restoring', 'message': f'Restoring face {face_idx + 1}/{len(result.restore_faces)}', 'progress': pct, 'face_index': face_idx})}\n\n"
                    await asyncio.sleep(0.05)

            yield f"event: result\ndata: {json.dumps({**result.to_dict(), 'image': _encode_image(restored) if auto_restore else None})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


__all__ = ["router"]
