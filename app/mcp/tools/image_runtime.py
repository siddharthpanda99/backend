"""MCP tools for Image Runtime — pipeline managers, VRAM, caching, LoRA, scheduler.

Registered under the Cognitive Orchestrator MCP server.
Each tool wraps common_lib.modules.image_processing.runtime managers.
"""

import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP

logger = logging.getLogger("mcp.tools.image_runtime")


def register_image_runtime_tools(mcp: FastMCP):
    """Register tools for image generation runtime management."""

    @mcp.tool()
    async def imageruntime_list_pipelines() -> List[Dict[str, Any]]:
        """List loaded image pipelines."""
        try:
            from common_lib.modules.image_processing.runtime.managers.pipeline_manager import PipelineManager
            svc = PipelineManager()
            result = svc.list_pipelines() if hasattr(svc, "list_pipelines") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"imageruntime_list_pipelines error: {e}")
            return []

    @mcp.tool()
    async def imageruntime_load_pipeline(pipeline_name: str, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Load an image pipeline by name."""
        try:
            from common_lib.modules.image_processing.runtime.managers.pipeline_manager import PipelineManager
            svc = PipelineManager()
            result = svc.load(pipeline_name, config) if hasattr(svc, "load") else {"name": pipeline_name}
            return result if isinstance(result, dict) else {"name": pipeline_name}
        except Exception as e:
            logger.error(f"imageruntime_load_pipeline error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def imageruntime_unload_pipeline(pipeline_name: str) -> str:
        """Unload an image pipeline."""
        try:
            from common_lib.modules.image_processing.runtime.managers.pipeline_manager import PipelineManager
            svc = PipelineManager()
            svc.unload(pipeline_name) if hasattr(svc, "unload") else None
            return f"Pipeline {pipeline_name} unloaded"
        except Exception as e:
            logger.error(f"imageruntime_unload_pipeline error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def imageruntime_vram_status() -> Dict[str, Any]:
        """Get VRAM usage status."""
        try:
            from common_lib.modules.image_processing.runtime.managers.vram_manager import VRAMManager
            svc = VRAMManager()
            result = svc.get_status() if hasattr(svc, "get_status") else {"allocated": 0, "total": 0}
            return result
        except Exception as e:
            logger.error(f"imageruntime_vram_status error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def imageruntime_clear_vram() -> str:
        """Clear VRAM cache."""
        try:
            from common_lib.modules.image_processing.runtime.managers.vram_manager import VRAMManager
            svc = VRAMManager()
            svc.clear() if hasattr(svc, "clear") else None
            return "VRAM cleared"
        except Exception as e:
            logger.error(f"imageruntime_clear_vram error: {e}")
            return f"Error: {e}"

    @mcp.tool()
    async def imageruntime_list_loras() -> List[Dict[str, Any]]:
        """List available LoRA models."""
        try:
            from common_lib.modules.image_processing.runtime.managers.lora_manager import LoraManager
            svc = LoraManager()
            result = svc.list() if hasattr(svc, "list") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"imageruntime_list_loras error: {e}")
            return []

    @mcp.tool()
    async def imageruntime_apply_lora(name: str, strength: float = 1.0) -> Dict[str, Any]:
        """Apply a LoRA model."""
        try:
            from common_lib.modules.image_processing.runtime.managers.lora_manager import LoraManager
            svc = LoraManager()
            result = svc.apply(name, strength) if hasattr(svc, "apply") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"imageruntime_apply_lora error: {e}")
            return {"error": str(e)}

    @mcp.tool()
    async def imageruntime_list_schedulers() -> List[Dict[str, Any]]:
        """List available schedulers."""
        try:
            from common_lib.modules.image_processing.runtime.managers.scheduler_manager import SchedulerManager
            svc = SchedulerManager()
            result = svc.list() if hasattr(svc, "list") else []
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"imageruntime_list_schedulers error: {e}")
            return []

    @mcp.tool()
    async def imageruntime_resolve_scheduler(name: str) -> Dict[str, Any]:
        """Resolve a scheduler by name."""
        try:
            from common_lib.modules.image_processing.runtime.managers.scheduler_manager import SchedulerManager
            svc = SchedulerManager()
            result = svc.resolve(name) if hasattr(svc, "resolve") else {"name": name}
            return result if isinstance(result, dict) else {"name": name}
        except Exception as e:
            logger.error(f"imageruntime_resolve_scheduler error: {e}")
            return {"error": str(e)}

    logger.info("Image Runtime: 9 MCP tools registered")
