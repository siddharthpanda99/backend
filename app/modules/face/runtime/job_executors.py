"""Face background-job executors.

Moves blocking face operations OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_face_executors_registered` and runs on a jobs
worker thread under a per-device semaphore (gpu: 1, cpu: 4).

Artifact policy: image bytes are persisted with
``common_lib.modules.jobs.artifacts.save_artifact`` and only the ref strings
land in ``result_refs``. Inline ``image_b64`` payloads are decoded to PNG
artifacts and stripped from stored metadata — raw base64 never touches
``JobRecord``. A ``result.json`` metadata artifact (b64-free) accompanies
every job.

Completion fan-out (SSE/inbox) is handled by ``JobService`` itself, which
calls ``notify_job_complete`` on every terminal transition.
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any, Callable, Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

# Detection
DETECT_KIND = "face.detect"
DETECT_DEVICE = "cpu"
DETECT_TIMEOUT = 120.0

# Landmarks
LANDMARKS_KIND = "face.landmarks"
LANDMARKS_DEVICE = "cpu"
LANDMARKS_TIMEOUT = 120.0

# Alignment / Crop
ALIGN_KIND = "face.align"
ALIGN_DEVICE = "cpu"
ALIGN_TIMEOUT = 60.0

CROP_KIND = "face.crop"
CROP_DEVICE = "cpu"
CROP_TIMEOUT = 60.0

# Quality
QUALITY_KIND = "face.quality"
QUALITY_DEVICE = "cpu"
QUALITY_TIMEOUT = 60.0

# Restoration (GPU)
RESTORE_KIND = "face.restore"
RESTORE_DEVICE = "gpu"
RESTORE_TIMEOUT = 600.0

# Swapping (GPU)
SWAP_KIND = "face.swap"
SWAP_DEVICE = "gpu"
SWAP_TIMEOUT = 600.0

# Identity
EMBED_KIND = "face.identity.embed"
EMBED_DEVICE = "cpu"
EMBED_TIMEOUT = 120.0

COMPARE_KIND = "face.identity.compare"
COMPARE_DEVICE = "cpu"
COMPARE_TIMEOUT = 30.0

# Expression (GPU)
EXPRESSION_KIND = "face.expression"
EXPRESSION_DEVICE = "gpu"
EXPRESSION_TIMEOUT = 300.0

# Age (GPU)
AGE_KIND = "face.age"
AGE_DEVICE = "gpu"
AGE_TIMEOUT = 300.0

# Relighting (CPU)
RELIGHT_KIND = "face.relight"
RELIGHT_DEVICE = "cpu"
RELIGHT_TIMEOUT = 180.0

# Eyes / Mouth (CPU)
EYES_KIND = "face.eyes"
EYES_DEVICE = "cpu"
EYES_TIMEOUT = 120.0

MOUTH_KIND = "face.mouth"
MOUTH_DEVICE = "cpu"
MOUTH_TIMEOUT = 120.0

# Enhancement (GPU)
ENHANCE_KIND = "face.enhance"
ENHANCE_DEVICE = "gpu"
ENHANCE_TIMEOUT = 600.0

# Makeup (GPU)
MAKEUP_KIND = "face.makeup"
MAKEUP_DEVICE = "gpu"
MAKEUP_TIMEOUT = 300.0

MAKEUP_PRESET_KIND = "face.makeup.preset"
MAKEUP_PRESET_DEVICE = "gpu"
MAKEUP_PRESET_TIMEOUT = 300.0

MAKEUP_TEXT_KIND = "face.makeup.text"
MAKEUP_TEXT_DEVICE = "gpu"
MAKEUP_TEXT_TIMEOUT = 300.0

# Tattoo (GPU)
TATTOO_DESIGN_KIND = "face.tattoo.design"
TATTOO_DESIGN_DEVICE = "gpu"
TATTOO_DESIGN_TIMEOUT = 300.0

TATTOO_PLACE_KIND = "face.tattoo.place"
TATTOO_PLACE_DEVICE = "gpu"
TATTOO_PLACE_TIMEOUT = 300.0

TATTOO_REMOVE_KIND = "face.tattoo.remove"
TATTOO_REMOVE_DEVICE = "gpu"
TATTOO_REMOVE_TIMEOUT = 300.0

# Sticker / Logo / Composite (GPU)
STICKER_KIND = "face.sticker.generate"
STICKER_DEVICE = "gpu"
STICKER_TIMEOUT = 300.0

STICKER_PHOTO_KIND = "face.sticker.from_photo"
STICKER_PHOTO_DEVICE = "gpu"
STICKER_PHOTO_TIMEOUT = 300.0

STICKER_PACK_KIND = "face.sticker.character_pack"
STICKER_PACK_DEVICE = "gpu"
STICKER_PACK_TIMEOUT = 600.0

LOGO_KIND = "face.logo.generate"
LOGO_DEVICE = "gpu"
LOGO_TIMEOUT = 300.0

LOGO_VECTORIZE_KIND = "face.logo.vectorize"
LOGO_VECTORIZE_DEVICE = "cpu"
LOGO_VECTORIZE_TIMEOUT = 120.0

LOGO_VARIATIONS_KIND = "face.logo.variations"
LOGO_VARIATIONS_DEVICE = "gpu"
LOGO_VARIATIONS_TIMEOUT = 300.0

COMPOSITE_INSERT_KIND = "face.composite.insert_subject"
COMPOSITE_INSERT_DEVICE = "gpu"
COMPOSITE_INSERT_TIMEOUT = 300.0

COMPOSITE_OVERLAY_KIND = "face.composite.overlay"
COMPOSITE_OVERLAY_DEVICE = "gpu"
COMPOSITE_OVERLAY_TIMEOUT = 300.0

# Keys that carry inline image payloads — always stripped before persisting.
_B64_KEYS: tuple[str, ...] = ("image_b64", "image", "source", "target", "background", "subject_image", "reference", "photo", "tattoo", "overlay_image")


# ---------------------------------------------------------------------------
# Small helpers (sync, stdlib-only at import time)
# ---------------------------------------------------------------------------


def _record_params(record: Any) -> dict[str, Any]:
    try:
        params: Any = record.get_params()
    except Exception:
        return {}
    return params if isinstance(params, dict) else {}


def _record_id(record: Any) -> str:
    try:
        job_id: Any = record.id
    except Exception:
        return "unknown"
    return str(job_id)


def _strip_b64(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload without inline image blobs."""
    return {k: v for k, v in payload.items() if k not in _B64_KEYS}


