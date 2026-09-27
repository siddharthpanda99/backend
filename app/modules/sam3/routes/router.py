"""SAM3 Routes — Thin API layer delegating to common_lib Sam3SessionService.

Long-running operations are jobs-backed by default; pass ``sync=true`` to run inline.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.modules.common.types.index import APIResponse
from common_lib.modules.image_processing.sam3.service import get_sam3_service, check_sam3_status

from app.modules.sam3.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(capture_job_actor)])


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_sam3_jobs():
    """Register SAM3 executors and return the actor-aware JobService proxy."""
    return owned_job_service()


def _sam3_job_payload(record: Any) -> Dict[str, Any]:
    refs: List[str] = []
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    return {
        "job_id": str(record.id),
        "status": str(record.status),
        "kind": str(record.kind),
        "progress": float(record.progress or 0.0),
        "result_refs": refs,
        "error": record.error,
    }


def _sam3_job_status(job_id: str) -> Dict[str, Any]:
    """Jobs-backed status view."""
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_sam3_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _sam3_job_payload(record)
    meta: Dict[str, Any] = {}
    try:
        refs = [str(r) for r in (record.get_result_refs() or [])]
    except Exception:
        refs = []
    for ref in refs:
        if not ref.endswith("result.json"):
            continue
        try:
            with open(ref, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                meta = loaded
                break
        except (OSError, ValueError):
            continue
    payload["meta"] = meta
    return payload


# ---------------------------------------------------------------------------
# Jobs endpoints
# ---------------------------------------------------------------------------


@router.get("/jobs")
async def list_sam3_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List background SAM3 jobs (newest first), newest-first with filters."""
    records = _ensure_sam3_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="sam3.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_sam3_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_sam3_job(job_id: str) -> Dict[str, Any]:
    """Poll a jobs-backed SAM3 job (progress, result_refs, result.json meta)."""
    return _sam3_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_sam3_job(job_id: str) -> Dict[str, Any]:
    """Cooperatively cancel a queued/running SAM3 job."""
    record = _ensure_sam3_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_sam3_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def sam3_job_events(job_id: str):
    """Stream SSE progress events backed by SAM3 job progress."""
    from fastapi.responses import StreamingResponse
    import asyncio
    import time as _time

    async def event_generator():
        deadline: float = _time.time() + 3600.0  # 1 hour max
        last_progress: float = -1.0
        yield f"event: started\ndata: {json.dumps({'job_id': job_id, 'status': 'queued'})}\n\n"
        while True:
            record: JobRecord | None = get_job_service().get(job_id)
            if record is None:
                yield f"event: failed\ndata: {json.dumps({'job_id': job_id, 'error': 'job not found'})}\n\n"
                return
            if record.progress != last_progress:
                last_progress = record.progress
                yield f"event: progress\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'progress': record.progress})}\n\n"
            if record.status in ("completed", "failed", "cancelled"):
                if record.status == "completed":
                    meta: Dict[str, Any] = {}
                    for ref in _sam3_job_payload(record)["result_refs"]:
                        if not ref.endswith("result.json"):
                            continue
                        try:
                            with open(ref, "r", encoding="utf-8") as fh:
                                loaded = json.load(fh)
                            if isinstance(loaded, dict):
                                meta = loaded
                                break
                        except (OSError, ValueError):
                            continue
                    yield f"event: completed\ndata: {json.dumps({'job_id': job_id, 'status': 'completed', 'meta': meta})}\n\n"
                else:
                    yield f"event: {record.status}\ndata: {json.dumps({'job_id': job_id, 'status': record.status, 'error': record.error or record.status})}\n\n"
                return
            if _time.time() > deadline:
                yield f"event: timeout\ndata: {json.dumps({'job_id': job_id, 'error': 'progress stream timed out'})}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
async def session_action(req: SessionAction, sync: bool = False):
    """Execute a SAM3 session action.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if sync:
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

    from app.modules.sam3.runtime.job_executors import SESSION_ACTION_KIND

    record = _ensure_sam3_jobs().submit(
        SESSION_ACTION_KIND,
        params={
            "session_id": req.session_id,
            "action": req.action,
            "params": req.params,
        },
    )
    return APIResponse(
        status="queued",
        message=f"Action '{req.action}' queued",
        data=_sam3_job_payload(record),
    )


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
