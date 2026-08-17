"""File System routes — thin router layer for common_lib.file_system service."""
from fastapi import APIRouter, HTTPException
from typing import Optional

router = APIRouter()


@router.get("/health")
async def health():
    """Health check for file_system module."""
    return {"status": "ok", "module": "file_system"}


@router.get("/info")
async def info():
    """Get file_system module info."""
    try:
        from common_lib.modules.file_system import __version__
        return {"module": "file_system", "version": __version__}
    except ImportError:
        return {"module": "file_system", "version": "unknown"}