def _decode_image(b64_data: str) -> np.ndarray:
    """Decode base64 image to RGB numpy array."""
    raw = base64.b64decode(b64_data)
    pil = Image.open(io.BytesIO(raw)).convert("RGB")
    return np.array(pil)


def _encode_image(arr: np.ndarray) -> str:
    """Encode RGB numpy array to base64 PNG."""
    pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _image_to_bytes(arr: np.ndarray) -> bytes:
    """Encode RGB numpy array to PNG bytes."""
    pil = Image.fromarray(arr)
    buf = io.BytesIO()
    pil.save(buf, format="PNG")
    return buf.getvalue()


def _save_png(job_id: str, filename: str, image_bytes: bytes) -> str:
    """Persist PNG bytes as a job artifact. Returns the ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    return save_artifact(job_id, filename, image_bytes)


def _save_json(job_id: str, filename: str, payload: dict[str, Any]) -> str:
    """Persist a JSON-serializable metadata payload. Returns the ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    return save_artifact(
        job_id, filename, json.dumps(payload, default=str).encode("utf-8")
    )


def _cancelled_result() -> dict[str, Any]:
    return {"result_refs": [], "status": "cancelled"}


async def _run_async(coro_factory: Callable[[], Any]) -> Any:
    """Run an async coroutine to completion on this worker thread."""
    import asyncio

    return asyncio.run(coro_factory())


