import logging
from typing import List, Dict, Any, Optional
from app.mcp.fastmcp_compat import FastMCP
from ..mcp_dependencies import resolve_vision_controller

logger = logging.getLogger("mcp.tools.vision")

def register_vision_tools(mcp: FastMCP):
    """Register all vision generation and model management tools."""
    
    @mcp.tool()
    async def vision_generate(
        prompt: str,
        negative_prompt: str = "low quality, blurry, distorted",
        model_name: str = "v1-5-pruned-emaonly",
        upscale_by: float = 1.0,
        denoise: float = 0.7,
        seed: int = -1
    ) -> Dict[str, Any]:
        """
        Generate an image using the Stable Diffusion v1.5 High-Res pipeline.
        Returns the file path of the generated image and metadata.
        """
        controller = resolve_vision_controller()
        try:
            # We wrap the synchronous controller call in a thread if needed, 
            # but usually these controllers are designed for async-like usage or 
            # we just call them directly if they are lightweight enough to not block the event loop for too long.
            # However, image generation IS blocking. 
            # In a real FastMCP server, @mcp.tool handles async/sync correctly.
            from common_lib.modules.vision.schemas import VisionGenerateRequest
            request = VisionGenerateRequest(
                prompt=prompt,
                negative_prompt=negative_prompt,
                model_name=model_name,
                upscale_by=upscale_by,
                denoise=denoise,
                seed=seed
            )
            response = controller.generate_sd15_high_res(
                prompt=request.prompt,
                negative_prompt=request.negative_prompt,
                model_name=request.model_name,
                upscale_by=request.upscale_by,
                denoise=request.denoise,
                seed=request.seed
            )
            return {
                "status": "success",
                "file_path": response.file_path,
                "metadata": response.metadata,
                "view_url": f"/generated/{response.file_path}"
            }
        except Exception as e:
            logger.error(f"Vision generation failed: {e}")
            return {"status": "error", "message": str(e)}

    @mcp.tool()
    async def vision_list_models(category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all available Stable Diffusion models/checkpoints by category (e.g. 'sd15', 'sdxl')."""
        from ..modules.vision.routes import _get_checkpoints_from_filesystem
        checkpoints = _get_checkpoints_from_filesystem(category)
        return [
            {"id": c["id"], "name": c["name"], "category": c.get("category", "")}
            for c in checkpoints
        ]

    @mcp.tool()
    async def vision_get_gallery() -> Dict[str, Any]:
        """Retrieve the latest images from the generated content gallery."""
        from ..modules.vision.routes import list_gallery
        # We can call the router function directly if it doesn't depend on Request object
        # but list_gallery doesn't take parameters.
        response = await list_gallery()
        return response.model_dump()

    @mcp.tool()
    async def vision_list_samplers() -> List[str]:
        """List available sampling algorithms for image generation."""
        from common_lib.modules.image_processing.nodes.sampling.samplers_library import get_all_samplers
        return get_all_samplers("diffusers")
