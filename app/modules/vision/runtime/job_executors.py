"""Vision background-job executors (SOTA / Qwen-2.1 / diffusion / img-ops).

Moves blocking vision work OFF the FastAPI event loop onto the jobs module:
each executor is a blocking ``fn(record, check_cancel, report_progress)``
registered via :func:`ensure_vision_executors_registered` and runs on a jobs
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
import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Job kinds / devices / timeouts
# ---------------------------------------------------------------------------

SOTA_SINGLE_KIND = "vision.sota.single"
SOTA_SINGLE_DEVICE = "gpu"
SOTA_SINGLE_TIMEOUT = 900.0

SOTA_BATCH_KIND = "vision.sota.batch"
SOTA_BATCH_DEVICE = "gpu"
SOTA_BATCH_TIMEOUT = 1800.0

QWEN21_TXT2IMG_KIND = "vision.qwen21.txt2img"
QWEN21_IMG2IMG_KIND = "vision.qwen21.img2img"
QWEN21_INPAINT_KIND = "vision.qwen21.inpaint"
QWEN21_OUTPAINT_KIND = "vision.qwen21.outpaint"
QWEN21_DEVICE = "gpu"
QWEN21_TIMEOUT = 900.0

DIFFUSION_GENERATE_KIND = "vision.diffusion.generate"
DIFFUSION_GENERATE_DEVICE = "gpu"
DIFFUSION_GENERATE_TIMEOUT = 900.0

DIFFUSION_LOAD_KIND = "vision.diffusion.load"
DIFFUSION_LOAD_DEVICE = "gpu"
DIFFUSION_LOAD_TIMEOUT = 600.0

IMGOPS_KIND = "vision.imgops"
IMGOPS_DEVICE = "gpu"
IMGOPS_TIMEOUT = 600.0

CAPTION_KIND = "vision.caption"
CAPTION_DEVICE = "cpu"
CAPTION_TIMEOUT = 300.0

SEGMENT_KIND = "vision.segment"
SEGMENT_DEVICE = "gpu"
SEGMENT_TIMEOUT = 600.0

FACE_SWAP_KIND = "vision.face_swap"
FACE_SWAP_DEVICE = "gpu"
FACE_SWAP_TIMEOUT = 600.0

ENCODE_KIND = "vision.encode"
ENCODE_DEVICE = "cpu"
ENCODE_TIMEOUT = 300.0

# Keys that carry inline image payloads — always stripped before persisting.
_B64_KEYS: tuple[str, ...] = ("image_b64", "images", "image")


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


def _save_png(job_id: str, filename: str, b64_data: str) -> Optional[str]:
    """Decode a base64 PNG and persist it as a job artifact. Returns the ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    try:
        raw: bytes = base64.b64decode(b64_data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("jobs: %s: invalid base64 for %s: %s", job_id, filename, exc)
        return None
    return save_artifact(job_id, filename, raw)


def _save_json(job_id: str, filename: str, payload: dict[str, Any]) -> str:
    """Persist a JSON-serializable metadata payload. Returns the ref."""
    from common_lib.modules.jobs.artifacts import save_artifact

    return save_artifact(
        job_id, filename, json.dumps(payload, default=str).encode("utf-8")
    )


def _cancelled_result() -> dict[str, Any]:
    return {"result_refs": [], "status": "cancelled"}


# ---------------------------------------------------------------------------
# SOTA single / batch (krea-2-turbo, qwen21, ming)
# ---------------------------------------------------------------------------


def sota_single_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``vision.sota.single`` jobs."""
    from common_lib.modules.vision.sota_generation_service import _SINGLE_DISPATCH

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    model: str = str(params.get("model", ""))
    if model not in _SINGLE_DISPATCH:
        raise ValueError(f"Unknown SOTA model: {model!r}")
    kwargs: dict[str, Any] = {
        "prompt": str(params.get("prompt", "")),
        "width": int(params.get("width", 1024)),
        "height": int(params.get("height", 1024)),
        "steps": int(params.get("steps", 20)),
        "cfg": float(params.get("cfg", 1.0)),
        "seed": int(params.get("seed", 0)),
        "device": str(params.get("device", "cuda")),
    }
    if model != "ming":
        kwargs["negative_prompt"] = str(params.get("negative_prompt", ""))
    report_progress(15.0)
    result: dict[str, Any] = _SINGLE_DISPATCH[model](**kwargs)
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    refs: list[str] = []
    meta: dict[str, Any] = dict(result)
    b64: Any = result.get("image_b64")
    if isinstance(b64, str) and b64:
        ref: Optional[str] = _save_png(job_id, f"{model}_output.png", b64)
        if ref:
            refs.append(ref)
    meta = _strip_b64(meta)
    meta["artifact_images"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(_save_json(job_id, "result.json", meta))
    report_progress(100.0)
    return {"result_refs": refs, "status": str(result.get("status", "unknown"))}


def sota_batch_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``vision.sota.batch`` jobs.

    Batch generators write PNGs into the job artifact dir directly, so refs
    are collected from disk — no base64 round-trip.
    """
    from common_lib.modules.jobs.artifacts import job_dir
    from common_lib.modules.vision.sota_generation_service import _BATCH_DISPATCH

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    model: str = str(params.get("model", ""))
    if model not in _BATCH_DISPATCH:
        raise ValueError(f"Unknown SOTA model: {model!r}")
    items: Any = params.get("items", [])
    if not isinstance(items, list):
        raise ValueError("'items' must be a list")
    out_dir = job_dir(job_id)
    report_progress(10.0)
    result: dict[str, Any] = _BATCH_DISPATCH[model](
        items=items,
        device=str(params.get("device", "cuda")),
        output_dir=str(out_dir),
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    refs: list[str] = sorted(
        str(p) for p in out_dir.iterdir() if p.is_file() and p.suffix == ".png"
    )
    meta: dict[str, Any] = {
        "status": result.get("status"),
        "model": model,
        "total": result.get("total", len(items)),
        "results": result.get("results", []),
        "artifact_images": refs,
    }
    refs.append(_save_json(job_id, "result.json", meta))
    report_progress(100.0)
    return {"result_refs": refs, "status": str(result.get("status", "unknown"))}


# ---------------------------------------------------------------------------
# Qwen-Image-2.1 (txt2img / img2img / inpaint / outpaint)
# ---------------------------------------------------------------------------


def _qwen21_service() -> Any:
    from common_lib.modules.image_processing.services.qwen21_service import (
        get_qwen21_service,
    )

    return get_qwen21_service()


def _qwen21_finish(
    job_id: str,
    meta: dict[str, Any],
    model: str = "qwen21",
) -> dict[str, Any]:
    """Persist qwen21 meta (b64-free) + PNG artifact. Returns executor payload."""
    refs: list[str] = []
    b64: Any = meta.get("image_b64")
    if isinstance(b64, str) and b64:
        ref: Optional[str] = _save_png(job_id, f"{model}_output.png", b64)
        if ref:
            refs.append(ref)
    clean: dict[str, Any] = _strip_b64(dict(meta))
    clean["artifact_images"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(_save_json(job_id, "result.json", clean))
    return {"result_refs": refs, "status": "success" if b64 else "error"}


def qwen21_txt2img_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    svc: Any = _qwen21_service()
    svc.load(device=str(params.get("device", "cuda")))
    if check_cancel():
        return _cancelled_result()
    report_progress(20.0)
    meta: dict[str, Any] = svc.txt2img(
        prompt=str(params.get("prompt", "")),
        negative_prompt=str(params.get("negative_prompt", "")),
        width=int(params.get("width", 1024)),
        height=int(params.get("height", 1024)),
        steps=int(params.get("steps", 20)),
        cfg=float(params.get("cfg", 1.0)),
        seed=int(params.get("seed", 0)),
        device=str(params.get("device", "cuda")),
        save_to_worklog=True,
    )
    report_progress(90.0)
    out: dict[str, Any] = _qwen21_finish(job_id, meta)
    report_progress(100.0)
    return out


def _decode_upload(params: dict[str, Any], key: str) -> bytes:
    b64: Any = params.get(key, "")
    if not isinstance(b64, str) or not b64:
        raise ValueError(f"Missing required upload field: {key!r} (base64)")
    return base64.b64decode(b64)


def qwen21_img2img_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    image: bytes = _decode_upload(params, "image_b64")
    svc: Any = _qwen21_service()
    svc.load(device=str(params.get("device", "cuda")))
    if check_cancel():
        return _cancelled_result()
    report_progress(20.0)
    meta: dict[str, Any] = svc.img2img(
        prompt=str(params.get("prompt", "")),
        image=image,
        strength=float(params.get("strength", 0.6)),
        steps=int(params.get("steps", 20)),
        cfg=float(params.get("cfg", 1.0)),
        seed=int(params.get("seed", 0)),
        negative_prompt=str(params.get("negative_prompt", "")),
        device=str(params.get("device", "cuda")),
        save_to_worklog=True,
    )
    report_progress(90.0)
    out: dict[str, Any] = _qwen21_finish(job_id, meta)
    report_progress(100.0)
    return out


def qwen21_inpaint_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    image: bytes = _decode_upload(params, "image_b64")
    mask: bytes = _decode_upload(params, "mask_b64")
    svc: Any = _qwen21_service()
    svc.load(device=str(params.get("device", "cuda")))
    if check_cancel():
        return _cancelled_result()
    report_progress(20.0)
    meta: dict[str, Any] = svc.inpaint(
        prompt=str(params.get("prompt", "")),
        image=image,
        mask=mask,
        strength=float(params.get("strength", 1.0)),
        steps=int(params.get("steps", 20)),
        cfg=float(params.get("cfg", 1.0)),
        seed=int(params.get("seed", 0)),
        negative_prompt=str(params.get("negative_prompt", "")),
        feather_px=int(params.get("feather_px", 16)),
        device=str(params.get("device", "cuda")),
        save_to_worklog=True,
    )
    report_progress(90.0)
    out: dict[str, Any] = _qwen21_finish(job_id, meta)
    report_progress(100.0)
    return out


def qwen21_outpaint_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    image: bytes = _decode_upload(params, "image_b64")
    svc: Any = _qwen21_service()
    svc.load(device=str(params.get("device", "cuda")))
    if check_cancel():
        return _cancelled_result()
    report_progress(20.0)
    meta: dict[str, Any] = svc.outpaint(
        prompt=str(params.get("prompt", "")),
        image=image,
        pad=int(params.get("pad", 256)),
        steps=int(params.get("steps", 20)),
        cfg=float(params.get("cfg", 1.0)),
        seed=int(params.get("seed", 0)),
        negative_prompt=str(params.get("negative_prompt", "")),
        feather_px=int(params.get("feather_px", 32)),
        device=str(params.get("device", "cuda")),
        save_to_worklog=True,
    )
    report_progress(90.0)
    out: dict[str, Any] = _qwen21_finish(job_id, meta)
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Diffusion runtime (generate / load)
# ---------------------------------------------------------------------------


def diffusion_generate_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``vision.diffusion.generate`` jobs."""
    from common_lib.modules.vision.runtime_service import generate_image

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    seed_raw: Any = params.get("seed")
    result: dict[str, Any] = generate_image(
        prompt=str(params.get("prompt", "")),
        negative_prompt=str(params.get("negative_prompt", "")),
        width=int(params.get("width", 512)),
        height=int(params.get("height", 512)),
        num_inference_steps=int(params.get("num_inference_steps", 30)),
        guidance_scale=float(params.get("guidance_scale", 7.5)),
        seed=int(seed_raw) if seed_raw is not None else None,
        family_key=params.get("family_key"),
        family=str(params.get("family", "auto")),
        num_images=int(params.get("num_images", 1)),
    )
    if check_cancel():
        return _cancelled_result()
    report_progress(90.0)
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    refs: list[str] = []
    images: Any = result.get("images", [])
    if isinstance(images, list):
        for i, b64 in enumerate(images):
            if isinstance(b64, str) and b64:
                ref: Optional[str] = _save_png(job_id, f"image_{i:03d}.png", b64)
                if ref:
                    refs.append(ref)
    clean: dict[str, Any] = _strip_b64(dict(result))
    clean["artifact_images"] = [r for r in refs if not r.endswith("result.json")]
    refs.append(_save_json(job_id, "result.json", clean))
    report_progress(100.0)
    return {"result_refs": refs, "status": "success"}


def diffusion_load_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``vision.diffusion.load`` jobs."""
    from common_lib.modules.vision.runtime_service import load_model

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    result: dict[str, Any] = load_model(
        family=params.get("family", "auto"),
        model_id=str(params.get("model_id", "")),
        torch_dtype=params.get("torch_dtype", "float16"),
    )
    if check_cancel():
        return _cancelled_result()
    if result.get("error"):
        raise RuntimeError(str(result["error"]))
    refs: list[str] = [_save_json(job_id, "result.json", dict(result))]
    report_progress(100.0)
    return {"result_refs": refs, "status": "success"}


# ---------------------------------------------------------------------------
# Image ops (SLOW_OPS) — single image through process_image
# ---------------------------------------------------------------------------


def imgops_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    """Blocking executor for ``vision.imgops`` jobs (slow ops only)."""
    from common_lib.modules.image_processing.ops_service import process_image

    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(5.0)
    if check_cancel():
        return _cancelled_result()
    method: str = str(params.get("method", ""))
    if not method:
        raise ValueError("Missing 'method' param")
    raw: bytes = _decode_upload(params, "image_b64")
    op_params: Any = params.get("op_params", {})
    if not isinstance(op_params, dict):
        op_params = {}
    report_progress(15.0)
    out: Any = process_image(method, raw, dict(op_params))
    if check_cancel():
        return _cancelled_result()
    report_progress(85.0)
    refs: list[str] = []
    if isinstance(out, bytes):
        from common_lib.modules.jobs.artifacts import save_artifact

        refs.append(save_artifact(job_id, "output.png", out))
        meta: dict[str, Any] = {"method": method, "artifact_images": list(refs)}
    else:
        payload: Any = out if isinstance(out, dict) else {"result": out}
        meta = _strip_b64(dict(payload))
        meta["method"] = method
        meta["artifact_images"] = []
    refs.append(_save_json(job_id, "result.json", meta))
    report_progress(100.0)
    return {"result_refs": refs, "status": "success"}


# ---------------------------------------------------------------------------
# Image-processing pipeline ops (caption / segment / face-swap / encode)
# ---------------------------------------------------------------------------


def _pipeline() -> Any:
    from common_lib.modules.image_processing.pipeline import ImageProcessingPipeline

    return ImageProcessingPipeline()


def caption_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    job_id: str = _record_id(record)
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    svc: Any = _pipeline()
    result: Any = svc.caption(str(params.get("image_path", "")))
    if hasattr(result, "model_dump"):
        payload: dict[str, Any] = result.model_dump()
    elif hasattr(result, "__dict__"):
        payload = dict(result.__dict__)
    else:
        payload = {"caption": str(result)}
    refs: list[str] = [_save_json(job_id, "result.json", _strip_b64(payload))]
    report_progress(100.0)
    return {"result_refs": refs, "status": "success"}


def _pipeline_optional_op(
    record: Any,
    op: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Run an optional pipeline op (segment/face_swap/encode) with fallback."""
    from common_lib.modules.jobs.artifacts import save_artifact

    job_id: str = _record_id(record)
    svc: Any = _pipeline()
    fn: Any = getattr(svc, op, None)
    if fn is None:
        fallback: dict[str, Any] = {"op": op, "status": "unavailable", **payload}
        refs: list[str] = [_save_json(job_id, "result.json", fallback)]
        return {"result_refs": refs, "status": "unavailable"}
    result: Any = fn(**payload)
    if isinstance(result, bytes):
        refs = [save_artifact(job_id, "output.png", result)]
        meta: dict[str, Any] = {"op": op, "status": "success", "artifact_images": refs}
    elif isinstance(result, dict):
        meta = _strip_b64(dict(result))
        meta.setdefault("op", op)
        meta.setdefault("status", "success")
        meta["artifact_images"] = []
        refs = []
    else:
        meta = {"op": op, "status": "success", "result": str(result)}
        refs = []
    refs.append(_save_json(job_id, "result.json", meta))
    return {"result_refs": refs, "status": str(meta.get("status", "success"))}


def segment_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    out: dict[str, Any] = _pipeline_optional_op(
        record,
        "segment",
        {
            "image_path": str(params.get("image_path", "")),
            "prompt": params.get("prompt"),
        },
    )
    report_progress(100.0)
    return out


def face_swap_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    out: dict[str, Any] = _pipeline_optional_op(
        record,
        "face_swap",
        {
            "source_image": str(params.get("source_image", "")),
            "target_image": str(params.get("target_image", "")),
        },
    )
    report_progress(100.0)
    return out


def encode_executor(
    record: Any,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[float], None],
) -> Any:
    params: dict[str, Any] = _record_params(record)
    report_progress(10.0)
    if check_cancel():
        return _cancelled_result()
    out: dict[str, Any] = _pipeline_optional_op(
        record,
        "encode",
        {"image_path": str(params.get("image_path", "")), "text": params.get("text")},
    )
    report_progress(100.0)
    return out


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

_EXECUTORS: tuple[tuple[str, Any, str, float], ...] = (
    (SOTA_SINGLE_KIND, sota_single_executor, SOTA_SINGLE_DEVICE, SOTA_SINGLE_TIMEOUT),
    (SOTA_BATCH_KIND, sota_batch_executor, SOTA_BATCH_DEVICE, SOTA_BATCH_TIMEOUT),
    (QWEN21_TXT2IMG_KIND, qwen21_txt2img_executor, QWEN21_DEVICE, QWEN21_TIMEOUT),
    (QWEN21_IMG2IMG_KIND, qwen21_img2img_executor, QWEN21_DEVICE, QWEN21_TIMEOUT),
    (QWEN21_INPAINT_KIND, qwen21_inpaint_executor, QWEN21_DEVICE, QWEN21_TIMEOUT),
    (QWEN21_OUTPAINT_KIND, qwen21_outpaint_executor, QWEN21_DEVICE, QWEN21_TIMEOUT),
    (
        DIFFUSION_GENERATE_KIND,
        diffusion_generate_executor,
        DIFFUSION_GENERATE_DEVICE,
        DIFFUSION_GENERATE_TIMEOUT,
    ),
    (
        DIFFUSION_LOAD_KIND,
        diffusion_load_executor,
        DIFFUSION_LOAD_DEVICE,
        DIFFUSION_LOAD_TIMEOUT,
    ),
    (IMGOPS_KIND, imgops_executor, IMGOPS_DEVICE, IMGOPS_TIMEOUT),
    (CAPTION_KIND, caption_executor, CAPTION_DEVICE, CAPTION_TIMEOUT),
    (SEGMENT_KIND, segment_executor, SEGMENT_DEVICE, SEGMENT_TIMEOUT),
    (FACE_SWAP_KIND, face_swap_executor, FACE_SWAP_DEVICE, FACE_SWAP_TIMEOUT),
    (ENCODE_KIND, encode_executor, ENCODE_DEVICE, ENCODE_TIMEOUT),
)


def ensure_vision_executors_registered() -> bool:
    """Register all vision executors (idempotent). Returns True if ok."""
    from common_lib.modules.jobs.service import get_job_service

    try:
        svc = get_job_service()
        for kind, fn, device, timeout in _EXECUTORS:
            svc.register_executor(kind, fn, device=device, timeout=timeout)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("ensure_vision_executors_registered failed: %s", exc)
        return False


__all__ = [
    "CAPTION_DEVICE",
    "CAPTION_KIND",
    "CAPTION_TIMEOUT",
    "DIFFUSION_GENERATE_DEVICE",
    "DIFFUSION_GENERATE_KIND",
    "DIFFUSION_GENERATE_TIMEOUT",
    "DIFFUSION_LOAD_DEVICE",
    "DIFFUSION_LOAD_KIND",
    "DIFFUSION_LOAD_TIMEOUT",
    "ENCODE_DEVICE",
    "ENCODE_KIND",
    "ENCODE_TIMEOUT",
    "FACE_SWAP_DEVICE",
    "FACE_SWAP_KIND",
    "FACE_SWAP_TIMEOUT",
    "IMGOPS_DEVICE",
    "IMGOPS_KIND",
    "IMGOPS_TIMEOUT",
    "QWEN21_DEVICE",
    "QWEN21_IMG2IMG_KIND",
    "QWEN21_INPAINT_KIND",
    "QWEN21_OUTPAINT_KIND",
    "QWEN21_TIMEOUT",
    "QWEN21_TXT2IMG_KIND",
    "SEGMENT_DEVICE",
    "SEGMENT_KIND",
    "SEGMENT_TIMEOUT",
    "SOTA_BATCH_DEVICE",
    "SOTA_BATCH_KIND",
    "SOTA_BATCH_TIMEOUT",
    "SOTA_SINGLE_DEVICE",
    "SOTA_SINGLE_KIND",
    "SOTA_SINGLE_TIMEOUT",
    "caption_executor",
    "diffusion_generate_executor",
    "diffusion_load_executor",
    "encode_executor",
    "ensure_vision_executors_registered",
    "face_swap_executor",
    "imgops_executor",
    "qwen21_img2img_executor",
    "qwen21_inpaint_executor",
    "qwen21_outpaint_executor",
    "qwen21_txt2img_executor",
    "segment_executor",
    "sota_batch_executor",
    "sota_single_executor",
]