def _finish(
    job_id: str,
    payload: dict[str, Any],
    *,
    extra_files: tuple[bytes, str] | tuple = (),
    status: str = "success",
) -> dict[str, Any]:
    """Persist result payload: artifact files first, then ``result.json``."""
    from common_lib.modules.jobs.artifacts import save_artifact

    refs: list[str] = []
    for file_bytes, filename in extra_files:
        if file_bytes:
            refs.append(save_artifact(job_id, filename, file_bytes))
    clean: dict[str, Any] = _strip_b64(dict(payload))
    clean["artifact_images"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(_save_json(job_id, "result.json", clean))
    return {"result_refs": refs, "status": status}


# ---------------------------------------------------------------------------
# Face operation executors
# ---------------------------------------------------------------------------


def detect_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.detect`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    detector = params.get("detector", "scrfd")
    confidence = params.get("confidence", 0.5)
    max_faces = params.get("max_faces", 10)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        detect_faces as _detect,
    )

    faces = _detect(
        image, detector=detector, confidence=confidence, max_faces=max_faces
    )
    report_progress(90.0)

    payload: dict[str, Any] = {"status": "success", "faces": faces, "count": len(faces)}
    return _finish(job_id, payload)


def landmarks_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.landmarks`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    bbox = params.get("bbox")
    model = params.get("model", "mediapipe")

    if not bbox:
        return _finish(job_id, {"error": "Missing 'bbox'"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        detect_landmarks as _landmarks,
    )

    result = _landmarks(image, bbox, model=model)
    if "points" in result and isinstance(result["points"], np.ndarray):
        result["points"] = result["points"].tolist()
    report_progress(90.0)

    return _finish(job_id, {"status": "success", **result})


def align_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.align`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    landmarks = np.array(params.get("landmarks", []))
    output_size = tuple(params.get("output_size", [256, 256]))
    scale = params.get("scale", 1.0)

    if len(landmarks) < 5:
        return _finish(job_id, {"error": "Need at least 5 landmarks"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import align_face

    result = align_face(image, landmarks, output_size=output_size, scale=scale)
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success"}
    return _finish(job_id, payload, extra_files=((img_bytes, "aligned.png"),))


def crop_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.crop`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    bbox = params.get("bbox")
    margin = params.get("margin", 1.6)
    output_size = tuple(params.get("output_size", [256, 256]))

    if not bbox:
        return _finish(job_id, {"error": "Missing 'bbox'"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import crop_face

    result = crop_face(image, bbox, margin=margin, output_size=output_size)
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "cropped.png"),))


def quality_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.quality`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    bbox = params.get("bbox")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        assess_face_quality,
    )

    result = assess_face_quality(image, face_bbox=bbox)
    report_progress(90.0)

    return _finish(job_id, {"status": "success", **result})


def restore_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.restore`` jobs (CodeFormer/GFPGAN)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    model = params.get("model", "codeformer")
    fidelity = params.get("fidelity", 0.5)
    upscale = params.get("upscale", False)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        restore_face,
    )

    result = _run_async(
        lambda: restore_face(image, model=model, fidelity=fidelity, upscale=upscale)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success", "model": model}
    return _finish(job_id, payload, extra_files=((img_bytes, "restored.png"),))


def swap_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.swap`` jobs (inswapper)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    source = _decode_image(params.get("source", ""))
    target = _decode_image(params.get("target", ""))
    source_bbox = params.get("source_bbox")
    target_bbox = params.get("target_bbox")
    model = params.get("model", "inswapper")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import swap_face

    result = _run_async(
        lambda: swap_face(
            source, target, source_bbox=source_bbox, target_bbox=target_bbox, model=model
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success", "model": model}, extra_files=((img_bytes, "swapped.png"),))


def embed_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.identity.embed`` jobs (ArcFace)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    bbox = params.get("bbox")
    model = params.get("model", "arcface")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        compute_face_embedding,
    )

    embedding = _run_async(
        lambda: compute_face_embedding(image, face_bbox=bbox, model=model)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    if embedding is None:
        return _finish(job_id, {"error": "No face detected"}, status="error")

    return _finish(job_id, {"status": "success", "embedding": embedding, "dimension": len(embedding)})


def compare_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.identity.compare`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    emb_a = params.get("embedding_a")
    emb_b = params.get("embedding_b")
    if not emb_a or not emb_b:
        return _finish(job_id, {"error": "Need embeddings"}, status="error")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import compare_faces

    similarity = _run_async(lambda: compare_faces(emb_a, emb_b))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(
        job_id,
        {
            "status": "success",
            "similarity": similarity,
            "match": similarity > 0.5,
            "confidence": "high"
            if similarity > 0.8
            else "medium"
            if similarity > 0.5
            else "low",
        },
    )


def expression_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.expression`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    expression = params.get("expression", "smile")
    strength = params.get("strength", 0.5)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        edit_expression,
    )

    result = _run_async(
        lambda: edit_expression(image, expression=expression, strength=strength)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success", "expression": expression}
    return _finish(job_id, payload, extra_files=((img_bytes, "expression.png"),))


def age_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.age`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    target_age = params.get("target_age", 30)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        transform_age,
    )

    result = _run_async(lambda: transform_age(image, target_age=target_age))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success", "target_age": target_age}
    return _finish(job_id, payload, extra_files=((img_bytes, "aged.png"),))


