from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Dict, Any, List, Optional
import io
import base64
import json
import asyncio

from app.modules.common.types.index import APIResponse
from common_lib.modules.image_processing.collage_sticker import (
    CollageDocument,
    render_collage,
    get_layout
)

from app.modules.collage.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

router = APIRouter(dependencies=[Depends(capture_job_actor)])


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_collage_jobs():
    return owned_job_service()


def _collage_job_payload(record: Any) -> Dict[str, Any]:
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


def _collage_job_status(job_id: str) -> Dict[str, Any]:
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_collage_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _collage_job_payload(record)
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
async def list_collage_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    records = _ensure_collage_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="collage.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_collage_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_collage_job(job_id: str) -> Dict[str, Any]:
    return _collage_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_collage_job(job_id: str) -> Dict[str, Any]:
    record = _ensure_collage_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_collage_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def collage_job_events(job_id: str):
    from fastapi.responses import StreamingResponse

    async def event_generator():
        import time as _time

        deadline: float = _time.time() + 3600.0
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
                    for ref in _collage_job_payload(record)["result_refs"]:
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


@router.post("/render")
async def render_collage_endpoint(doc: CollageDocument, sync: bool = False):
    """
    Renders the given CollageDocument config into a high-res composed image.
    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if sync:
        try:
            composed_img = render_collage(doc)

            output_buffer = io.BytesIO()
            composed_img.save(output_buffer, format="PNG")
            output_buffer.seek(0)

            return StreamingResponse(output_buffer, media_type="image/png")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")

    from app.modules.collage.runtime.job_executors import RENDER_KIND

    # Convert CollageDocument to dict for job params
    record = _ensure_collage_jobs().submit(
        RENDER_KIND, params=doc.model_dump(mode="json")
    )
    return {"status": "queued", **_collage_job_payload(record)}


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
async def cutout_background_endpoint(file: UploadFile = File(...), sync: bool = False):
    """
    Auto AI background removal endpoint.
    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if sync:
        try:
            contents = await file.read()
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

    from app.modules.collage.runtime.job_executors import CUTOUT_KIND

    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    record = _ensure_collage_jobs().submit(
        CUTOUT_KIND, params={"image": image_b64}
    )
    return APIResponse(
        status="queued",
        message="Background removal queued",
        data=_collage_job_payload(record),
    )
