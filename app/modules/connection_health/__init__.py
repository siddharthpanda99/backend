"""
Connection Health Module
Provides health check telemetry and aggregated health dashboard data for connections.
"""

from app.modules.connection_health.routes import router

__all__ = ["router"]