def relight_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.relight`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    direction = params.get("direction", "front")
    color = tuple(params.get("color", [255, 255, 255]))
    intensity = params.get("intensity", 0.7)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        relight_face,
    )

    result = _run_async(
        lambda: relight_face(
            image, light_direction=direction, light_color=color, intensity=intensity
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success", "direction": direction}
    return _finish(job_id, payload, extra_files=((img_bytes, "relighted.png"),))


def eyes_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.eyes`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    operation = params.get("operation", "whiten")
    value = params.get("value")
    strength = params.get("strength", 0.5)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import edit_eyes

    result = _run_async(
        lambda: edit_eyes(image, operation=operation, value=value, strength=strength)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success", "operation": operation}
    return _finish(job_id, payload, extra_files=((img_bytes, "eyes.png"),))


def mouth_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.mouth`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    operation = params.get("operation", "whiten_teeth")
    value = params.get("value")
    strength = params.get("strength", 0.5)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import edit_mouth

    result = _run_async(
        lambda: edit_mouth(image, operation=operation, value=value, strength=strength)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    payload: dict[str, Any] = {"status": "success", "operation": operation}
    return _finish(job_id, payload, extra_files=((img_bytes, "mouth.png"),))


def enhance_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.enhance`` jobs (full beautification)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    enhance_params = {k: v for k, v in params.items() if k != "image"}

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.face_operations import (
        full_beautification,
    )

    result = _run_async(lambda: full_beautification(image, **enhance_params))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "enhanced.png"),))


def makeup_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.makeup`` jobs (transfer)."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    reference_b64 = params.get("reference")
    if not reference_b64:
        return _finish(job_id, {"error": "Missing reference image"}, status="error")
    reference = _decode_image(reference_b64)
    region = params.get("region", "full")
    intensity = params.get("intensity", 0.7)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.beauty_operations import (
        makeup_transfer,
    )

    result = _run_async(
        lambda: makeup_transfer(image, reference, region=region, intensity=intensity)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "makeup.png"),))


def makeup_preset_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.makeup.preset`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    preset_id = params.get("preset", params.get("preset_id", "natural_glam"))

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.beauty_operations import (
        makeup_preset,
    )

    result = _run_async(lambda: makeup_preset(image, preset_id=preset_id))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success", "preset": preset_id}, extra_files=((img_bytes, "makeup_preset.png"),))


def makeup_text_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.makeup.text`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    prompt = params.get("prompt", params.get("makeup_prompt", ""))
    strength = params.get("strength", 0.6)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.beauty_operations import (
        makeup_apply_text,
    )

    result = _run_async(lambda: makeup_apply_text(image, prompt, strength=strength))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success", "prompt": prompt}, extra_files=((img_bytes, "makeup_text.png"),))


def tattoo_design_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.tattoo.design`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    prompt = params.get("prompt", "")
    style = params.get("style", "traditional")
    colors = params.get("colors")
    body_part = params.get("body_part")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.skin_operations import (
        tattoo_design,
    )

    result = _run_async(
        lambda: tattoo_design(
            prompt=prompt, style=style, colors=colors, body_part=body_part
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "tattoo_design.png"),))


