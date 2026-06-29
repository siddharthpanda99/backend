"""Sandbox API — routes for interactive Python code execution in Docker containers."""

from fastapi import APIRouter
from .routes import router as sandbox_router

router = APIRouter()
router.include_router(sandbox_router)

__all__ = ["router"]
