"""Sandbox API — routes for interactive Python code execution in Docker containers."""

from fastapi import APIRouter
from .routes import router as sandbox_router
from .routes_code_mode import router as code_mode_router

router = APIRouter()
router.include_router(sandbox_router)
router.include_router(code_mode_router)

__all__ = ["router"]