def tattoo_place_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.tattoo.place`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    tattoo = _decode_image(params.get("tattoo", ""))
    body_part = params.get("body_part", params.get("body_region", "arm"))
    x = params.get("x")
    y = params.get("y")

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.skin_operations import (
        tattoo_place,
    )

    result = _run_async(
        lambda: tattoo_place(image, tattoo, body_part=body_part, x=x, y=y)
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "tattoo_placed.png"),))


def tattoo_remove_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.tattoo.remove`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image = _decode_image(params.get("image", ""))
    tattoo_region = params.get("tattoo_region")
    fade_sessions = params.get("fade_sessions", 0)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.skin_operations import (
        tattoo_remove,
    )

    result = _run_async(
        lambda: tattoo_remove(
            image, tattoo_region=tattoo_region, fade_sessions=fade_sessions
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result)
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "tattoo_removed.png"),))


def sticker_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.sticker.generate`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "image required"}, status="error")

    style = params.get("style", "flat")
    img = _decode_image(image_b64)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        generate_sticker as _gen_sticker,
        STICKER_STYLES,
    )

    if style not in STICKER_STYLES:
        return _finish(job_id, {"error": f"Unknown style: {style}"}, status="error")

    result = _run_async(
        lambda: _gen_sticker(
            base_image=img,
            style=style,
            add_border=params.get("add_border", True),
            border_color=params.get("border_color", "#ffffff"),
            border_width=params.get("border_width", 4),
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result["image"])
    payload: dict[str, Any] = {
        "status": "success",
        "style": style,
        "style_prompt": result["style_prompt"],
        "border_applied": result["border_applied"],
    }
    return _finish(job_id, payload, extra_files=((img_bytes, "sticker.png"),))


def sticker_photo_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.sticker.from_photo`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    photo_b64 = params.get("photo")
    if not photo_b64:
        return _finish(job_id, {"error": "photo required"}, status="error")

    img = _decode_image(photo_b64)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        sticker_from_photo as _sticker_photo,
    )

    result = _run_async(
        lambda: _sticker_photo(
            photo=img,
            style=params.get("style", "flat"),
            subject_hint=params.get("subject_hint"),
            add_border=params.get("add_border", True),
            border_color=params.get("border_color", "#ffffff"),
            border_width=params.get("border_width", 4),
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result["image"])
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "sticker_from_photo.png"),))


