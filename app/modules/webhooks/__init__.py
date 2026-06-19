"""
Webhook Manager Module
Provides REST API for webhook endpoint management and delivery log tracking.
"""

from app.modules.webhooks.routes import router

__all__ = ["router"]
