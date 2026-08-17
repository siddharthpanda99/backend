"""Image Runtime routes — thin router layer for common_lib.image_runtime service."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    """Health check for image_runtime module."""
    return {"status": "ok", "module": "image_runtime"}


@router.get("/info")
async def info():
    """Get image_runtime module info."""
    return {"module": "image_runtime", "version": "unknown"}
