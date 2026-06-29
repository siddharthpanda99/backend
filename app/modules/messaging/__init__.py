"""Messaging Gateway — unified multi-channel message dispatch for agents and systems."""

from app.modules.messaging.routes import router as messaging_router

__all__ = ["messaging_router"]
