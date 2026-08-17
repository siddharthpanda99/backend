import logging
import os
import psutil
from typing import Dict, Any
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.system")

def register_system_tools(mcp: FastMCP):
    """Register tools for host-level monitoring and global configuration management."""

    @mcp.tool()
    async def get_host_telemetry() -> Dict[str, Any]:
        """Retrieve detailed host-level hardware telemetry (CPU, RAM, Disk, Load)."""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory": dict(psutil.virtual_memory()._asdict()),
            "disk": dict(psutil.disk_usage('/')._asdict()),
            "load_avg": os.getloadavg() if hasattr(os, "getloadavg") else None
        }

    @mcp.tool()
    async def get_global_config() -> Dict[str, Any]:
        """Retrieve the active platform configuration and environment profile."""
        from app.core.config import settings
        return {
            "project_name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "env": settings.ENV,
            "features": list(settings.FEATURES.keys())
        }
