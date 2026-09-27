"""
Filter CRUD API Routes - /api/v1/filters/

Provides full CRUD operations for image filters, preset management,
filter application, and pipeline execution.

Long-running operations are jobs-backed by default; pass ``sync=true`` to run inline.
"""

import base64
import json
import logging
import io
import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query, Depends
from fastapi.responses import StreamingResponse
from PIL import Image
import numpy as np

from common_lib.modules.image_processing.services.filter_service import (
    FilterService,
    FilterCreateRequest,
    FilterUpdateRequest,
    FilterResponse,
    FilterOperation,
)

from app.modules.filters.runtime.actor import capture_job_actor, owned_job_service
from common_lib.modules.jobs.artifacts import job_dir
from common_lib.modules.jobs.models import JobRecord
from common_lib.modules.jobs.service import get_job_service

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(capture_job_actor)])
service = FilterService()


# ---------------------------------------------------------------------------
# Jobs-backed execution helpers
# ---------------------------------------------------------------------------


def _ensure_filters_jobs():
    """Register filters executors and return the actor-aware JobService proxy."""
    return owned_job_service()


def _filters_job_payload(record: Any) -> Dict[str, Any]:
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


def _filters_job_status(job_id: str) -> Dict[str, Any]:
    """Jobs-backed status view with b64-free metadata (never inline blobs)."""
    from fastapi import HTTPException as _HTTPException

    svc = _ensure_filters_jobs()
    record = svc.get(job_id)
    if record is None:
        raise _HTTPException(status_code=404, detail=f"Job {job_id} not found")
    payload: Dict[str, Any] = _filters_job_payload(record)
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
async def list_filters_jobs(
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """List background filter jobs (newest first), newest-first with filters."""
    records = _ensure_filters_jobs().list(
        status=status,
        kind=kind,
        kind_prefix="filters.",
        limit=min(max(limit, 1), 200),
        offset=max(offset, 0),
    )
    items = [_filters_job_payload(record) for record in records]
    return {"data": items, "total": len(items)}


@router.get("/jobs/{job_id}")
async def get_filters_job(job_id: str) -> Dict[str, Any]:
    """Poll a jobs-backed filter job (progress, result_refs, result.json meta)."""
    return _filters_job_status(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_filters_job(job_id: str) -> Dict[str, Any]:
    """Cooperatively cancel a queued/running filter job."""
    record = _ensure_filters_jobs().cancel(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return {"status": "ok", **_filters_job_payload(record)}


@router.get("/jobs/{job_id}/events")
async def filters_job_events(job_id: str):
    """Stream SSE progress events backed by filter job progress."""
    async def event_generator():
        import time as _time

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
                    for ref in _filters_job_payload(record)["result_refs"]:
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


@router.get("/", response_model=List[FilterResponse])
async def list_filters(
    category: Optional[str] = Query(None, description="Filter by category"),
    tags: Optional[str] = Query(None, description="Filter by tags (comma-separated)"),
    author: Optional[str] = Query(None, description="Filter by author"),
    is_public: Optional[bool] = Query(None, description="Filter by public status"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Result offset"),
):
    """List all filters with optional filtering."""
    tag_list = tags.split(",") if tags else None
    return service.list_filters(
        category=category,
        tags=tag_list,
        author=author,
        is_public=is_public,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.post("/", response_model=FilterResponse, status_code=201)
async def create_filter(request: FilterCreateRequest, author: str = "api"):
    """Create a new filter."""
    try:
        return service.create_filter(request, author=author)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{filter_id}", response_model=FilterResponse)
async def get_filter(filter_id: str):
    """Get a filter by ID."""
    result = service.get_filter(filter_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Filter not found: {filter_id}")
    return result


@router.put("/{filter_id}", response_model=FilterResponse)
async def update_filter(filter_id: str, request: FilterUpdateRequest):
    """Update an existing filter."""
    try:
        result = service.update_filter(filter_id, request)
        if not result:
            raise HTTPException(
                status_code=404, detail=f"Filter not found: {filter_id}"
            )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{filter_id}", status_code=204)
async def delete_filter(filter_id: str):
    """Delete a filter."""
    success = service.delete_filter(filter_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Filter not found: {filter_id}")


@router.post("/{filter_id}/apply")
async def apply_filter(
    filter_id: str,
    file: UploadFile = File(...),
    sync: bool = False,
):
    """Apply a filter to an uploaded image.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    if sync:
        try:
            image = Image.open(io.BytesIO(contents)).convert("RGB")
            result = service.apply_filter(image, filter_id)

            buf = io.BytesIO()
            result.save(buf, format="PNG")
            buf.seek(0)

            from fastapi.responses import Response

            return Response(content=buf.getvalue(), media_type="image/png")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to apply filter: {e}")
            raise HTTPException(status_code=500, detail="Failed to apply filter")

    from app.modules.filters.runtime.job_executors import APPLY_KIND

    record = _ensure_filters_jobs().submit(
        APPLY_KIND, params={"filter_id": filter_id, "image": image_b64}
    )
    return {"status": "queued", **_filters_job_payload(record)}


@router.post("/apply")
async def apply_operations(
    file: UploadFile = File(...),
    operations: str = Form(...),
    sync: bool = False,
):
    """Apply a list of operations to an uploaded image.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    if sync:
        try:
            import json

            op_data = json.loads(operations)
            ops = [FilterOperation(**op) for op in op_data]

            image = Image.open(io.BytesIO(contents)).convert("RGB")
            result = service.apply_operations(image, ops)

            buf = io.BytesIO()
            result.save(buf, format="PNG")
            buf.seek(0)

            from fastapi.responses import Response

            return Response(content=buf.getvalue(), media_type="image/png")
        except Exception as e:
            logger.error(f"Failed to apply operations: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to apply operations: {str(e)}"
            )

    from app.modules.filters.runtime.job_executors import APPLY_OPERATIONS_KIND

    record = _ensure_filters_jobs().submit(
        APPLY_OPERATIONS_KIND, params={"operations": operations, "image": image_b64}
    )
    return {"status": "queued", **_filters_job_payload(record)}


@router.post("/preview")
async def preview_filter(
    file: UploadFile = File(...),
    operations: str = Form(...),
    sync: bool = False,
):
    """Preview filter operations on an image (returns base64 + metadata).

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    if sync:
        try:
            import json

            op_data = json.loads(operations)
            ops = [FilterOperation(**op) for op in op_data]

            image = Image.open(io.BytesIO(contents)).convert("RGB")
            result = service.apply_operations(image, ops)

            buf = io.BytesIO()
            result.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

            return {
                "preview": f"data:image/png;base64,{b64}",
                "width": result.width,
                "height": result.height,
                "operations_count": len(ops),
            }
        except Exception as e:
            logger.error(f"Failed to preview filter: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to preview: {str(e)}")

    from app.modules.filters.runtime.job_executors import PREVIEW_KIND

    record = _ensure_filters_jobs().submit(
        PREVIEW_KIND, params={"operations": operations, "image": image_b64}
    )
    return {"status": "queued", **_filters_job_payload(record)}


@router.get("/{filter_id}/export")
async def export_filter(filter_id: str):
    """Export a filter as JSON."""
    try:
        json_str = service.export_filter_json(filter_id)
        from fastapi.responses import JSONResponse
        import json

        return JSONResponse(content=json.loads(json_str))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/import")
async def import_filter(
    name: str = Form(...),
    category: str = Form("custom"),
    description: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    is_public: bool = Form(False),
    operations: str = Form(...),
    author: str = "api",
):
    """Import a filter from JSON data."""
    try:
        import json

        op_data = json.loads(operations)
        ops = [FilterOperation(**op) for op in op_data]

        request = FilterCreateRequest(
            name=name,
            description=description,
            category=category,
            tags=tags.split(",") if tags else [],
            is_public=is_public,
            operations=ops,
        )
        return service.create_filter(request, author=author)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/categories/list")
async def get_categories():
    """Get all available filter categories."""
    categories = service.get_filter_categories()
    return {"categories": categories}


@router.get("/tags/list")
async def get_tags():
    """Get all available filter tags."""
    tags = service.get_filter_tags()
    return {"tags": tags}


@router.get("/presets/list")
async def list_presets(category: Optional[str] = Query(None)):
    """List built-in filter presets."""
    presets = service.get_presets(category=category)
    return {"presets": presets, "count": len(presets)}


@router.post("/presets/generate-previews")
async def generate_preset_previews(
    regenerate: bool = Query(False, description="Regenerate existing previews"),
    sync: bool = False,
):
    """Generate preview thumbnails for all built-in filter presets.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if sync:
        try:
            results = service.generate_preset_previews(regenerate=regenerate)
            generated = sum(1 for r in results if r["status"] == "generated")
            skipped = sum(1 for r in results if r["status"] == "skipped")
            errors = sum(1 for r in results if r["status"] == "error")
            return {
                "results": results,
                "summary": {
                    "total": len(results),
                    "generated": generated,
                    "skipped": skipped,
                    "errors": errors,
                },
            }
        except Exception as e:
            logger.error(f"Failed to generate preset previews: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    from app.modules.filters.runtime.job_executors import PRESET_PREVIEWS_KIND

    record = _ensure_filters_jobs().submit(
        PRESET_PREVIEWS_KIND, params={"regenerate": regenerate}
    )
    return {"status": "queued", **_filters_job_payload(record)}


@router.post("/presets/{preset_id}/apply")
async def apply_preset(
    preset_id: str,
    file: UploadFile = File(...),
    sync: bool = False,
):
    """Apply a built-in preset to an uploaded image.

    Jobs-backed by default; pass ``sync=true`` to run inline.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    contents = await file.read()
    image_b64 = base64.b64encode(contents).decode("utf-8")

    if sync:
        try:
            image = Image.open(io.BytesIO(contents)).convert("RGB")
            result = service.apply_preset(image, preset_id)

            buf = io.BytesIO()
            result.save(buf, format="PNG")
            buf.seek(0)

            from fastapi.responses import Response

            return Response(content=buf.getvalue(), media_type="image/png")
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except Exception as e:
            logger.error(f"Failed to apply preset: {e}")
            raise HTTPException(status_code=500, detail="Failed to apply preset")

    from app.modules.filters.runtime.job_executors import PRESET_APPLY_KIND

    record = _ensure_filters_jobs().submit(
        PRESET_APPLY_KIND, params={"preset_id": preset_id, "image": image_b64}
    )
    return {"status": "queued", **_filters_job_payload(record)}


@router.get("/operation-types")
async def get_operation_types():
    """Get all valid operation types with descriptions."""
    types_info = {
        "exposure": {
            "description": "Adjust exposure by EV stops",
            "params": {"ev": "float, -5 to 5"},
        },
        "brightness": {
            "description": "Adjust brightness",
            "params": {"value": "int, 0-200 (100=default)"},
        },
        "contrast": {
            "description": "Adjust contrast",
            "params": {"value": "int, 0-200 (100=default)"},
        },
        "gamma": {
            "description": "Gamma correction",
            "params": {"gamma": "float, 0.1-5.0 (1.0=default)"},
        },
        "saturation": {
            "description": "Adjust saturation",
            "params": {"amount": "int, 0-200 (100=default)"},
        },
        "vibrance": {
            "description": "Intelligent saturation",
            "params": {"amount": "int, -100 to 100"},
        },
        "temperature": {
            "description": "Color temperature",
            "params": {"value": "int, -100 to 100"},
        },
        "tint": {
            "description": "Green-magenta tint",
            "params": {"value": "int, -100 to 100"},
        },
        "hue_shift": {
            "description": "Shift hue by degrees",
            "params": {"degrees": "float, 0-360"},
        },
        "highlights": {
            "description": "Adjust highlights",
            "params": {"amount": "int, -100 to 100"},
        },
        "shadows": {
            "description": "Adjust shadows",
            "params": {"amount": "int, -100 to 100"},
        },
        "whites": {
            "description": "Adjust white point",
            "params": {"amount": "int, -100 to 100"},
        },
        "blacks": {
            "description": "Adjust black point",
            "params": {"amount": "int, -100 to 100"},
        },
        "clarity": {
            "description": "Local contrast enhancement",
            "params": {"amount": "int, -100 to 100"},
        },
        "dehaze": {
            "description": "Remove haze/fog",
            "params": {"amount": "int, 0-100"},
        },
        "gaussian_blur": {
            "description": "Gaussian blur",
            "params": {"radius": "float, 0.1-50"},
        },
        "motion_blur": {
            "description": "Directional motion blur",
            "params": {"length": "int, 1-50", "angle": "float, 0-360"},
        },
        "lens_blur": {
            "description": "Lens/bloom blur",
            "params": {"radius": "float, 0.1-50"},
        },
        "tilt_shift": {
            "description": "Tilt-shift blur",
            "params": {"focus_center": "float, 0-1", "focus_width": "float, 0-1"},
        },
        "unsharp_mask": {
            "description": "Unsharp mask sharpening",
            "params": {"radius": "float, 0.1-10", "amount": "float, 0-2"},
        },
        "high_pass_sharpen": {
            "description": "High-pass sharpening",
            "params": {"radius": "float, 0.1-10", "amount": "float, 0-2"},
        },
        "detail_enhancement": {
            "description": "Laplacian detail enhancement",
            "params": {"amount": "float, 0-5"},
        },
        "film_grain": {
            "description": "Add film grain",
            "params": {"intensity": "float, 0-1"},
        },
        "vignette": {
            "description": "Vignette effect",
            "params": {"strength": "float, 0-1", "feather": "float, 0-1"},
        },
        "bloom": {
            "description": "Bloom/glow effect",
            "params": {
                "threshold": "float, 0-1",
                "radius": "float, 0-20",
                "intensity": "float, 0-1",
            },
        },
        "color_balance": {
            "description": "Color balance by tone zone",
            "params": {"highlights": "float", "midtones": "float", "shadows": "float"},
        },
        "split_toning": {
            "description": "Split-toning effect",
            "params": {
                "shadows_color": "[r,g,b]",
                "highlights_color": "[r,g,b]",
                "balance": "float",
            },
        },
        "invert": {"description": "Invert colors", "params": {}},
        "tone_mapping": {
            "description": "HDR tone mapping",
            "params": {
                "operator": "str: reinhard/aces_filmic/uncharted2",
                "exposure": "float",
            },
        },
        "film_stock": {
            "description": "Film stock emulation",
            "params": {
                "stock": "str: kodak_portra_400/fuji_velvia_50",
                "intensity": "float",
            },
        },
        "watercolor": {
            "description": "Watercolor effect",
            "params": {"edge_width": "int", "blur_radius": "int"},
        },
        "oil_painting": {
            "description": "Oil painting effect",
            "params": {"size": "int, 1-8"},
        },
        "sketch": {
            "description": "Pencil sketch effect",
            "params": {"blur_radius": "int, 1-51"},
        },
        "glitch": {
            "description": "Glitch/artifact effect",
            "params": {"intensity": "float, 0-1", "displacement": "int"},
        },
    }
    return {"operation_types": types_info, "count": len(types_info)}


__all__ = ["router"]