def sticker_pack_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.sticker.character_pack`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "image required"}, status="error")

    img = _decode_image(image_b64)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        generate_character_pack as _char_pack,
    )

    result = _run_async(
        lambda: _char_pack(
            base_image=img,
            expressions=params.get("expressions"),
            style=params.get("style", "kawaii"),
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    stickers_bytes = [
        (_image_to_bytes(s["image"]), f"sticker_{s['expression']}.png")
        for s in result["stickers"]
    ]
    return _finish(job_id, {"status": "success", "count": result["count"]}, extra_files=tuple(stickers_bytes))


def logo_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.logo.generate`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    brand_name = params.get("brand_name")
    if not brand_name:
        return _finish(job_id, {"error": "brand_name required"}, status="error")

    style = params.get("style", "minimal")

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        generate_logo as _gen_logo,
        LOGO_STYLES,
    )

    if style not in LOGO_STYLES:
        return _finish(job_id, {"error": f"Unknown style: {style}"}, status="error")

    result = _run_async(
        lambda: _gen_logo(
            brand_name=brand_name,
            style=style,
            colors=params.get("colors"),
            tagline=params.get("tagline"),
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result["image"])
    payload: dict[str, Any] = {
        "status": "success",
        "brand_name": result["brand_name"],
        "style": style,
        "colors": result["colors"],
    }
    return _finish(job_id, payload, extra_files=((img_bytes, "logo.png"),))


def logo_vectorize_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.logo.vectorize`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "image required"}, status="error")

    img = _decode_image(image_b64)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        vectorize_logo as _vec_logo,
    )

    result = _run_async(
        lambda: _vec_logo(img=img, output_format=params.get("format", "svg"))
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    return _finish(
        job_id,
        {
            "status": "success",
            "svg_data": result["svg_data"],
            "format": result["format"],
        },
    )


def logo_variations_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.logo.variations`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()

    image_b64 = params.get("image")
    if not image_b64:
        return _finish(job_id, {"error": "image required"}, status="error")

    img = _decode_image(image_b64)

    report_progress(30.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        generate_logo_variations as _logo_vars,
    )

    result = _run_async(lambda: _logo_vars(logo=img, variations=params.get("variations")))
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    variations_bytes = [
        (_image_to_bytes(v["image"]), f"logo_{v['name']}.png")
        for v in result["variations"]
    ]
    return _finish(job_id, {"status": "success", "count": result["count"]}, extra_files=tuple(variations_bytes))


def composite_insert_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.composite.insert_subject`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    bg_b64 = params.get("background")
    sub_b64 = params.get("subject_image")
    if not bg_b64 or not sub_b64:
        return _finish(job_id, {"error": "background and subject_image required"}, status="error")

    bg = _decode_image(bg_b64)
    subject = _decode_image(sub_b64)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        insert_subject as _insert,
    )

    result = _run_async(
        lambda: _insert(
            background=bg,
            subject=subject,
            position=tuple(params.get("position", [0, 0])),
            scale=params.get("scale", 1.0),
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result["image"])
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "composite.png"),))


def composite_overlay_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``face.composite.overlay`` jobs."""
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()

    base_b64 = params.get("base_image")
    overlay_b64 = params.get("overlay_image")
    if not base_b64 or not overlay_b64:
        return _finish(job_id, {"error": "base_image and overlay_image required"}, status="error")

    base = _decode_image(base_b64)
    overlay = _decode_image(overlay_b64)

    report_progress(15.0)
    if check_cancel():
        return _cancelled_result()

    from common_lib.modules.image_processing.services.compositing_service import (
        overlay_image as _overlay,
    )

    result = _run_async(
        lambda: _overlay(
            base_image=base,
            overlay_image=overlay,
            position=tuple(params.get("position", [0, 0])),
            scale=params.get("scale", 1.0),
            blend_mode=params.get("blend_mode", "normal"),
            opacity=params.get("opacity", 1.0),
        )
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)

    img_bytes = _image_to_bytes(result["image"])
    return _finish(job_id, {"status": "success"}, extra_files=((img_bytes, "overlay.png"),))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Callable[..., Any], str, float], ...] = (
    # Detection
    (DETECT_KIND, detect_executor, DETECT_DEVICE, DETECT_TIMEOUT),
    (LANDMARKS_KIND, landmarks_executor, LANDMARKS_DEVICE, LANDMARKS_TIMEOUT),
    # Alignment / Crop
    (ALIGN_KIND, align_executor, ALIGN_DEVICE, ALIGN_TIMEOUT),
    (CROP_KIND, crop_executor, CROP_DEVICE, CROP_TIMEOUT),
    # Quality
    (QUALITY_KIND, quality_executor, QUALITY_DEVICE, QUALITY_TIMEOUT),
    # Restoration
    (RESTORE_KIND, restore_executor, RESTORE_DEVICE, RESTORE_TIMEOUT),
    # Swapping
    (SWAP_KIND, swap_executor, SWAP_DEVICE, SWAP_TIMEOUT),
    # Identity
    (EMBED_KIND, embed_executor, EMBED_DEVICE, EMBED_TIMEOUT),
    (COMPARE_KIND, compare_executor, COMPARE_DEVICE, COMPARE_TIMEOUT),
    # Expression
    (EXPRESSION_KIND, expression_executor, EXPRESSION_DEVICE, EXPRESSION_TIMEOUT),
    # Age
    (AGE_KIND, age_executor, AGE_DEVICE, AGE_TIMEOUT),
    # Relighting
    (RELIGHT_KIND, relight_executor, RELIGHT_DEVICE, RELIGHT_TIMEOUT),
    # Eyes / Mouth
    (EYES_KIND, eyes_executor, EYES_DEVICE, EYES_TIMEOUT),
    (MOUTH_KIND, mouth_executor, MOUTH_DEVICE, MOUTH_TIMEOUT),
    # Enhancement
    (ENHANCE_KIND, enhance_executor, ENHANCE_DEVICE, ENHANCE_TIMEOUT),
    # Makeup
    (MAKEUP_KIND, makeup_executor, MAKEUP_DEVICE, MAKEUP_TIMEOUT),
    (MAKEUP_PRESET_KIND, makeup_preset_executor, MAKEUP_PRESET_DEVICE, MAKEUP_PRESET_TIMEOUT),
    (MAKEUP_TEXT_KIND, makeup_text_executor, MAKEUP_TEXT_DEVICE, MAKEUP_TEXT_TIMEOUT),
    # Tattoo
    (TATTOO_DESIGN_KIND, tattoo_design_executor, TATTOO_DESIGN_DEVICE, TATTOO_DESIGN_TIMEOUT),
    (TATTOO_PLACE_KIND, tattoo_place_executor, TATTOO_PLACE_DEVICE, TATTOO_PLACE_TIMEOUT),
    (TATTOO_REMOVE_KIND, tattoo_remove_executor, TATTOO_REMOVE_DEVICE, TATTOO_REMOVE_TIMEOUT),
    # Sticker
    (STICKER_KIND, sticker_executor, STICKER_DEVICE, STICKER_TIMEOUT),
    (STICKER_PHOTO_KIND, sticker_photo_executor, STICKER_PHOTO_DEVICE, STICKER_PHOTO_TIMEOUT),
    (STICKER_PACK_KIND, sticker_pack_executor, STICKER_PACK_DEVICE, STICKER_PACK_TIMEOUT),
    # Logo
    (LOGO_KIND, logo_executor, LOGO_DEVICE, LOGO_TIMEOUT),
    (LOGO_VECTORIZE_KIND, logo_vectorize_executor, LOGO_VECTORIZE_DEVICE, LOGO_VECTORIZE_TIMEOUT),
    (LOGO_VARIATIONS_KIND, logo_variations_executor, LOGO_VARIATIONS_DEVICE, LOGO_VARIATIONS_TIMEOUT),
    # Composite
    (COMPOSITE_INSERT_KIND, composite_insert_executor, COMPOSITE_INSERT_DEVICE, COMPOSITE_INSERT_TIMEOUT),
    (COMPOSITE_OVERLAY_KIND, composite_overlay_executor, COMPOSITE_OVERLAY_DEVICE, COMPOSITE_OVERLAY_TIMEOUT),
)


def ensure_face_executors_registered() -> bool:
    """Register all face executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_face_executors_registered failed: %s", exc)
        return False


__all__ = [
    "AGE_DEVICE",
    "AGE_KIND",
    "AGE_TIMEOUT",
    "ALIGN_DEVICE",
    "ALIGN_KIND",
    "ALIGN_TIMEOUT",
    "COMPARE_DEVICE",
    "COMPARE_KIND",
    "COMPARE_TIMEOUT",
    "COMPOSITE_INSERT_DEVICE",
    "COMPOSITE_INSERT_KIND",
    "COMPOSITE_INSERT_TIMEOUT",
    "COMPOSITE_OVERLAY_DEVICE",
    "COMPOSITE_OVERLAY_KIND",
    "COMPOSITE_OVERLAY_TIMEOUT",
    "DETECT_DEVICE",
    "DETECT_KIND",
    "DETECT_TIMEOUT",
    "EYES_DEVICE",
    "EYES_KIND",
    "EYES_TIMEOUT",
    "EMBED_DEVICE",
    "EMBED_KIND",
    "EMBED_TIMEOUT",
    "ENHANCE_DEVICE",
    "ENHANCE_KIND",
    "ENHANCE_TIMEOUT",
    "EXPRESSION_DEVICE",
    "EXPRESSION_KIND",
    "EXPRESSION_TIMEOUT",
    "LOGO_DEVICE",
    "LOGO_KIND",
    "LOGO_TIMEOUT",
    "LOGO_VECTORIZE_DEVICE",
    "LOGO_VECTORIZE_KIND",
    "LOGO_VECTORIZE_TIMEOUT",
    "LOGO_VARIATIONS_DEVICE",
    "LOGO_VARIATIONS_KIND",
    "LOGO_VARIATIONS_TIMEOUT",
    "MAKEUP_DEVICE",
    "MAKEUP_KIND",
    "MAKEUP_TIMEOUT",
    "MAKEUP_PRESET_DEVICE",
    "MAKEUP_PRESET_KIND",
    "MAKEUP_PRESET_TIMEOUT",
    "MAKEUP_TEXT_DEVICE",
    "MAKEUP_TEXT_KIND",
    "MAKEUP_TEXT_TIMEOUT",
    "MOUTH_DEVICE",
    "MOUTH_KIND",
    "MOUTH_TIMEOUT",
    "QUALITY_DEVICE",
    "QUALITY_KIND",
    "QUALITY_TIMEOUT",
    "RELIGHT_DEVICE",
    "RELIGHT_KIND",
    "RELIGHT_TIMEOUT",
    "RESTORE_DEVICE",
    "RESTORE_KIND",
    "RESTORE_TIMEOUT",
    "STICKER_DEVICE",
    "STICKER_KIND",
    "STICKER_TIMEOUT",
    "STICKER_PHOTO_DEVICE",
    "STICKER_PHOTO_KIND",
    "STICKER_PHOTO_TIMEOUT",
    "STICKER_PACK_DEVICE",
    "STICKER_PACK_KIND",
    "STICKER_PACK_TIMEOUT",
    "SWAP_DEVICE",
    "SWAP_KIND",
    "SWAP_TIMEOUT",
    "TATTOO_DESIGN_DEVICE",
    "TATTOO_DESIGN_KIND",
    "TATTOO_DESIGN_TIMEOUT",
    "TATTOO_PLACE_DEVICE",
    "TATTOO_PLACE_KIND",
    "TATTOO_PLACE_TIMEOUT",
    "TATTOO_REMOVE_DEVICE",
    "TATTOO_REMOVE_KIND",
    "TATTOO_REMOVE_TIMEOUT",
    "align_executor",
    "age_executor",
    "compare_executor",
    "composite_insert_executor",
    "composite_overlay_executor",
    "crop_executor",
    "detect_executor",
    "embed_executor",
    "enhance_executor",
    "ensure_face_executors_registered",
    "expression_executor",
    "eyes_executor",
    "logo_executor",
    "logo_vectorize_executor",
    "logo_variations_executor",
    "makeup_executor",
    "makeup_preset_executor",
    "makeup_text_executor",
    "mouth_executor",
    "quality_executor",
    "relight_executor",
    "restore_executor",
    "sticker_executor",
    "sticker_pack_executor",
    "sticker_photo_executor",
    "swap_executor",
    "tattoo_design_executor",
    "tattoo_place_executor",
    "tattoo_remove_executor",
]