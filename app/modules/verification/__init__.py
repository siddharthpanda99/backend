"""Verification Backend module — thin routes over common_lib verification service."""

from app.modules.verification.routes import router

__all__ = ["router"]
