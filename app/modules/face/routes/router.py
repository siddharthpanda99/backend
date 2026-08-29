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
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Body
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


# ── Age ─────────────────────────────────────────────────────────


@router.post("/age")
async def transform_age(body: Dict[str, Any] = Body(...)):
    """Transform face age (5-80)."""
    from common_lib.modules.image_processing.services.face_operations import transform_age

    image = _decode_image(body.get("image", ""))
    target_age = body.get("target_age", 30)

    result = transform_age(image, target_age=target_age)
    return {"status": "success", "image": _encode_image(result)}


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


__all__ = ["router"]
